from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64
from io import BytesIO
import pandas as pd
import re
import zipfile
import tempfile

class ImportStockReceiptWizard(models.TransientModel):
    _name = 'import.stock.receipt.wizard'
    _description = 'Import Stock Receipts Wizard'

    file = fields.Binary(string="XLSX File", required=True)
    file_name = fields.Char(string="Filename")

    def action_import_receipts(self):
        if not self.file:
            raise ValidationError("No file uploaded.")

        # Decode file
        try:
            file_content = base64.b64decode(self.file)
            df = pd.read_excel(BytesIO(file_content))
        except Exception as e:
            raise ValidationError("Failed to read the Excel file")

        # Required columns
        required_columns = [
            'partner_id', 'location_dest_id', 'scheduled_date', 'origin', 'is_landed_cost',
            'location_id', 'move_ids_without_package/product_id',
            'move_ids_without_package/product_qty',
            'move_ids_without_package/move_brand_barcode',
            'move_ids_without_package/move_cp',
            'move_ids_without_package/move_mrp',
            'move_ids_without_package/move_rsp',
            'move_ids_without_package/type_product',
        ]

        missing_columns = [c for c in required_columns if c not in df.columns]
        if missing_columns:
            raise ValidationError(f"Missing columns: {', '.join(missing_columns)}")

        created_pickings = self.env['stock.picking']

        # Group by Origin
        grouped = df.groupby('origin')
        company = self.env.company
        incoming_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('company_id', '=', company.id)], limit=1)

        if not incoming_type:
            raise ValidationError(f"No Incoming Operation Type found for company {company.name}")

        for origin, group in grouped:
            first_row = group.iloc[0]

            partner = self.env['res.partner'].search(
                [('name', '=', first_row['partner_id'])], limit=1)
            if not partner:
                raise ValidationError(f"Partner '{first_row['partner_id']}' not found.")

            location_src = self.env['stock.location'].search(
                [('complete_name', '=', first_row['location_id'])], limit=1)
            location_dest = self.env['stock.location'].search(
                [('complete_name', '=', first_row['location_dest_id'])], limit=1)

            if not location_src or not location_dest:
                raise ValidationError(f"Location not found: {first_row['location_id']} or {first_row['location_dest_id']}")
            existing_picking = self.env['stock.picking'].sudo().search(
                [('origin', '=', origin)],limit=1)
            if existing_picking:
                raise ValidationError(
                    f"Receipt with Origin '{origin}' already exists "
                    f"(Picking: {existing_picking.name}). "
                    f"Please use a unique Origin."
                )

            # Create Picking
            picking = self.env['stock.picking'].create({
                'partner_id': partner.id,
                'location_id': location_src.id,
                'location_dest_id': location_dest.id,
                'scheduled_date': first_row['scheduled_date'],
                'is_landed_cost': first_row['is_landed_cost'],
                'origin': origin,
                'stock_type': 'data_import',
                'picking_type_id': incoming_type.id,
            })

            created_pickings |= picking

            # Create Stock Moves
            for _, row in group.iterrows():
                product_name = row['move_ids_without_package/product_id']

                # Extract default_code from [CODE]
                match = re.search(r'\[(.*?)\]', product_name)
                if not match:
                    raise ValidationError(f"Invalid product format: {product_name}")

                default_code = match.group(1)

                product = self.env['product.product'].search(
                    [('default_code', '=', default_code)], limit=1)
                if not product:
                    raise ValidationError(f"Product with Internal Reference '{default_code}' not found.")

                cp = float(row['move_ids_without_package/move_cp'] or 0)
                mrp = float(row['move_ids_without_package/move_mrp'] or 0)
                rsp = float(row['move_ids_without_package/move_rsp'] or 0)

                if cp <= 0 or mrp <= 0 or rsp <= 0:
                    raise ValidationError(f"Invalid pricing for {product.display_name} → "
                        f"CP={cp}, MRP={mrp}, RSP={rsp}")

                self.env['stock.move'].create({
                    'name': product.name,
                    'product_id': product.id,
                    'product_uom_qty': row['move_ids_without_package/product_qty'],
                    'quantity': row['move_ids_without_package/product_qty'],
                    'location_id': location_src.id,
                    'location_dest_id': location_dest.id,
                    'picking_id': picking.id,
                    'partner_id': partner.id,
                    'type_product': row['move_ids_without_package/type_product'],
                    'move_brand_barcode': row['move_ids_without_package/move_brand_barcode'],
                    'move_cp': cp,
                    'move_mrp': mrp,
                    'move_rsp': rsp,
                })
        # -------------------------
        # SUCCESS + OPEN RECORD(S)
        # -------------------------
        if len(created_pickings) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Stock Receipt',
                'res_model': 'stock.picking',
                'view_mode': 'form',
                'res_id': created_pickings.id,
                'target': 'current',
            }

        return {
            'type': 'ir.actions.act_window',
            'name': 'Imported Stock Receipts',
            'res_model': 'stock.picking',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created_pickings.ids)],
            'target': 'current',
        }


