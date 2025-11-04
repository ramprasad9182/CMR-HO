from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError
from collections import defaultdict
import re

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
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'), ('sub_contract', 'Sub Contracting'), ('inter_state','Inter State'), ('intra_state','Intra State'), ('others', 'Others')],
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

    def get_picking_lines(self):
        # Gather lot_id + sale_serial_type combinations already used in other sale orders
        used_lots = self.env['sale.order.line'].sudo().search([
            ('order_id', '!=', self.id),
            ('lot_ids', '!=', False),
            ('sale_serial_type', '!=', False)
        ])
        used_combinations = set()
        for line in used_lots:
            for lot in line.lot_ids:
                used_combinations.add((lot.name, line.sale_serial_type))

        self.order_line.unlink()

        existing_order = self.env['sale.order'].sudo().search(
            [('picking_document', '=', self.picking_document.id), ('id', '!=', self.id)], limit=1)
        if existing_order:
            raise ValidationError(
                f"This picking document '{self.picking_document.name}' is already used in Sale Order '{existing_order.name}'.")

        picking = self.env['stock.picking'].sudo().search([('name', '=', self.picking_document.name)])

        for line in picking.move_line_ids_without_package:
            if not line.product_id:
                raise ValidationError(f"No Products Found in '{picking.name}'.")

            if not line.lot_id:
                continue
            if not line.lot_id.product_qty > 0:
                continue
            # Skip if this (lot.name + serial_type) is already used elsewhere
            if (line.lot_id.name, line.lot_id.serial_type) in used_combinations:
                continue

            replicated = line.lot_id.product_id.product_replication_list_id.filtered(
                lambda x: x.store_id.name == self.partner_id.name)
            if replicated and replicated.date_replication == False:
                raise ValidationError(
                    f"This Article {line.lot_id.product_id.display_name} not integrated to store.")

            lot_ids = [(6, 0, line.lot_id.ids)]
            barcodes = line.lot_id.mapped('ref')
            barcodes = [barcode for barcode in barcodes if barcode]
            branded_barcode_value = ', '.join(set(barcodes))
            self.order_line.create({
                'order_id': self.id,
                'product_id': line.product_id.id,
                'family_id': line.product_id.categ_id.parent_id.parent_id.parent_id.id,
                'category_id': line.product_id.categ_id.parent_id.parent_id.id,
                'class_id': line.product_id.categ_id.parent_id.id,
                'brick_id': line.product_id.categ_id.id,
                'lot_ids': lot_ids,
                'branded_barcode': branded_barcode_value or line.product_id.barcode,
                'type_product': line.type_product,
                'product_uom_qty': line.quantity,
                'price_unit': line.lot_id.cost_price,
                'sale_serial_type': line.lot_id.serial_type,
            })
            line.lot_id.is_uploaded = True

    @api.onchange('barcode_scanned')
    def _onchange_barcode_scanned(self):
        if not self.so_type:
            if self.barcode_scanned:
                raise ValidationError('Please choose a So Type before scanning a barcode.')
            return
        if self.barcode_scanned:
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

            def global_lot_qty(lot, current_type):
                sale_lines = self.env['sale.order.line'].search([
                    ('lot_ids.name', '=', lot.name),
                    ('company_id', '=', self.env.company.id),
                    ('sale_serial_type', '=', current_type),
                    ('order_id.state', 'not in', ['cancel'])
                ])
                return sum(sale_lines.mapped('product_uom_qty'))

            def global_serial_used_orders(serial, current_type):
                sale_lines = self.env['sale.order.line'].search([
                    ('lot_ids.name', '=', serial),
                    ('company_id', '=', self.env.company.id),
                    ('sale_serial_type', '=', current_type),
                    ('order_id.state', 'not in', ['cancel'])
                ])
                return sale_lines.mapped('order_id.name')

            existing_order_line_cmds = [(4, line.id) for line in self.order_line]

            # GS1 Barcode
            if re.match(gs1_pattern, barcode):
                product_barcode, scanned_number = re.match(gs1_pattern, barcode).groups()
                product = search_product('barcode', product_barcode)
                if not product:
                    raise ValidationError(f"No product found with barcode {product_barcode}.")
                if product.tracking not in ('serial', 'lot'):
                    raise ValidationError(f'Product {product.display_name} must have serial or lot tracking.')
                location = self.env.ref('stock.stock_location_stock').id
                lots = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),('quantity','>',0),('location_id.id','=',location),
                    ('lot_id.name', '=', scanned_number),('lot_id.type_product','=','un_brand'),
                    ('company_id', '=', self.company_id.id)
                ], limit=1)
                lot = lots.lot_id
                if lot.rs_price <= 0.0 :
                    raise ValidationError(f"You are not allowed to some of the serial numbers are not done landed cost.")

                if not lot:
                    raise ValidationError(f'No lot/serial number found for {scanned_number}.')

                sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
                if product.tracking == 'serial':
                    if self.entered_qty > 1:
                        raise ValidationError("Serial Product: Qty must be 1.")
                    if scanned_number in self.order_line.filtered(
                            lambda l: l.sale_serial_type == sale_serial_type).mapped('lot_ids.name'):
                        raise ValidationError(f"Serial number {scanned_number} is already used in this order.")
                    existing_orders = global_serial_used_orders(scanned_number, sale_serial_type)
                    if existing_orders:
                        raise ValidationError(
                            f"Serial {scanned_number} already used in: {', '.join(set(existing_orders))}")
                    qty = 1
                else:
                    if not self.entered_qty or self.entered_qty <= 0:
                        raise ValidationError("Enter a valid quantity for lot tracked product.")
                    qty = self.entered_qty
                    if any(
                            lot.name in line.lot_ids.mapped('name') and line.sale_serial_type == sale_serial_type
                            for line in self.order_line
                    ):
                        raise ValidationError(
                            f"Lot {lot.name} is already added in this sale order.")
                    existing_qty = global_lot_qty(lot, sale_serial_type)
                    lot_qty = self.env['stock.move.line'].sudo().search([
                        ('company_id.nhcl_company_bool', '=', True), ('lot_id', '=', lot.id),
                        ('location_dest_id.id', '=', location)])
                    if existing_qty + qty > sum(lot_qty.mapped('quantity')):
                        raise ValidationError(f'Qty for lot {lot.name} exceeds available stock.')
                replicated = lot.product_id.product_replication_list_id.filtered(
                    lambda x: x.store_id.name == self.partner_id.name)
                if replicated and replicated.date_replication == False:
                    raise ValidationError(
                        f"This Article {lot.product_id.display_name} not integrated to store.")

                new_line = (0, 0, {
                    'product_id': product.id,
                    'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                    'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
                    'class_id': lot.product_id.categ_id.parent_id.id,
                    'brick_id': lot.product_id.categ_id.id,
                    'product_uom_qty': qty,
                    'lot_ids': [(4, lot.id)],
                    'branded_barcode': lot.ref,
                    'type_product': lot.type_product,
                    'price_unit': lot.cost_price,
                    'sale_serial_type': sale_serial_type,
                })
                lot.is_uploaded = True
                self.order_line = [new_line] + existing_order_line_cmds

            # EAN-13 Barcode
            elif re.match(ean13_pattern, barcode):
                ean13_barcode = re.match(ean13_pattern, barcode).group(1)
                location = self.env.ref('stock.stock_location_stock').id
                lots = self.env['stock.quant'].search([
                    ('lot_id.ref', '=', ean13_barcode),
                    ('location_id.id', '=', location),
                    ('quantity', '>', 0),
                    ('lot_id.type_product', '=', 'brand'),
                    ('company_id', '=', self.company_id.id)
                ], order='id asc')

                if not lots:
                    raise ValidationError(f"No lots found with EAN-13 barcode {ean13_barcode}.")

                product = lots[0].product_id
                if not product or product.tracking not in ('serial', 'lot'):
                    raise ValidationError(f'Product must be tracked.')

                # Variables for allocation
                remaining_qty = self.entered_qty or 0
                if remaining_qty <= 0:
                    raise ValidationError("Enter a valid quantity to allocate.")

                used_names = set(self.order_line.mapped('lot_ids.name'))
                allocated_lines = []

                for lot_quant in lots:
                    lot = lot_quant.lot_id
                    sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'

                    if product.tracking == 'serial':
                        # Serial → only one per line
                        if self.entered_qty > 1:
                            raise ValidationError("Serial product: Qty must be 1.")
                        if lot.name in used_names:
                            continue
                        existing_orders = global_serial_used_orders(lot.name, sale_serial_type)
                        if existing_orders:
                            continue
                        if lot.rs_price <= 0.0:
                            raise ValidationError(
                                f"You are not allowed to add serials not done with landed cost."
                            )
                        replicated = lot.product_id.product_replication_list_id.filtered(
                            lambda x: x.store_id.name == self.partner_id.name)
                        if replicated and not replicated.date_replication:
                            raise ValidationError(
                                f"This Article {lot.product_id.display_name} not integrated to store."
                            )
                        new_line = (0, 0, {
                            'product_id': product.id,
                            'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                            'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
                            'class_id': lot.product_id.categ_id.parent_id.id,
                            'brick_id': lot.product_id.categ_id.id,
                            'product_uom_qty': 1,
                            'lot_ids': [(4, lot.id)],
                            'branded_barcode': lot.ref,
                            'type_product': lot.type_product,
                            'price_unit': lot.cost_price,
                            'sale_serial_type': sale_serial_type,
                        })
                        allocated_lines.append(new_line)
                        lot.is_uploaded = True
                        break

                    elif product.tracking == 'lot':
                        # Skip already used lots
                        if any(lot.name in line.lot_ids.mapped('name') and line.sale_serial_type == sale_serial_type
                               for line in self.order_line):
                            continue

                        existing_qty = global_lot_qty(lot, sale_serial_type)
                        total_stock_qty = sum(self.env['stock.move.line'].sudo().search([
                            ('company_id.nhcl_company_bool', '=', True),
                            ('lot_id', '=', lot.id),
                            ('location_dest_id.id', '=', location)
                        ]).mapped('quantity'))

                        available_qty = total_stock_qty - existing_qty
                        if available_qty <= 0:
                            continue

                        allocate_qty = min(remaining_qty, available_qty)
                        if allocate_qty <= 0:
                            continue

                        if lot.rs_price <= 0.0:
                            raise ValidationError(
                                f"You are not allowed to add lot {lot.name} not done with landed cost."
                            )
                        replicated = lot.product_id.product_replication_list_id.filtered(
                            lambda x: x.store_id.name == self.partner_id.name)
                        if replicated and not replicated.date_replication:
                            raise ValidationError(
                                f"This Article {lot.product_id.display_name} not integrated to store."
                            )

                        new_line = (0, 0, {
                            'product_id': product.id,
                            'family_id': lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                            'category_id': lot.product_id.categ_id.parent_id.parent_id.id,
                            'class_id': lot.product_id.categ_id.parent_id.id,
                            'brick_id': lot.product_id.categ_id.id,
                            'product_uom_qty': allocate_qty,
                            'lot_ids': [(4, lot.id)],
                            'branded_barcode': lot.ref,
                            'type_product': lot.type_product,
                            'price_unit': lot.cost_price,
                            'sale_serial_type': sale_serial_type,
                        })
                        allocated_lines.append(new_line)
                        lot.is_uploaded = True
                        remaining_qty -= allocate_qty

                        if remaining_qty <= 0:
                            break

                if not allocated_lines:
                    raise ValidationError(
                        f"All lots for barcode {ean13_barcode} are used or exceed available quantity.")

                if remaining_qty > 0:
                    raise ValidationError(
                        f"Only {self.entered_qty - remaining_qty} qty allocated. Not enough available lots to fulfill full {self.entered_qty} qty."
                    )

                # Update order lines
                self.order_line = allocated_lines + existing_order_line_cmds

            # Custom Serial Barcode
            elif re.match(custom_serial_pattern, barcode):
                prefix = re.match(custom_serial_pattern, barcode).group(1)
                location = self.env.ref('stock.stock_location_stock').id
                lots = self.env['stock.quant'].search(['|',
                    ('lot_id.ref', '=', prefix),('lot_id.name', '=', f'{prefix}'),('quantity','>',0),
                    ('company_id', '=', self.company_id.id),('location_id.id','=',location)
                ])
                if not lots:
                    raise ValidationError(f"No lots found for custom barcode {prefix}")

                selected_lot = None
                qty = 0
                for lot in lots.lot_id:
                    product = lot.product_id
                    sale_serial_type = 'return' if lot.serial_type == 'return' else 'regular'
                    if product.tracking == 'serial':
                        if self.entered_qty > 1:
                            raise ValidationError("Serial product: Qty must be 1.")
                        if lot.name in self.order_line.filtered(
                                lambda l: l.sale_serial_type == sale_serial_type).mapped('lot_ids.name'):
                            raise ValidationError(f"Serial {lot.name} already used in this order.")
                        existing_orders = global_serial_used_orders(lot.name, sale_serial_type)
                        if existing_orders:
                            raise ValidationError(
                                f"Serial {lot.name} already used in: {', '.join(set(existing_orders))}")
                        selected_lot = lot
                        qty = 1
                        break
                    elif product.tracking == 'lot':
                        if not self.entered_qty or self.entered_qty <= 0:
                            raise ValidationError("Enter a valid quantity for lot tracked product.")
                        if any(
                                lot.name in line.lot_ids.mapped('name') and line.sale_serial_type == sale_serial_type
                                for line in self.order_line
                        ):
                            raise ValidationError(
                                f"Lot {lot.name} is already added in this sale order.")
                        existing_qty = global_lot_qty(lot, sale_serial_type)
                        lot_qty = self.env['stock.move.line'].sudo().search([
                            ('company_id.nhcl_company_bool', '=', True),
                            ('lot_id', '=', lot.id),
                            ('location_dest_id.id', '=', location)])
                        if existing_qty + self.entered_qty <= sum(lot_qty.mapped('quantity')):
                            selected_lot = lot
                            qty = self.entered_qty
                            break
                if not selected_lot:
                    raise ValidationError(f"No available lot found for {prefix} that meets constraints.")
                if selected_lot.rs_price <= 0.0 :
                    raise ValidationError(f"You are not allowed to some of the serial numbers are not done landed cost.")
                replicated = selected_lot.product_id.product_replication_list_id.filtered(
                    lambda x: x.store_id.name == self.partner_id.name)
                if replicated and replicated.date_replication == False:
                    raise ValidationError(
                        f"This Article {selected_lot.product_id.display_name} not integrated to store.")
                new_line = (0, 0, {
                    'product_id': selected_lot.product_id.id,
                    'family_id': selected_lot.product_id.categ_id.parent_id.parent_id.parent_id.id,
                    'category_id': selected_lot.product_id.categ_id.parent_id.parent_id.id,
                    'class_id': selected_lot.product_id.categ_id.parent_id.id,
                    'brick_id': selected_lot.product_id.categ_id.id,
                    'product_uom_qty': qty,
                    'lot_ids': [(4, selected_lot.id)],
                    'branded_barcode': selected_lot.ref,
                    'type_product': selected_lot.type_product,
                    'price_unit': selected_lot.cost_price,
                    'sale_serial_type': sale_serial_type
                })
                selected_lot.is_uploaded = True
                self.order_line = [new_line] + existing_order_line_cmds
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

    @api.constrains('lot_ids')
    def check_lot_serial_main_location(self):
        for line in self:
            if line.order_id.stock_type == 'regular':
                location = False
                if self.lot_ids:
                    location = self.env.ref('stock.stock_location_stock').id
                    for i in self:
                        lot = self.env['stock.quant'].search(
                            [('lot_id.name', '=', i.lot_ids.name), ('location_id', '=', location), ('quantity', '>', 0),
                             ('company_id.nhcl_company_bool', '=', True)])
                        if not lot:
                            raise ValidationError(f"This {i.lot_ids.name} Serial/Lot are not available in the main location")

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


    def _action_launch_stock_rule(self, previous_product_uom_qty=False):
        """ Override to ensure lot/serial numbers are carried over to stock moves """
        moves = super(SaleOrderLine, self)._action_launch_stock_rule(previous_product_uom_qty)
        for rec in self:
            for move_id in rec.move_ids:
                if move_id.product_id.tracking == 'serial':
                    lot_ids = self.filtered(lambda x:x.product_id == move_id.product_id).mapped('lot_ids')
                    move_id.move_line_ids.lot_id = False
                    move_id.lot_ids = [(4, lot.id) for lot in lot_ids]
        return moves


    @api.constrains('lot_ids')
    def check_landed_cost_yes(self):
        for lot in self:
            if lot.lot_ids.cost_price < 1.0 or lot.lot_ids.rs_price < 1.0:
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