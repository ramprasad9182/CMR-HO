from odoo import models, fields
from odoo.exceptions import ValidationError
import base64
from io import BytesIO
import pandas as pd
import re

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

        # 🚀 preload products (performance)
        products = self.env['product.product'].search([])

        barcode_map = {p.barcode: p for p in products if p.barcode}
        default_code_map = {p.default_code: p for p in products if p.default_code}
        name_map = {p.name.strip(): p for p in products if p.name}

        partner = self.env.ref('base.partner_admin')

        MAX_QTY = 6000
        current_qty = 0
        po = None

        created_pos = self.env['purchase.order']
        line_buffer = []

        for index, row in df.iterrows():

            qty = float(row['Closing Qty'] or 0)
            if qty <= 0:
                continue

            # 🚀 SPLIT LOGIC
            if not po or (current_qty + qty > MAX_QTY):

                if line_buffer:
                    self.env['purchase.order.line'].create(line_buffer)
                    line_buffer = []
                    self.env.cr.commit()

                po = self.env['purchase.order'].create({
                    'partner_id': partner.id,
                    'date_order': fields.Datetime.now(),
                    'nhcl_po_type': 'data_import',
                })

                created_pos |= po
                current_qty = 0

            # ✅ product fields
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

            # ✅ barcode fallback
            move_brand_barcode = barcode if barcode and barcode != '-' else item_code

            cp = float(row['Cost Rate'] or 0)
            rsp = float(row['RSP'] or 0)

            if cp <= 0 or rsp <= 0:
                raise ValidationError(
                    f"Invalid pricing for {product.display_name}"
                )

            current_qty += qty

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
                'type_product': 'promo',
            })

            # 🚀 batch insert
            if len(line_buffer) >= 2000:
                self.env['purchase.order.line'].create(line_buffer)
                line_buffer = []
                self.env.cr.commit()

        # final flush
        if line_buffer:
            self.env['purchase.order.line'].create(line_buffer)
            self.env.cr.commit()

        # ✅ SUCCESS MESSAGE
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Purchase Orders created successfully: {len(created_pos)}',
                'type': 'success',
                'sticky': False,
            }
        }