class ImportPOWizard(models.TransientModel):
    _name = 'import.po.wizard'
    _description = 'Import PO Wizard'

    file = fields.Binary(string="XLSX File", required=True)
    file_name = fields.Char(string="Filename")

    def action_import_purchase_orders(self):
        if not self.file:
            raise ValidationError("No file uploaded.")

        try:
            file_content = base64.b64decode(self.file)
            df = pd.read_excel(BytesIO(file_content))
        except Exception:
            raise ValidationError("Failed to read the Excel file")

        required_columns = [
            'Odoo Product',
            'Item Code',
            'Barcode',
            'RSP',
            'Cost Rate',
            'Closing Qty',
        ]

        missing = [c for c in required_columns if c not in df.columns]
        if missing:
            raise ValidationError(f"Missing columns: {', '.join(missing)}")

        # preload products
        products = self.env['product.product'].search([])

        barcode_map = {p.barcode: p for p in products if p.barcode}
        default_code_map = {p.default_code: p for p in products if p.default_code}
        name_map = {p.name.strip(): p for p in products if p.name}

        partner = self.env.ref('base.partner_admin')
        picking = self.env['stock.picking.type'].search([('stock_picking_type','=','receipt'),('company_id','=',self.env.company.id)])

        # ✅ create single PO
        po = self.env['purchase.order'].create({
            'partner_id': partner.id,
            'date_order': fields.Datetime.now(),
            'nhcl_po_type': 'data_import',
            'company_id': self.env.company.id,
            'picking_type_id': picking.id
        })

        line_buffer = []

        for index, row in df.iterrows():

            qty = float(row['Closing Qty'] or 0)
            if qty <= 0:
                continue

            barcode = str(row['Barcode']).strip() if row['Barcode'] else ''
            item_code = str(row['Item Code']).strip() if row['Item Code'] else ''
            odoo_product_name = str(row['Odoo Product']).strip() if row['Odoo Product'] else ''

            product = False

            # 1. Barcode
            if barcode and barcode != '-':
                product = barcode_map.get(barcode)

            # 2. Item Code
            if not product and item_code:
                product = default_code_map.get(item_code)

            # 3. Exact Name
            if not product and odoo_product_name:
                product = name_map.get(odoo_product_name)

            # 4. Fallback search
            if not product and odoo_product_name:
                product = self.env['product.product'].search([
                    ('name', 'ilike', odoo_product_name)
                ], limit=1)

            if not product:
                raise ValidationError(
                    f"Product not found → Barcode: {barcode}, Item: {item_code}, Name: {odoo_product_name}"
                )

            move_brand_barcode = barcode if barcode and barcode != '-' else item_code

            cp = float(row['Cost Rate'] or 0)
            rsp = float(row['RSP'] or 0)

            if cp <= 0 or rsp <= 0:
                raise ValidationError(
                    f"Invalid pricing for {product.display_name}"
                )

            line_buffer.append({
                'order_id': po.id,
                'product_id': product.id,
                'name': product.name,
                'product_qty': qty,
                'price_unit': cp,
                'date_planned': fields.Datetime.now(),
                'move_brand_barcode': move_brand_barcode,
                'move_cp': cp,
                'move_mrp': 10000,
                'move_rsp': rsp,
                'type_product': 'brand',
                'company_id': self.env.company.id,
            })

        # ✅ create all lines at once
        if line_buffer:
            self.env['purchase.order.line'].create(line_buffer)

        # ✅ SUCCESS MESSAGE
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Purchase Order {po.name} created successfully with {len(line_buffer)} lines',
                'type': 'success',
                'sticky': False,
            }
        }



class ExcelQtySplitWizard(models.TransientModel):
    _name = 'excel.qty.split.wizard'
    _description = 'Split Excel by Quantity'

    file = fields.Binary(string="Upload Excel", required=True)
    filename = fields.Char()
    output_file = fields.Binary(string="Download ZIP")
    output_filename = fields.Char(default="split_files.zip")

    max_qty = fields.Integer(default=6000, string="Max Qty per File")



    @api.constrains('max_qty')
    def check_max_qty(self):
        if self.max_qty > 9000:
            raise ValidationError("You can not give more than 9000 Qty.")
        elif self.max_qty < 0:
            raise ValidationError("You can not give negative Qty.")

    def action_split_file(self):
        file_content = base64.b64decode(self.file)
        df = pd.read_excel(BytesIO(file_content))

        required_cols = [
            'Odoo_Product', 'Age_Code', 'Item_Code',
            'Barcode', 'RSP', 'Cost_Rate', 'Closing_Qty'
        ]

        df = df[required_cols].copy()
        df['Closing_Qty'] = df['Closing_Qty'].fillna(0).astype(float)

        file_index = 1
        current_qty = 0
        current_chunk = []

        temp_zip = tempfile.NamedTemporaryFile(delete=False)
        zipf = zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED)

        def add_to_zip(chunk, index):
            if not chunk:
                return
            chunk_df = pd.DataFrame(chunk)
            buffer = BytesIO()
            chunk_df.to_excel(buffer, index=False)
            buffer.seek(0)
            zipf.writestr(f'{self.env.company.name}_{index}.xlsx', buffer.read())

        for row in df.itertuples(index=False):
            row_dict = row._asdict()
            remaining_qty = row_dict['Closing_Qty']

            while remaining_qty > 0:
                available = self.max_qty - current_qty

                if available == 0:
                    add_to_zip(current_chunk, file_index)
                    file_index += 1
                    current_chunk = []
                    current_qty = 0
                    available = self.max_qty

                if remaining_qty <= available:
                    new_row = dict(row_dict)
                    new_row['Closing_Qty'] = remaining_qty
                    current_chunk.append(new_row)
                    current_qty += remaining_qty
                    remaining_qty = 0
                else:
                    new_row = dict(row_dict)
                    new_row['Closing_Qty'] = available
                    current_chunk.append(new_row)

                    remaining_qty -= available
                    current_qty += available

        if current_chunk:
            add_to_zip(current_chunk, file_index)

        zipf.close()

        with open(temp_zip.name, 'rb') as f:
            self.output_file = base64.b64encode(f.read())
        company_name = re.sub(r'[^A-Za-z0-9_-]', '', self.env.company.name.replace(' ', '_'))
        self.output_filename = f"{company_name}.zip"

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'excel.qty.split.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }