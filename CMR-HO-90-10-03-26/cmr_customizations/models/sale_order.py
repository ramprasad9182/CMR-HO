from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from collections import defaultdict
import re
from datetime import timedelta

class StoreIndents(models.Model):
    _name = "store.indent.refernce"

    product_id = fields.Many2one("product.product", string="Product", related="po_line_id.product_id")
    so_order_id = fields.Many2one('sale.order', string="Order Reference")
    po_line_id = fields.Many2one('purchase.order.line', string="PO Line")
    pi_quantity = fields.Float(string="PI Quantity", related="po_line_id.product_qty")
    allocated_quantity = fields.Float(string="Allocated Quantity")
    order_date = fields.Datetime(string="Order Date", related="po_line_id.date_order")
    company_id = fields.Many2one("res.company", string="Company", related="po_line_id.order_id.company_id")


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    so_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('direct_po','Direct PO'),('ho_operation', 'HO Operation'), ('sub_contract', 'Sub Contracting'), ('inter_state','Inter State'), ('intra_state','Intra State'), ('others', 'Others')],
        string='SO Type', required=True, tracking=True)
    dummy_so_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'),
         ('others', 'Others')], string='Dummy SO Type', compute='_compute_nhcl_so_type')
    barcode_scanned = fields.Char(string="Scan Barcode")
    picking_document = fields.Many2one('stock.picking', string="Document", copy=False)
    operation_type = fields.Selection([('scan','Scan'), ('import','Import'), ('document','Document')], string="Operation Type", tracking=True, copy=False, default='scan')
    transpoter_id = fields.Many2one('dev.transport.details',string='Transport by')
    disco = fields.Float('disc')
    entered_qty = fields.Float(string='Lot Qty', copy=False)
    stock_type = fields.Selection([('regular', 'Regular'), ('damage', 'Damage'), ('return', 'Return'),
                                   ('damage_main', 'Damage-Main'), ('main_damage', 'Main-Damage'),
                                   ('return_main', 'Return-Main')], string='Type', tracking=True)

    nhcl_sale_type = fields.Selection([('store', 'With Indent'), ('regular', 'Without Indent')])
    sale_indent_details_ids = fields.One2many('store.indent.refernce', 'so_order_id', string="product")
    nhcl_indent_id = fields.Many2one("purchase.order",
                                     domain="[('state', '=', 'draft'), ('company_id', '=', mapped_company_id)]")
    mapped_company_id = fields.Many2one(
        'res.company', compute='_compute_mapped_company', store=False
    )
    detail_visible = fields.Boolean(default=True, compute="_compute_visible")
    allow_import_order = fields.Boolean('Allow Import', compute='_compute_import_order_lines')
    nhcl_remarks = fields.Text(string="Remarks")


    def action_open_import_wizard(self):
        """Open wizard to import barcodes for this sale order"""
        self.ensure_one()
        return {
            'name': 'Import Barcodes',
            'type': 'ir.actions.act_window',
            'res_model': 'order.line.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_sale_order_id': self.id,
            },
        }

    @api.model
    def auto_cancel_old_sale_orders(self):
        today = fields.Datetime.now()
        deadline_date = today - timedelta(days=7)

        # Get Bot User (replace login with your bot login)
        bot_user = self.env.ref('base.user_root').id
        if not bot_user:
            return  # or raise error
        SaleOrder = self.env['sale.order'].with_user(bot_user)
        sale_orders = SaleOrder.search([
            ('company_id.nhcl_company_bool', '=', True),
            ('state', 'in', ['sale']),
            ('stock_type', '=', 'regular'),
            ('locked', '=', False),
            ('date_order', '<=', deadline_date),
        ])
        for order in sale_orders:
            pickings_to_cancel = order.picking_ids.filtered(lambda p: p.state not in ['done', 'cancel'])
            for picking in pickings_to_cancel:
                for move in picking.move_ids_without_package:
                    move.state = 'draft'
                    picking.with_user(bot_user).action_cancel()
            order.with_user(bot_user).state = 'cancel'


    def _compute_import_order_lines(self):
        if self.env.user and self.env.user.import_sale_order_line == True:
            self.allow_import_order = True
        else:
            self.allow_import_order = False

    @api.onchange('so_type')
    def _onchange_so_type(self):
        self._compute_import_order_lines()

    @api.depends('nhcl_indent_id', 'sale_indent_details_ids')
    def _compute_visible(self):
        for rec in self:
            if rec.nhcl_indent_id and not rec.sale_indent_details_ids:
                rec.detail_visible = False
            else:
                rec.detail_visible = True

    @api.depends('partner_id')
    def _compute_mapped_company(self):
        for record in self:
            record.mapped_company_id = False
            if record.partner_id:
                company = self.env['res.company'].search([
                    ('partner_id', '=', record.partner_id.id)
                ], limit=1)
                record.mapped_company_id = company

    def load_po_lines(self):
        for rec in self:
            duplicates = self.env['sale.order'].search([
                ('nhcl_indent_id', '=', rec.nhcl_indent_id.id),
                ('id', '!=', rec.id)
            ])
            if duplicates:
                other_order = duplicates[0]  # Just show the first conflicting one
                raise ValidationError(_(
                    "This indent is already assigned to another Sale Order: %s (Customer: %s)"
                ) % (other_order.name, other_order.partner_id.name))
            if rec.nhcl_indent_id.state != 'draft':
                return
            rec.sale_indent_details_ids.unlink()
            domain = [
                ('order_id.nhcl_po_type', 'in', ['inter_state', 'intra_state']),
                ('company_id.nhcl_company_bool', '=', False),
                ('order_id','=',rec.nhcl_indent_id.id)
            ]
            purchase_order_lines = self.env['purchase.order.line'].sudo().search(domain)
            line_commands = []
            summary_dict = defaultdict(float)
            for line in purchase_order_lines:
                line_commands.append((0, 0, {
                    'po_line_id': line.id,
                    'so_order_id': rec.id,
                }))
                summary_dict[line.product_id] += line.product_qty

            rec.sale_indent_details_ids = line_commands
            return



    @api.onchange('partner_id', 'order_line')
    def trigger_the_compute_tax_id(self):
        for rec in self:
            rec.order_line._compute_tax_id()
            rec.get_so_type()

    def get_so_type(self):
        if self.partner_id and self.env.company.state_id:
            if self.partner_id.state_id.id == self.env.company.state_id.id:
                self.so_type = 'intra_state'
            else:
                self.so_type = 'inter_state'
        else:
            self.so_type = ''

    def button_to_reset_discount(self):
        discount_product_line = self.order_line.filtered(lambda x: x.product_id.name == 'Discount')
        if discount_product_line:
            self.disco = 0
            self.order_line._compute_tax_id()
            discount_product_line.unlink()


    def nhcl_active_company_partner(self):
        for rec in self:
            allowed_company_ids = self.env.context.get('allowed_company_ids', [])
            if rec.partner_id and allowed_company_ids and self.env.user.id != 1:
                company_exists = self.env['res.company'].sudo().search([('id', 'in', allowed_company_ids),
                    ('partner_id', '=', rec.partner_id.id)])
                if not company_exists:
                    raise ValidationError(_("Please enable the related company '%s'.") % rec.partner_id.name)

    def action_confirm(self):
        for order in self:
            order.nhcl_active_company_partner()
            if not order.order_line:
                raise ValidationError("You can’t confirm an empty quotation. Please add some products to move before proceeding.")

            if order.nhcl_sale_type == 'store' and order.sale_indent_details_ids:

                # Map the products and their quantities in the sale order lines
                product_qty_map = defaultdict(float)
                for line in order.order_line:
                    product_qty_map[line.product_id.id] += line.product_uom_qty

                # Map the products and allocated quantities in the indent
                allocated_map = {
                    detail.product_id.id: detail.allocated_quantity
                    for detail in order.sale_indent_details_ids
                }

                # Combined loop to check both conditions: missing products and quantity mismatch
                for product_id in set(product_qty_map.keys()).union(set(allocated_map.keys())):
                    ordered_qty = product_qty_map.get(product_id, 0.0)
                    allocated_qty = allocated_map.get(product_id, 0.0)

                    # Check if the product is in the indent but not in the order lines
                    if allocated_qty > 0 and ordered_qty == 0:
                        product_name = self.env['product.product'].browse(product_id).display_name
                        raise ValidationError(
                            _("Product '%s' is allocated in the indent but missing in the Sale Order lines. Please add it.")
                            % product_name
                        )

                    # Check if the product is in the order lines but not in the indent
                    if ordered_qty > 0 and allocated_qty == 0:
                        product_name = self.env['product.product'].browse(product_id).display_name
                        raise ValidationError(
                            _("Product '%s' is in the Sale Order lines but not allocated in the indent. Please remove it.")
                            % product_name
                        )

                    # Check if the ordered quantity matches the allocated quantity
                    if ordered_qty != allocated_qty:
                        product_name = self.env['product.product'].browse(product_id).display_name
                        raise ValidationError(
                            _("Ordered quantity for product '%s' (%s) does not match the allocated quantity (%s). Please correct it.")
                            % (product_name, ordered_qty, allocated_qty)
                        )

                # Cancel the indent after successful validation
                order.nhcl_indent_id.write({'state': 'cancel'})

        return super(SaleOrder, self).action_confirm()

    # def get_picking_lines(self):
    #     self.ensure_one()
    #
    #     # Step 1: Validate picking document usage BEFORE deleting lines
    #     existing_order = self.env['sale.order'].sudo().search(
    #         [
    #             ('picking_document', '=', self.picking_document.id),
    #             ('id', '!=', self.id),
    #             ('operation_type', '=', 'document'),
    #             ('company_id.nhcl_company_bool', '=', True),
    #         ],
    #         limit=1
    #     )
    #     if existing_order:
    #         raise ValidationError(
    #             _("Picking document '%s' is already linked with Sale Order '%s'.")
    #             % (self.picking_document.name, existing_order.name)
    #         )
    #     # Step 2: Fetch picking directly via relational field
    #     picking = self.env['stock.picking'].sudo().search([
    #         ('id', '=', self.picking_document.id),
    #         ('company_id.nhcl_company_bool', '=', True),
    #     ], limit=1)
    #     if not picking:
    #         raise ValidationError(_("No matching Picking Document found."))
    #     # Step 4: Remove existing lines only after validation and gathering info
    #     self.order_line.unlink()
    #     new_lines = []
    #     for ml in picking.move_line_ids_without_package:
    #         lot = ml.lot_id
    #
    #         if not ml.product_id:
    #             raise ValidationError(_("Product missing in picking '%s'.") % picking.name)
    #
    #         if not lot or not lot.product_qty > 0:
    #             continue
    #         branded_vals = list(set(lot.mapped('ref') or []))
    #         branded_barcode_value = ', '.join(branded_vals) or ml.product_id.barcode
    #
    #         new_lines.append({
    #             'order_id': self.id,
    #             'product_id': ml.product_id.id,
    #             'family_id': ml.product_id.categ_id.parent_id.parent_id.parent_id.id,
    #             'category_id': ml.product_id.categ_id.parent_id.parent_id.id,
    #             'class_id': ml.product_id.categ_id.parent_id.id,
    #             'brick_id': ml.product_id.categ_id.id,
    #             'lot_ids': [(6, 0, lot.ids)],
    #             'branded_barcode': branded_barcode_value,
    #             'type_product': ml.type_product,
    #             'product_uom_qty': ml.quantity,
    #             'price_unit': lot.cost_price,
    #             'sale_serial_type': lot.serial_type,
    #         })
    #
    #         lot.is_uploaded = True
    #
    #     # Step 6: Bulk create to reduce overhead
    #     if new_lines:
    #         self.env['sale.order.line'].create(new_lines)

    def get_picking_lines(self):
        self.ensure_one()

        # Step 1: Validate picking document usage BEFORE deleting lines
        existing_order = self.env['sale.order'].sudo().search(
            [
                ('picking_document', '=', self.picking_document.id),
                ('id', '!=', self.id),
                ('operation_type', '=', 'document'),
                ('company_id.nhcl_company_bool', '=', True),
            ],
            limit=1
        )
        if existing_order:
            raise ValidationError(
                _("Picking document '%s' is already linked with Sale Order '%s'.")
                % (self.picking_document.name, existing_order.name)
            )
        # Step 2: Fetch Picking
        picking = self.env['stock.picking'].sudo().search([
            ('id', '=', self.picking_document.id),
            ('company_id.nhcl_company_bool', '=', True),
        ], limit=1)
        if not picking:
            raise ValidationError(_("No matching Picking Document found."))
        # Step 3: Preload used lot + serial type combinations from OTHER sale orders
        used_combinations = set()
        used_lines = self.env['sale.order.line'].sudo().search([
            ('order_id', '!=', self.id),
            ('lot_ids', '!=', False),
            ('sale_serial_type', '!=', False),
            ('company_id.nhcl_company_bool', '=', True),
        ])
        for line in used_lines:
            for used_lot in line.lot_ids:
                used_combinations.add((used_lot.id, line.sale_serial_type))
        # Step 4: Remove existing lines
        self.order_line.unlink()
        # Step 5: Prepare new order lines
        new_lines = []
        for ml in picking.move_line_ids_without_package:
            lot = ml.lot_id
            if not lot or not lot.product_qty > 0:
                continue
            # Duplicate validation: skip if used elsewhere
            serial_type = lot.serial_type
            if (lot.id, serial_type) in used_combinations:
                continue
            branded_vals = list(set(lot.mapped('ref') or []))
            branded_barcode_value = ', '.join(branded_vals) or ml.product_id.barcode
            new_lines.append({
                'order_id': self.id,
                'product_id': ml.product_id.id,
                'family_id': ml.product_id.categ_id.parent_id.parent_id.parent_id.id,
                'category_id': ml.product_id.categ_id.parent_id.parent_id.id,
                'class_id': ml.product_id.categ_id.parent_id.id,
                'brick_id': ml.product_id.categ_id.id,
                'lot_ids': [(6, 0, lot.ids)],
                'branded_barcode': branded_barcode_value,
                'type_product': ml.type_product,
                'product_uom_qty': lot.product_qty,
                'price_unit': lot.cost_price,
                'sale_serial_type': serial_type,
            })
            lot.is_uploaded = True
        # Step 6: Bulk create
        if new_lines:
            self.env['sale.order.line'].create(new_lines)


    def _get_serial_available_qty(self, lot, location, product):
        StockMoveLine = self.env['stock.move.line'].sudo()
        SaleLine = self.env['sale.order.line']

        # INWARD qty
        in_qty = sum(StockMoveLine.search([
            ('company_id.nhcl_company_bool', '=', True),
            ('lot_id', '=', lot.id),
            ('location_dest_id.id', '=', location),
            ('state', '=', 'done'),
        ]).mapped('quantity'))
        # OUTWARD qty (delivery / sale / consumption)
        out_qty = sum(StockMoveLine.search([
            ('company_id.nhcl_company_bool', '=', True),
            ('lot_id', '=', lot.id),
            ('location_id.id', '=', location), ('picking_id.stock_picking_type', '=', 'goods_return')
        ]).mapped('quantity'))
        sold_qty = sum(SaleLine.search([
            ('lot_ids', 'in', lot.id),
            ('company_id.nhcl_company_bool', '=', True),
            ('order_id.state', 'not in', ['cancel']),
            ('order_id.stock_type', '=', 'regular'),
        ]).mapped('product_uom_qty'))

        # Used in current order (avoid duplicate scan)
        current_qty = sum(self.order_line.filtered(
            lambda l: l.product_id.id == product.id and lot.name in l.lot_ids.mapped('name')
        ).mapped('product_uom_qty'))
        return in_qty - out_qty - sold_qty - current_qty

    @api.onchange('barcode_scanned')
    def _onchange_barcode_scanned(self):
        if not self.so_type:
            if self.barcode_scanned:
                raise ValidationError('Please choose a So Type before scanning a barcode.')
            return

        if not self.barcode_scanned:
            return

        barcode = self.barcode_scanned
        gs1_pattern = r'01(\d{14})21([A-Za-z0-9]+)'
        ean13_pattern = r'(\d{13})'
        custom_serial_pattern = r'^(R\d+)'

        def search_product(barcode_field, barcode_value):
            product = self.env['product.product'].search([(barcode_field, '=', barcode_value)], limit=1)
            if not product:
                template = self.env['product.template'].search([(barcode_field, '=', barcode_value)], limit=1)
                if template:
                    product = template.product_variant_id
            return product

        # ------------------------------------------
        # GS1 BARCODE
        # ------------------------------------------
        if re.match(gs1_pattern, barcode):
            product_barcode, scanned_number = re.match(gs1_pattern, barcode).groups()
            product = search_product('barcode', product_barcode)

            if not product:
                raise ValidationError(f"No product found with barcode {product_barcode}.")

            if product.tracking not in ('serial', 'lot'):
                raise ValidationError(f'Product {product.display_name} must have serial or lot tracking.')

            location = self.env.ref('stock.stock_location_stock').id

            lots = self.env['stock.quant'].search([
                ('product_id', '=', product.id),
                ('quantity', '>', 0),
                ('location_id.id', '=', location),
                ('lot_id.name', '=', scanned_number),
                ('lot_id.type_product', '=', 'un_brand'),
                ('company_id', '=', self.company_id.id)
            ], limit=1)
            lot = lots.lot_id
            if not lot:
                raise ValidationError(f'No lot/serial number found for {scanned_number}.')
            if lot.rs_price <= 0.0:
                raise ValidationError("You are not allowed to add serials not done with landed cost.")
            landed_cost = lot.picking_id.has_landed_cost_status
            if not landed_cost and lot.picking_id.is_landed_cost == 'yes':
                raise ValidationError(f"You are not allowed to add {lot.name} serial not done with landed cost.")
            for lot in lots.lot_id:
                product = lot.product_id
                if product.tracking not in ['serial', 'lot']:
                    raise ValidationError(f"Product has {product.name} no tracking.")
                if lot.rs_price <= 0.0:
                    raise ValidationError(f"You are not allowed to add {lot.name} serial not done with landed cost.")
                landed_cost = lot.picking_id.has_landed_cost_status
                if not landed_cost and lot.picking_id.is_landed_cost == 'yes':
                    raise ValidationError(f"You are not allowed to add {lot.name} serial not done with landed cost.")
                if product.tracking == 'serial':
                    if self.entered_qty > 1:
                        raise ValidationError("Serial product: Qty must be 1.")
                    if lot.name in self.order_line.mapped('lot_ids.name'):
                        raise ValidationError(f"Serial {lot.name} already used in this order.")
                    in_serial_qty = self.env['stock.move.line'].sudo().search([
                        ('company_id.nhcl_company_bool', '=', True),
                        ('lot_id', '=', lot.id),
                        ('location_dest_id.id', '=', location)
                    ]).mapped('quantity')
                    out_serial_qty = self.env['stock.move.line'].sudo().search([
                        ('company_id.nhcl_company_bool', '=', True),
                        ('lot_id', '=', lot.id), ('picking_id.stock_picking_type', '=', 'goods_return')
                    ]).mapped('quantity')
                    existing_so_line = self.env['sale.order.line'].search([
                        ('lot_ids', 'in', lot.id), ('company_id.nhcl_company_bool', '=', True),
                        ('order_id.state', 'not in', ['cancel']), ('order_id.stock_type', '=', 'regular'),
                    ]).mapped('product_uom_qty')
                    self.order_line = [(0, 0, {
                        'product_id': product.id,
                        'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                        'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
                        'class_id': lot.product_id.categ_id.parent_id.id,
                        'brick_id': lot.product_id.categ_id.id,
                        'product_uom_qty': lot.product_qty,
                        'lot_ids': [(4, lot.id)],
                        'branded_barcode': lot.ref,
                        'type_product': lot.type_product,
                        'price_unit': lot.cost_price,
                        'sale_serial_type': lot.serial_type,
                    })]
                    current_serial_order_qty = sum(self.order_line.filtered(
                        lambda l: l.product_id.id == product.id and l.lot_ids.name == scanned_number).mapped(
                        'product_uom_qty'))
                    used_serial_qty = (existing_so_line + out_serial_qty + current_serial_order_qty)
                    if in_serial_qty < used_serial_qty:
                        raise ValidationError(f"Serial {lot.name} is not available to sale.")
                elif product.tracking == 'lot':
                    if lot.rs_price <= 0.0:
                        raise ValidationError(
                            f"You are not allowed to add {lot.name} lot not done with landed cost.")
                    landed_cost = lot.picking_id.has_landed_cost_status
                    if not landed_cost and lot.picking_id.is_landed_cost == 'yes':
                        raise ValidationError(
                            f"You are not allowed to add {lot.name} serial not done with landed cost.")
                    if not self.entered_qty or self.entered_qty <= 0:
                        raise ValidationError("Enter a valid quantity for lot tracked product.")
                    in_lot_qty = sum(self.env['stock.move.line'].sudo().search([
                        ('company_id.nhcl_company_bool', '=', True),
                        ('lot_id', '=', lot.id),
                        ('location_dest_id.id', '=', location)
                    ]).mapped('quantity'))
                    out_lot_qty = sum(self.env['stock.move.line'].sudo().search([
                        ('company_id.nhcl_company_bool', '=', True),
                        ('lot_id', '=', lot.id), ('picking_id.stock_picking_type', '=', 'goods_return')
                    ]).mapped('quantity'))
                    existing_so_line = sum(self.env['sale.order.line'].search([
                        ('lot_ids', 'in', lot.id), ('company_id.nhcl_company_bool', '=', True),
                        ('order_id.state', 'not in', ['cancel']), ('order_id.stock_type', '=', 'regular'),
                    ]).mapped('product_uom_qty'))
                    existing_sale_line = self.order_line.filtered(lambda x: x.lot_ids.name == scanned_number)
                    if existing_sale_line:
                        existing_sale_line.product_uom_qty += self.entered_qty
                        existing_sale_line.price_unit = lot.cost_price
                    else:
                        self.order_line = [(0, 0, {
                            'product_id': product.id,
                            'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                            'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
                            'class_id': lot.product_id.categ_id.parent_id.id,
                            'brick_id': lot.product_id.categ_id.id,
                            'product_uom_qty': self.entered_qty,
                            'lot_ids': [(4, lot.id)],
                            'branded_barcode': lot.ref,
                            'type_product': lot.type_product,
                            'price_unit': lot.cost_price,
                            'sale_serial_type': lot.serial_type,
                        })]
                    current_order_qty = sum(self.order_line.filtered(
                        lambda l: l.product_id.id == product.id and l.lot_ids.name == scanned_number).mapped(
                        'product_uom_qty'))
                    used_serial_qty = (existing_so_line + out_lot_qty + current_order_qty)
                    if in_lot_qty < used_serial_qty:
                        raise ValidationError(f"Lot {lot.name} is not available to sale.")
                    if (in_lot_qty - used_serial_qty) < 0:
                        raise ValidationError(f"Lot {lot.name} is not enough qty to sale.")
        # ------------------------------------------
        # EAN 13 BARCODE
        # ------------------------------------------
        elif re.match(ean13_pattern, barcode):
            ean13_barcode = re.match(ean13_pattern, barcode).group(1)
            location = self.env.ref('stock.stock_location_stock').id
            # 🔹 Find all serial quants linked to EAN-13
            quants = self.env['stock.quant'].search([
                ('lot_id.ref', '=', ean13_barcode),
                ('location_id.id', '=', location),
                ('quantity', '>', 0),
                ('lot_id.type_product', '=', 'brand'),
                ('company_id', '=', self.company_id.id)
            ], order='id asc')
            if not quants:
                raise ValidationError(f"No serials found for EAN-13 barcode {ean13_barcode}")
            product = quants[0].product_id
            entered_qty = self.entered_qty or 0
            if product.tracking == 'serial':
                remaining_qty = 1
                new_lines = []
                for quant in quants:
                    if remaining_qty <= 0:
                        break
                    lot = quant.lot_id
                    # 🔸 Skip already added serials
                    if lot in self.order_line.mapped('lot_ids.name'):
                        continue
                    # 🔸 Check serial availability
                    available_qty = self._get_serial_available_qty(
                        lot=lot,
                        location=location,
                        product=product
                    )
                    # 🔸 If exhausted, move to next serial
                    if available_qty <= 0:
                        continue
                    landed_cost = lot.picking_id.has_landed_cost_status
                    if not landed_cost and lot.picking_id.is_landed_cost == 'yes':
                        raise ValidationError(
                            f"You are not allowed to add {lot.name} serial not done with landed cost.")
                    # 🔹 Add serial to sale order
                    new_lines.append((0, 0, {
                        'product_id': product.id,
                        'family_id': product.categ_id.parent_id.parent_id.parent_id.id,
                        'category_id': product.categ_id.parent_id.parent_id.id,
                        'class_id': product.categ_id.parent_id.id,
                        'brick_id': product.categ_id.id,
                        'product_uom_qty': 1,
                        'lot_ids': [(4, lot.id)],
                        'branded_barcode': lot.ref,
                        'type_product': lot.type_product,
                        'price_unit': lot.cost_price,
                        'sale_serial_type': lot.serial_type,
                    }))
                    remaining_qty -= 1
                # 🔹 Not enough serials available
                if remaining_qty > 0:
                    raise ValidationError(
                        f"Requested {entered_qty} serials but only "
                        f"{entered_qty - remaining_qty} available for EAN-13 {ean13_barcode}"
                    )
                self.order_line = new_lines
            elif product.tracking == 'lot':
                remaining_qty = entered_qty
                new_lines = []

                for quant in quants:
                    if remaining_qty <= 0:
                        break

                    lot = quant.lot_id

                    # 🔸 Check available qty for this lot
                    available_qty = self._get_serial_available_qty(
                        lot=lot,
                        location=location,
                        product=product
                    )

                    if available_qty <= 0:
                        continue

                    # 🔸 Allocate as much as possible from this lot
                    allocate_qty = min(remaining_qty, available_qty)

                    # 🔸 Check if this lot already exists in order line
                    existing_line = self.order_line.filtered(
                        lambda l: (
                                l.product_id.id == product.id and
                                lot.name in l.lot_ids.mapped('name')
                        )
                    )
                    if existing_line:
                        # 🔹 Increase qty in same line
                        existing_line.product_uom_qty += allocate_qty
                        existing_line.price_unit += lot.cost_price
                    else:
                        landed_cost = lot.picking_id.has_landed_cost_status
                        if not landed_cost and lot.picking_id.is_landed_cost == 'yes':
                            raise ValidationError(
                                f"You are not allowed to add {lot.name} serial not done with landed cost.")
                        # 🔹 Create new line
                        new_lines.append((0, 0, {
                            'product_id': product.id,
                            'family_id': product.categ_id.parent_id.parent_id.parent_id.id,
                            'category_id': product.categ_id.parent_id.parent_id.id,
                            'class_id': product.categ_id.parent_id.id,
                            'brick_id': product.categ_id.id,
                            'product_uom_qty': allocate_qty,
                            'lot_ids': [(4, lot.id)],
                            'branded_barcode': lot.ref,
                            'type_product': lot.type_product,
                            'price_unit': lot.cost_price,
                            'sale_serial_type': lot.serial_type,
                        }))
                    remaining_qty -= allocate_qty
                if remaining_qty > 0:
                    raise ValidationError(
                        f"Requested {entered_qty} qty but only "
                        f"{entered_qty - remaining_qty} available for EAN-13 {ean13_barcode}"
                    )
                self.order_line = new_lines
        # ------------------------------------------
        # CUSTOM SERIAL BARCODE
        # ------------------------------------------
        elif re.match(custom_serial_pattern, barcode):
            prefix = re.match(custom_serial_pattern, barcode).group(1)
            location = self.env.ref('stock.stock_location_stock').id
            Quant = self.env['stock.quant']

            # ------------------------------------------
            # STEP 1: SEARCH UNBRAND SERIAL (KEEP SAME)
            # ------------------------------------------
            lots = Quant.search([
                ('quantity', '>', 0),
                ('company_id', '=', self.company_id.id),
                ('location_id', '=', location),
                ('lot_id.name', '=', prefix),
                ('lot_id.type_product', '=', 'un_brand')
            ])

            # ------------------------------------------
            # STEP 2: SEARCH BRAND SERIAL (FALLBACK)
            # ------------------------------------------
            if not lots:
                lots = Quant.search([
                    ('quantity', '>', 0),
                    ('company_id', '=', self.company_id.id),
                    ('location_id', '=', location),
                    ('lot_id.ref', '=', prefix),
                    ('lot_id.type_product', '=', 'brand')
                ])

            if not lots:
                raise ValidationError(f"No lots found for custom barcode {prefix}")

            # ------------------------------------------
            # STEP 3: UNBRAND LOGIC (AS-IS)
            # ------------------------------------------
            if lots[0].lot_id.type_product == 'un_brand':
                for lot in lots.lot_id:
                    product = lot.product_id

                    if product.tracking not in ['serial', 'lot']:
                        raise ValidationError(f"Product has {product.name} no tracking.")

                    landed_cost = lot.picking_id.has_landed_cost_status
                    if not landed_cost and lot.picking_id.is_landed_cost == 'yes':
                        raise ValidationError(
                            f"You are not allowed to add {lot.name} serial not done with landed cost."
                        )

                    # ---------------- SERIAL ----------------
                    if product.tracking == 'serial':
                        if self.entered_qty > 1:
                            raise ValidationError("Serial product: Qty must be 1.")

                        if lot.name in self.order_line.mapped('lot_ids.name'):
                            raise ValidationError(f"Serial {lot.name} already used in this order.")

                        in_serial_qty = sum(self.env['stock.move.line'].sudo().search([
                            ('company_id.nhcl_company_bool', '=', True),
                            ('lot_id', '=', lot.id),
                            ('location_dest_id.id', '=', location)
                        ]).mapped('quantity'))

                        out_serial_qty = sum(self.env['stock.move.line'].sudo().search([
                            ('company_id.nhcl_company_bool', '=', True),
                            ('lot_id', '=', lot.id),
                            ('picking_id.stock_picking_type', '=', 'goods_return')
                        ]).mapped('quantity'))

                        existing_so_qty = sum(self.env['sale.order.line'].search([
                            ('lot_ids', 'in', lot.id),
                            ('company_id.nhcl_company_bool', '=', True),
                            ('order_id.state', 'not in', ['cancel']),
                            ('order_id.stock_type', '=', 'regular'),
                        ]).mapped('product_uom_qty'))

                        self.order_line = [(0, 0, {
                            'product_id': product.id,
                            'family_id': product.categ_id.parent_id.parent_id.parent_id.id,
                            'category_id': product.categ_id.parent_id.parent_id.id,
                            'class_id': product.categ_id.parent_id.id,
                            'brick_id': product.categ_id.id,
                            'product_uom_qty': 1,
                            'lot_ids': [(4, lot.id)],
                            'branded_barcode': lot.ref,
                            'type_product': lot.type_product,
                            'price_unit': lot.cost_price,
                            'sale_serial_type': lot.serial_type,
                        })]

                        if in_serial_qty < (existing_so_qty + out_serial_qty + 1):
                            raise ValidationError(f"Serial {lot.name} is not available to sale.")

                    # ---------------- LOT ----------------
                    else:
                        if not self.entered_qty or self.entered_qty <= 0:
                            raise ValidationError("Enter a valid quantity for lot tracked product.")

                        in_lot_qty = sum(self.env['stock.move.line'].sudo().search([
                            ('company_id.nhcl_company_bool', '=', True),
                            ('lot_id', '=', lot.id),
                            ('location_dest_id.id', '=', location)
                        ]).mapped('quantity'))

                        out_lot_qty = sum(self.env['stock.move.line'].sudo().search([
                            ('company_id.nhcl_company_bool', '=', True),
                            ('lot_id', '=', lot.id),
                            ('picking_id.stock_picking_type', '=', 'goods_return')
                        ]).mapped('quantity'))

                        existing_so_qty = sum(self.env['sale.order.line'].search([
                            ('lot_ids', 'in', lot.id),
                            ('company_id.nhcl_company_bool', '=', True),
                            ('order_id.state', 'not in', ['cancel']),
                            ('order_id.stock_type', '=', 'regular'),
                        ]).mapped('product_uom_qty'))

                        existing_line = self.order_line.filtered(
                            lambda l: lot.name in l.lot_ids.mapped('name')
                        )

                        if existing_line:
                            existing_line.product_uom_qty += self.entered_qty
                            existing_line.price_unit = lot.cost_price
                        else:
                            self.order_line = [(0, 0, {
                                'product_id': product.id,
                                'family_id': product.categ_id.parent_id.parent_id.parent_id.id,
                                'category_id': product.categ_id.parent_id.parent_id.id,
                                'class_id': product.categ_id.parent_id.id,
                                'brick_id': product.categ_id.id,
                                'product_uom_qty': self.entered_qty,
                                'lot_ids': [(4, lot.id)],
                                'branded_barcode': lot.ref,
                                'type_product': lot.type_product,
                                'price_unit': lot.cost_price,
                                'sale_serial_type': lot.serial_type,
                            })]

                        if in_lot_qty < (existing_so_qty + out_lot_qty + self.entered_qty):
                            raise ValidationError(f"Lot {lot.name} is not enough qty to sale.")

            # ------------------------------------------
            # STEP 4: BRAND LOGIC (FIXED)
            # ------------------------------------------
            else:
                location = self.env.ref('stock.stock_location_stock').id
                StockMoveLine = self.env['stock.move.line']
                SaleLine = self.env['sale.order.line']

                used_lot_ids = self.order_line.mapped('lot_ids').ids

                selected_quant = None
                available_qty = 0

                # ------------------------------------------
                # STEP 1: FIND NEXT AVAILABLE LOT / SERIAL
                # ------------------------------------------
                for quant in lots.sorted(key=lambda q: q.id):  # FIFO
                    lot = quant.lot_id
                    product = lot.product_id

                    # -------------------------------
                    # SERIAL LOGIC
                    # -------------------------------
                    if product.tracking == 'serial':
                        if lot.id in used_lot_ids:
                            continue

                        # IN
                        in_qty = sum(StockMoveLine.sudo().search([
                            ('company_id.nhcl_company_bool', '=', True),
                            ('lot_id', '=', lot.id),
                            ('location_dest_id.id', '=', location)
                        ]).mapped('quantity'))

                        # OUT
                        out_qty = sum(StockMoveLine.sudo().search([
                            ('company_id.nhcl_company_bool', '=', True),
                            ('lot_id', '=', lot.id),
                            ('picking_id.stock_picking_type', '=', 'goods_return')
                        ]).mapped('quantity'))

                        # SOLD
                        sold_qty = sum(SaleLine.search([
                            ('lot_ids', 'in', lot.id),
                            ('company_id.nhcl_company_bool', '=', True),
                            ('order_id.state', 'not in', ['cancel']),
                            ('order_id.stock_type', '=', 'regular'),
                        ]).mapped('product_uom_qty'))

                        if (in_qty - out_qty - sold_qty) > 0:
                            selected_quant = quant
                            available_qty = 1
                            break

                    # -------------------------------
                    # LOT LOGIC
                    # -------------------------------
                    elif product.tracking == 'lot':
                        if not self.entered_qty or self.entered_qty <= 0:
                            raise ValidationError("Enter a valid quantity for lot tracked product.")

                        requested_qty = self.entered_qty

                        # IN
                        in_qty = sum(StockMoveLine.sudo().search([
                            ('company_id.nhcl_company_bool', '=', True),
                            ('lot_id', '=', lot.id),
                            ('location_dest_id.id', '=', location)
                        ]).mapped('quantity'))

                        # OUT
                        out_qty = sum(StockMoveLine.sudo().search([
                            ('company_id.nhcl_company_bool', '=', True),
                            ('lot_id', '=', lot.id),
                            ('picking_id.stock_picking_type', '=', 'goods_return')
                        ]).mapped('quantity'))

                        # SOLD
                        sold_qty = sum(SaleLine.search([
                            ('lot_ids', 'in', lot.id),
                            ('company_id.nhcl_company_bool', '=', True),
                            ('order_id.state', 'not in', ['cancel']),
                            ('order_id.stock_type', '=', 'regular'),
                        ]).mapped('product_uom_qty'))

                        # CURRENT ORDER
                        current_qty = sum(self.order_line.filtered(
                            lambda l: lot.id in l.lot_ids.ids
                        ).mapped('product_uom_qty'))

                        remaining_qty = in_qty - out_qty - sold_qty - current_qty

                        if remaining_qty > 0:
                            selected_quant = quant
                            available_qty = remaining_qty
                            break

                    else:
                        continue

                if not selected_quant:
                    raise ValidationError(f"No available stock for barcode {prefix}")

                # ------------------------------------------
                # STEP 2: LANDED COST VALIDATION
                # ------------------------------------------
                lot = selected_quant.lot_id
                product = lot.product_id

                landed_cost = lot.picking_id.has_landed_cost_status
                if not landed_cost and lot.picking_id.is_landed_cost == 'yes':
                    raise ValidationError(
                        f"You are not allowed to add {lot.name} not done with landed cost."
                    )

                # ------------------------------------------
                # STEP 3: CREATE / UPDATE SALE LINE
                # ------------------------------------------
                if product.tracking == 'serial':
                    # SERIAL → ONE PER SCAN
                    self.order_line = [(0, 0, {
                        'product_id': product.id,
                        'family_id': product.categ_id.parent_id.parent_id.parent_id.id,
                        'category_id': product.categ_id.parent_id.parent_id.id,
                        'class_id': product.categ_id.parent_id.id,
                        'brick_id': product.categ_id.id,
                        'product_uom_qty': 1,
                        'lot_ids': [(6, 0, [lot.id])],
                        'branded_barcode': lot.ref,
                        'type_product': lot.type_product,
                        'price_unit': lot.cost_price,
                        'sale_serial_type': lot.serial_type,
                    })]

                else:
                    # LOT → QTY BASED
                    allocate_qty = min(self.entered_qty, available_qty)

                    existing_line = self.order_line.filtered(
                        lambda l: lot.id in l.lot_ids.ids
                    )

                    if existing_line:
                        existing_line.product_uom_qty += allocate_qty
                        existing_line.price_unit = lot.cost_price
                    else:
                        self.order_line = [(0, 0, {
                            'product_id': product.id,
                            'family_id': product.categ_id.parent_id.parent_id.parent_id.id,
                            'category_id': product.categ_id.parent_id.parent_id.id,
                            'class_id': product.categ_id.parent_id.id,
                            'brick_id': product.categ_id.id,
                            'product_uom_qty': allocate_qty,
                            'lot_ids': [(6, 0, [lot.id])],
                            'branded_barcode': lot.ref,
                            'type_product': lot.type_product,
                            'price_unit': lot.cost_price,
                            'sale_serial_type': lot.serial_type,
                        })]

                    if allocate_qty < self.entered_qty:
                        raise ValidationError(
                            f"Only {allocate_qty} qty available in lot {lot.name}, "
                            f"requested {self.entered_qty}"
                        )
        else:
            raise ValidationError('Invalid barcode format.')
        self.barcode_scanned = False
        self.entered_qty = False


    # Removing sale order lines
    def reset_product_lines(self):
        self.picking_document = False
        for rec in self.order_line:
            for lot in rec.lot_ids:
                lot.is_uploaded = False
            rec.unlink()
                


    @api.depends('so_type')
    def _compute_nhcl_so_type(self):
        if self.so_type == 'ho_operation':
            self.dummy_so_type = 'ho_operation'
        elif self.so_type == 'advertisement':
            self.dummy_so_type = 'advertisement'
        elif self.so_type == 'others':
            self.dummy_so_type = 'others'
        elif self.so_type == 'inter_state':
            self.dummy_so_type = 'ho_operation'
        elif self.so_type == 'intra_state':
            self.dummy_so_type = 'ho_operation'
        elif self.so_type == 'sub_contract':
            self.dummy_so_type = 'ho_operation'
        elif self.so_type == 'direct_po':
            self.dummy_so_type = 'ho_operation'
        else:
            self.dummy_so_type = ''

    def inter_company_create_purchase_order(self, company):
        """ Create a Purchase Order from the current SO (self)
            Note : In this method, reading the current SO is done as sudo, and the creation of the derived
            PO as intercompany_user, minimizing the access right required for the trigger user
            :param company : the company of the created PO
            :rtype company : res.company record
        """
        for rec in self:
            if not company or not rec.company_id.partner_id:
                continue

            # find user for creating and validating SO/PO from company
            intercompany_uid = company.intercompany_user_id and company.intercompany_user_id.id or False
            if not intercompany_uid:
                raise ValidationError(_('Provide one user for intercompany relationships for %(name)s '), name=company.name)
            # check intercompany user access rights
            if not self.env['purchase.order'].with_user(intercompany_uid).check_access_rights('create',
                                                                                              raise_exception=False):
                raise ValidationError(_("An inter-company user of company%s does not have sufficient access rights", company.name))

            company_partner = rec.company_id.partner_id.with_user(intercompany_uid)
            # create the PO and generate its lines from the SO
            # read it as sudo, because inter-compagny user can not have the access right on PO
            po_vals = rec.sudo()._prepare_purchase_order_data(company, company_partner)
            inter_user = self.env['res.users'].sudo().browse(intercompany_uid)
            for line in rec.order_line.sudo():
                po_vals['order_line'] += [(0, 0, rec._prepare_purchase_order_line_data(line, rec.date_order, company))]
            purchase_order = self.env['purchase.order'].create(po_vals)
            for k in purchase_order.order_line:
                k._compute_tax_id()

            msg = _("Automatically generated from %(origin)s of company %(company)s.", origin=self.name,
                    company=company.name)
            purchase_order.message_post(body=msg)

            # write customer reference field on SO
            if not rec.client_order_ref:
                rec.client_order_ref = purchase_order.name

            # auto-validate the purchase order if needed
            if company.auto_validation:
                purchase_order.with_user(intercompany_uid).button_confirm()


    def _prepare_purchase_order_data(self, company, company_partner):
        """ Generate purchase order values, from the SO (self)
            :param company_partner : the partner representing the company of the SO
            :rtype company_partner : res.partner record
            :param company : the company in which the PO line will be created
            :rtype company : res.company record
        """
        self.ensure_one()
        # find location and warehouse, pick warehouse from company object
        warehouse = company.warehouse_id and company.warehouse_id.company_id.id == company.id and company.warehouse_id or False
        if not warehouse:
            raise UserError(_('Configure correct warehouse for company(%s) from Menu: Settings/Users/Companies', company.name))
        if self.stock_type == 'regular':
            picking_type_id = self.env['stock.picking.type'].search([
                ('code', '=', 'incoming'), ('warehouse_id', '=', warehouse.id)
            ], limit=1)
        else:
            picking_type_id = self.env['stock.picking.type'].search([
                ('stock_picking_type', '=', self.stock_type), ('warehouse_id', '=', warehouse.id)
            ], limit=1)
        if not picking_type_id:
            intercompany_uid = company.intercompany_user_id.id
            picking_type_id = self.env['purchase.order'].with_user(intercompany_uid)._default_picking_type()
        return {
            'name': self.env['ir.sequence'].sudo().next_by_code('purchase.order'),
            'origin': self.name,
            'partner_id': company_partner.id,
            'nhcl_po_type': self.so_type,
            'picking_type_id': picking_type_id.id,
            'date_order': self.date_order,
            'company_id': company.id,
            'fiscal_position_id': self.env['account.fiscal.position']._get_fiscal_position(company_partner).id,
            'payment_term_id': company_partner.property_supplier_payment_term_id.id,
            'auto_generated': True,
            'auto_sale_order_id': self.id,
            'partner_ref': self.name,
            'currency_id': self.currency_id.id,
            'order_line': [],
        }



