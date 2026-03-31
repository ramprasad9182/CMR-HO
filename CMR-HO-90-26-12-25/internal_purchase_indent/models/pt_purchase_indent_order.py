import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from collections import defaultdict

_logger = logging.getLogger(__name__)


class PTUploadIndent(models.Model):
    _name = 'pt.upload.indent'
    _description = 'PT Upload Indents'
    _rec_name = 'name'

    name = fields.Char(
        string='Indent Number',
        required=True,
        copy=False,
        readonly=True,
        default='New'
    )

    pt_order_line_ids = fields.One2many(
        'pt.upload.indent.orderline',
        'pt_indent_id',
        string="PO Lines"
    )
    pt_product_summary_ids = fields.One2many(
        'pt.product.summary',
        'pt_indent_sum_id',
        string="Product Summary Data"
    )

    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    request_owner_id = fields.Many2one(
        "res.users",
        check_company=True,
        default=lambda self: self.env.user,
    )

    store = fields.Many2one(
        "res.company",
        string="Store",
        domain="[('nhcl_company_bool', '=', False)]",
    )

    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")

    product_category = fields.Many2many(
        "product.category",
        string="Product Category",
        domain="[('parent_id.parent_id.parent_id', '!=', False)]",
    )
    product_variant = fields.Many2many(
        'product.product',
        string="Product",
        domain="[('categ_id', '=', product_category)]"
    )

    product_variant_tags = fields.Char(
        string='Product Variant Tags',
        compute='_get_variant_tags',
        store=True
    )
    store_tags = fields.Char(
        string='Store Tags',
        compute='_get_store_tags',
        store=True
    )

    indent_filter_type = fields.Selection(
        [
            ('purchase', 'Purchase'),
            ('product_category', 'Product Category')
        ],
        default='product_category',
        string='Filter Type',
        copy=False
    )

    # Purchase Order selection (no filters)
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        copy=False,

    )

    location_type = fields.Selection(
        [
            ('ho', 'Head Office'),
            ('store', 'Store'),
        ],
        string="Location Type",
        required=True,
        default='ho'
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('progress', 'On Process'),
        ('done', 'Confirmed'),
        ('cancel', 'Cancelled')
    ], string='Status', readonly=True, index=True, copy=False, default='draft', tracking=True)

    select_all = fields.Boolean(string="Select All", default=False)
    vendor = fields.Many2one('res.partner', string="Vendor", domain="[('group_contact.name', '=', 'Vendor')]")

    purchase_order_current_company_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order (Current Company)',
        domain="[('company_id', '=', company_id)]",
        copy=False,
    )

    receipt_number_current_company = fields.Many2one(
        'stock.picking',
        string='Receipt (Current Company)',
        compute="_compute_current_company_receipt",
        store=True,
    )



    @api.onchange('select_all')
    def _onchange_select_all(self):
        """ On changing the 'select_all' field, set all individual records' 'select' fields accordingly """
        for line in self.pt_product_summary_ids:
            line.select = self.select_all

    @api.depends('purchase_order_current_company_id')
    def _compute_current_company_receipt(self):
        for record in self:
            if not record.purchase_order_current_company_id:
                record.receipt_number_current_company = False
                continue

            po = record.purchase_order_current_company_id

            # find incoming receipts linked to this PO
            pickings = self.env['stock.picking'].search([
                ('origin', '=', po.name),
                ('picking_type_id.code', '=', 'incoming'),
                ('state', '=', 'assigned')  # ✅ only draft receipts
            ], limit=1)

            record.receipt_number_current_company = pickings.id if pickings else False


    # ==============================
    # CREATE: Auto sequence
    # ==============================
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('internal.purchase.indent') or 'New'
        return super().create(vals)


    # ==============================
    # TAG COMPUTATIONS
    # ==============================
    @api.depends('product_variant')
    def _get_variant_tags(self):
        for rec in self:
            rec.product_variant_tags = ', '.join([p.display_name for p in rec.product_variant]) if rec.product_variant else ''

    @api.depends('store')
    def _get_store_tags(self):
        for rec in self:
            rec.store_tags = rec.store.display_name if rec.store else ''

    # ==============================
    # DATE RANGE VALIDATION
    # ==============================
    @api.constrains('from_date', 'to_date')
    def _check_date_range(self):
        for rec in self:
            if rec.from_date and rec.to_date and rec.from_date > rec.to_date:
                raise ValidationError("From Date cannot be after To Date.")

    def action_load_po_lines(self):
        """Load purchase order lines and create summary lines based on product + barcode."""
        self.ensure_one()
        _logger.info("========== Starting action_load_po_lines for indent: %s ==========", self.name)
        print("========== Starting action_load_po_lines for indent:", self.name, "==========")

        # Clear existing lines
        self.pt_order_line_ids.unlink()
        self.pt_product_summary_ids.unlink()
        print("Cleared existing pt_order_line_ids and pt_product_summary_ids")

        # Build search domain
        domain = [
            ('state', '=', 'draft'),
            ('order_id.nhcl_po_type', 'in', ['inter_state', 'intra_state']),
            ('date_order', '>=', self.from_date),
            ('date_order', '<=', self.to_date),
            ('company_id.nhcl_company_bool', '=', False)
        ]
        if self.store:
            domain.append(('company_id', '=', self.store.id))
        if self.product_category:
            domain.append(('product_id.categ_id', 'in', self.product_category.ids))
        if self.product_variant:
            domain.append(('product_id', 'in', self.product_variant.ids))
        if self.purchase_order_id:
            domain.append(('order_id', '=', self.purchase_order_id.id))

        print("Search domain:", domain)
        purchase_order_lines = self.env['purchase.order.line'].sudo().search(domain)
        print("Found", len(purchase_order_lines), "purchase order lines")

        if not purchase_order_lines:
            raise UserError("No PO Indents available to load.")

        line_commands = []
        summary_dict = {}

        # --- Loop through PO lines ---
        for line in purchase_order_lines:
            print(
                f"Processing PO Line: {line.id} | Product: {line.product_id.display_name} | Barcode: {line.icode_barcode} | Qty: {line.product_qty}")

            # Add detailed indent line
            line_commands.append((0, 0, {
                'pt_po_line_id': line.id,
                'pt_indent_id': self.id,
                'icode_barcode': line.icode_barcode,
                'brand': line.brand,
                'size': line.size,
                'design': line.design,
                'fit': line.fit,
                'colour': line.colour,
                'mrp': line.mrp,
                'rsp': line.rsp,
                'des5': line.des5,
                'des6': line.des6,
            }))

            # Use (product_id, icode_barcode) as the composite key
            key = (line.product_id.id, line.icode_barcode or '')

            if key not in summary_dict:
                summary_dict[key] = {
                    'product_id': line.product_id,
                    'icode_barcode': line.icode_barcode,
                    'brand': line.brand,
                    'size': line.size,
                    'design': line.design,
                    'fit': line.fit,
                    'colour': line.colour,
                    'mrp': line.mrp,
                    'rsp': line.rsp,
                    'des5': line.des5,
                    'des6': line.des6,
                    'total_qty': 0.0,
                }
                print(
                    f"→ New summary entry created for Product: {line.product_id.display_name}, Barcode: {line.icode_barcode}")

            # Aggregate total quantity
            summary_dict[key]['total_qty'] += line.product_qty
            print(
                f"→ Updated total_qty for ({line.product_id.display_name}, {line.icode_barcode}): {summary_dict[key]['total_qty']}")

        # --- Create order and summary lines ---
        print("Creating", len(line_commands), "detailed PO lines")
        self.pt_order_line_ids = line_commands

        print("Creating", len(summary_dict), "summary lines")
        self.pt_product_summary_ids = [
            (0, 0, {
                'product_id': vals['product_id'].id,
                'icode_barcode': vals['icode_barcode'],
                'brand': vals['brand'],
                'size': vals['size'],
                'design': vals['design'],
                'fit': vals['fit'],
                'colour': vals['colour'],
                'mrp': vals['mrp'],
                'rsp': vals['rsp'],
                'des5': vals['des5'],
                'des6': vals['des6'],
                'pi_quantity': vals['total_qty'],
                'as_of_date': datetime.now(),
                'pt_indent_sum_id': self.id,
            }) for key, vals in summary_dict.items()
        ]

        # Update state
        self.state = 'progress'
        _logger.info("PO lines and summary lines loaded successfully for indent %s", self.name)
        print("========== Completed action_load_po_lines for indent:", self.name, "==========")

    def action_update_receipt_quantity(self):
        """Update stock.move.line records from PO lines.
           - If tracking = 'lot': one move line per barcode.
           - If tracking = 'serial': one move line per quantity (qty_done = 1).
           - Keeps move quantities unchanged.
           - Cancels related Purchase Order after completion."""
        for record in self:
            print("========== Starting action_update_receipt_quantity ==========")
            print("Processing record:", record.name)
            _logger.info("Starting receipt quantity update for indent: %s", record.name)

            if not record.purchase_order_id:
                raise UserError("Please select a Purchase Order first.")
            if not record.receipt_number_current_company:
                raise UserError("No draft receipt found for this Purchase Order.")

            receipt = record.receipt_number_current_company
            print("Receipt found:", receipt.name, "| State:", receipt.state)

            po_lines = record.pt_order_line_ids.mapped('pt_po_line_id')
            print("Total PO lines to process:", len(po_lines))
            if not po_lines:
                continue

            # Group PO lines by product
            grouped_by_product = {}
            for line in po_lines:
                grouped_by_product.setdefault(line.product_id, []).append(line)

            for product, lines in grouped_by_product.items():
                print(f"\nProcessing Product: {product.display_name} | Tracking: {product.tracking}")

                move = receipt.move_ids_without_package.filtered(lambda m: m.product_id == product)
                if not move:
                    print(f"No existing move found for {product.display_name}, skipping.")
                    continue

                # Clear existing move lines once per product
                if move.move_line_ids:
                    print(f"Clearing {len(move.move_line_ids)} existing move lines for {product.display_name}")
                    move.move_line_ids.unlink()

                # LOT-TRACKED
                if product.tracking == 'lot':
                    print(f"→ Product {product.display_name} is LOT tracked.")
                    unique_barcodes = {}
                    for line in lines:
                        key = str(line.icode_barcode).split('.')[0] if line.icode_barcode else 'NO_BARCODE'
                        unique_barcodes.setdefault(key, 0.0)
                        unique_barcodes[key] += line.product_qty

                    for barcode, qty in unique_barcodes.items():
                        lot_id = self.env['stock.lot'].search([('ref', '=', barcode)], limit=1)
                        cat1 = lot_id.product_id.categ_id
                        # walk the parent chain safely
                        p11 = cat1.parent_id
                        p22 = p11.parent_id if p11 else False
                        p33 = p22.parent_id if p22 else False
                        move_line_vals = {
                            'move_id': move.id,
                            'product_id': product.id,
                            'product_uom_id': lines[0].product_uom.id,
                            'qty_done': qty,
                            'location_id': receipt.location_id.id,
                            'location_dest_id': receipt.location_dest_id.id,
                            'picking_id': receipt.id,
                            'internal_ref_lot': barcode if barcode != 'NO_BARCODE' else False,
                            # 'lot_id': lot_id.id if lot_id else False,
                            'brick': cat1.id,
                            'class_level_id': p11.id if p11 else False,
                            'category': p22.id if p22 else False,
                            'family': p33.id if p33 else False,
                        }
                        self.env['stock.move.line'].create(move_line_vals)
                        print(f"→ Created LOT move line for {product.display_name}, Barcode: {barcode}, Qty: {qty}")

                # SERIAL-TRACKED
                elif product.tracking == 'serial':
                    print(f"→ Product {product.display_name} is SERIAL tracked.")
                    for line in lines:
                        barcode = str(line.icode_barcode).split('.')[0] if line.icode_barcode else False
                        qty = int(line.product_qty)
                        lot_id = self.env['stock.lot'].search([('ref', '=', barcode)], limit=1)
                        cat1 = lot_id.product_id.categ_id
                        # walk the parent chain safely
                        p11 = cat1.parent_id
                        p22 = p11.parent_id if p11 else False
                        p33 = p22.parent_id if p22 else False
                        for i in range(qty):
                            move_line_vals = {
                                'move_id': move.id,
                                'product_id': product.id,
                                'product_uom_id': line.product_uom.id,
                                'qty_done': 1.0,
                                'location_id': receipt.location_id.id,
                                'location_dest_id': receipt.location_dest_id.id,
                                'picking_id': receipt.id,
                                'internal_ref_lot': barcode,
                                # 'lot_id': lot_id.id if lot_id else False,
                                'brick': cat1.id,
                                'class_level_id': p11.id if p11 else False,
                                'category': p22.id if p22 else False,
                                'family': p33.id if p33 else False,
                            }
                            self.env['stock.move.line'].create(move_line_vals)
                        print(f"→ Created {qty} SERIAL move lines for {product.display_name}, Barcode: {barcode}")

                else:
                    print(f"→ Product {product.display_name} is NOT tracked (tracking = {product.tracking}). Skipping.")
                    _logger.info("Skipped non-tracked product %s", product.display_name)

            # --- Finalize record ---
            record.write({'state': 'done'})
            print("State updated to 'done' for record:", record.name)
            _logger.info("Indent %s marked as done", record.name)

            # --- Cancel related Purchase Order ---
            if record.purchase_order_id and record.purchase_order_id.state not in ['cancel', 'done']:
                print(f"Cancelling linked Purchase Order: {record.purchase_order_id.name}")
                record.purchase_order_id.button_cancel()
                _logger.info("Cancelled Purchase Order %s", record.purchase_order_id.name)

            print("========== Completed action_update_receipt_quantity ==========\n")

        return True





