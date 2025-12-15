from odoo import models, fields, _
from odoo.exceptions import UserError
import base64
from io import BytesIO
import pandas as pd

class ImportStockReceiptWizard(models.TransientModel):
    _name = 'import.stock.receipt.wizard'
    _description = 'Import Stock Receipts Wizard'

    file = fields.Binary(string="XLSX File", required=True)
    file_name = fields.Char(string="Filename")

    def action_import_receipts(self):
        if not self.file:
            raise UserError("No file uploaded.")
            # Decode the binary data to get the file content
        file_content = base64.b64decode(self.file)
        # Load the file content into a pandas DataFrame
        try:
            df = pd.read_excel(BytesIO(file_content))
        except Exception as e:
            raise UserError(f"Failed to read the Excel file: {str(e)}")
        # Validate the required columns in the DataFrame
        required_columns = [
            'partner_id', 'location_dest_id', 'scheduled_date', 'origin', 'is_landed_cost',
            'location_id', 'move_ids_without_package/product_id', 'move_ids_without_package/product_qty',
            'move_ids_without_package/move_brand_barcode','move_ids_without_package/move_cp', 'move_ids_without_package/move_mrp',
            'move_ids_without_package/move_rsp', 'move_ids_without_package/type_product',
        ]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise UserError(f"Missing columns: {', '.join(missing_columns)} in the provided file.")
        # Process each row in the DataFrame
        grouped = df.groupby('origin')

        for origin, group in grouped:
            # Use the first row in the group to create the picking
            first_row = group.iloc[0]

            partner = self.env['res.partner'].search([('name', '=', first_row['partner_id'])], limit=1)
            if not partner:
                raise UserError(f"Partner '{first_row['partner_id']}' not found in Odoo.")

            location_src = self.env['stock.location'].search([('complete_name', '=', first_row['location_id'])],
                                                             limit=1)
            location_dest = self.env['stock.location'].search([('complete_name', '=', first_row['location_dest_id'])],
                                                              limit=1)
            if not location_src or not location_dest:
                raise UserError(f"Location(s) not found: {first_row['location_id']} or {first_row['location_dest_id']}")

            # Create one stock.picking for this origin group
            picking = self.env['stock.picking'].create({
                'partner_id': partner.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
                'stock_type': 'data_import',
                'scheduled_date': first_row['scheduled_date'],
                'is_landed_cost': first_row['is_landed_cost'],
                'origin': origin,
                'picking_type_id': 1,
                'state': 'draft',
            })
            for _, row in group.iterrows():
                product = self.env['product.product'].search(
                    [('display_name', '=', row['move_ids_without_package/product_id'])], limit=1)
                if not product:
                    raise UserError(f"Product '{row['move_ids_without_package/product_id']}' not found in Odoo.")
                cp = float(row['move_ids_without_package/move_cp'] or 0)
                mrp = float(row['move_ids_without_package/move_mrp'] or 0)
                rsp = float(row['move_ids_without_package/move_rsp'] or 0)

                if cp <= 0 or mrp <= 0 or rsp <= 0:
                    raise UserError(
                        f"Invalid pricing in row for product '{product.display_name}': "
                        f"CP={cp}, MRP={mrp}, RSP={rsp}. All must be > 0.")
                self.env['stock.move'].create({
                    'product_id': product.id,
                    'name': product.name,
                    'product_uom_qty': row['move_ids_without_package/product_qty'],
                    'location_id': location_src.id,
                    'location_dest_id': location_dest.id,
                    'partner_id': partner.id,
                    'picking_id': picking.id,
                    'type_product': row['move_ids_without_package/type_product'],
                    'move_brand_barcode': row['move_ids_without_package/move_brand_barcode'],
                    'move_cp': cp,
                    'move_mrp': mrp,
                    'move_rsp': rsp,
                })