class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    lot_ids = fields.Many2many('stock.lot', string="Serial Numbers")
    branded_barcode = fields.Char(string="Barcode")
    type_product = fields.Selection([('brand', 'Brand'), ('un_brand', 'UnBrand'), ('others', 'Others')],
                                    string='Brand Type', copy=False)
    sale_serial_type = fields.Selection([('regular', 'Regular'), ('return', 'Returned')],
                                        string='Serial Type', copy=False, tracking=True)
    l10n_in_hsn_code = fields.Char(related='product_id.l10n_in_hsn_code', string='HSN/SAC Code',  store=True, readonly=False)
    date_order = fields.Datetime(
        related="order_id.date_order", readonly=True, store=True, index=True, )
    analytic_account_id = fields.Many2one(related="order_id.analytic_account_id", readonly=True,
                                          store=True, index=True, )
    prod_barcode = fields.Char('Barcode', copy=False)
    family_id = fields.Many2one('product.category', string='Family', copy=False)
    category_id = fields.Many2one('product.category', string='Category', copy=False)
    class_id = fields.Many2one('product.category', string='Class', copy=False)
    brick_id = fields.Many2one('product.category', string='Brick', copy=False)
    s_no = fields.Integer(string="Row No", compute="_compute_s_no")

    @api.depends('order_id')
    def _compute_s_no(self):
        for rec in self.order_id:
            for index, line in enumerate(rec.order_line, start=1):
                line.s_no = index

    @api.model
    def create(self, vals_list):
        res = super(SaleOrderLine, self).create(vals_list)
        if res.lot_ids.is_under_plan == True:
            raise ValidationError(f"This {res.lot_ids.name} Serial/Lot number under Audit plan.")
        return res


    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.order_id and not self.order_id.so_type:
            # Clear the product_id and raise an error if no stock_type is selected
            self.product_id = False
            raise ValidationError(
                "Before you can select a product, you must first select a SO Type."
            )
    def remove_sale_order_line(self):
        for rec in self:
            for lot in rec.lot_ids:
                lot.is_uploaded = False
            rec.unlink()


    # def _action_launch_stock_rule(self, previous_product_uom_qty=False):
    #     """ Override to ensure lot/serial numbers are carried over to stock moves """
    #     moves = super(SaleOrderLine, self)._action_launch_stock_rule(previous_product_uom_qty)
    #     for rec in self:
    #         for move_id in rec.move_ids:
    #             if move_id.product_id.tracking == 'serial':
    #                 lot_ids = self.filtered(lambda x:x.product_id == move_id.product_id).mapped('lot_ids')
    #                 move_id.move_line_ids.lot_id = False
    #                 move_id.lot_ids = [(4, lot.id) for lot in lot_ids]
    #     return moves


    @api.constrains('lot_ids')
    def check_landed_cost_yes(self):
        for lot in self:
            if lot.lot_ids and lot.lot_ids.cost_price < 1.0 or lot.lot_ids.rs_price < 1.0:
                raise ValidationError("You are not allowed to some of the serial numbers are not done landed cost.")

    @api.onchange('price_unit', 'discount')
    def trigger_the_compute_tax_id(self):
        for rec in self:
            rec._compute_tax_id()

    def unlink(self):
        for line in self:
            if line.product_id.name == 'Discount' and line.order_id.disco > 0:
                raise ValidationError(
                    _("You are not allowed to unlink Discount Product; if you want to remove discount, use the Reset Discount Button!."))
        return super(SaleOrderLine, self).unlink()

    @api.depends('product_id', 'company_id', 'price_unit', 'order_id.partner_id', 'discount', 'order_id.so_type')
    def _compute_tax_id(self):
        lines_by_company = defaultdict(lambda: self.env['sale.order.line'])
        cached_taxes = {}
        for line in self:
            # Check if 'so_type' is 'intra_state' and clear taxes
            if line.order_id.so_type == 'intra_state':
                line.tax_id = False
                continue  # Skip tax computation for this line
            lines_by_company[line.company_id] += line
        for company, lines in lines_by_company.items():
            for line in lines.with_company(company):
                taxes = None
                if line.product_id:
                    taxes = line.product_id.taxes_id._filter_taxes_by_company(company)
                    if len(taxes) >= 2:
                        for tax in taxes:
                            if line.discount > 0:
                                if tax.min_amount <= line.price_unit * (
                                        1 - line.discount / 100) <= tax.max_amount:
                                    taxes = tax
                                    break
                            else:
                                if tax.min_amount <= line.price_unit * (
                                        1 - line.order_id.disco / 100) <= tax.max_amount:
                                    taxes = tax
                                    break
                if not line.product_id or not taxes:
                    # Nothing to map
                    line.tax_id = False
                    continue
                fiscal_position = line.order_id.fiscal_position_id
                cache_key = (fiscal_position.id, company.id, tuple(taxes.ids))
                cache_key += line._get_custom_compute_tax_cache_key()
                if cache_key in cached_taxes:
                    result = cached_taxes[cache_key]
                else:
                    result = fiscal_position.map_tax(taxes)
                    cached_taxes[cache_key] = result
                line.tax_id = result


class SaleOrderDiscount(models.TransientModel):
    _inherit = 'sale.order.discount'

    def _create_discount_lines(self):
        """Create SOline(s) according to wizard configuration"""
        self.ensure_one()
        discount_product = self._get_discount_product()

        if self.discount_type == 'amount':
            vals_list = [
                self._prepare_discount_line_values(
                    product=discount_product,
                    amount=self.discount_amount,
                    taxes=self.env['account.tax'],
                )
            ]
        else:  # so_discount
            total_price_per_tax_groups = defaultdict(float)
            for line in self.sale_order_id.order_line:
                if not line.product_uom_qty or not line.price_unit:
                    continue

                total_price_per_tax_groups[line.tax_id] += line.price_total

            if not total_price_per_tax_groups:
                # No valid lines on which the discount can be applied
                return
            elif len(total_price_per_tax_groups) == 1:
                # No taxes, or all lines have the exact same taxes
                taxes = next(iter(total_price_per_tax_groups.keys()))
                subtotal = total_price_per_tax_groups[taxes]
                vals_list = [{
                    **self._prepare_discount_line_values(
                        product=discount_product,
                        amount=subtotal * self.discount_percentage,
                        taxes=taxes,
                        description=_(
                            "Discount: %(percent)s%%",
                            percent=self.discount_percentage * 100
                        ),
                    ),
                }]
            else:
                vals_list = [
                    self._prepare_discount_line_values(
                        product=discount_product,
                        amount=subtotal * self.discount_percentage,
                        taxes=taxes,
                        description=_(
                            "Discount: %(percent)s%%"
                            "- On products with the following taxes %(taxes)s",
                            percent=self.discount_percentage * 100,
                            taxes=", ".join(taxes.mapped('name'))
                        ),
                    ) for taxes, subtotal in total_price_per_tax_groups.items()
                ]
        return self.env['sale.order.line'].create(vals_list)

    def action_apply_discount(self):
        self.ensure_one()
        self = self.with_company(self.company_id)
        if self.discount_type == 'sol_discount':
            self.sale_order_id.order_line.write({'discount': self.discount_percentage * 100})
            self.sale_order_id.order_line._compute_tax_id()
        elif self.discount_type == 'amount':
            raise ValidationError(_("Fixed Amount Discount is not applicable; please change to another discount type!."))
        else:
            self.sale_order_id.write({'disco': self.discount_percentage * 100})
            self.sale_order_id.order_line._compute_tax_id()
            self._create_discount_lines()