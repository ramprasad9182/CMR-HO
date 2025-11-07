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

    bill_number = fields.Char(string="Vendor Bill Number", store=True)

    # Automatically fetch receipt in draft state from PO
    # receipt_number = fields.Many2one(
    #     'stock.picking',
    #     string="Receipt (Draft)",
    #     compute="_compute_receipt",
    #     store=True,
    # )

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

    select_all = fields.Boolean(string="Select All", default=False)

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
    # BILL NUMBER ONCHANGE
    # ==============================
    @api.onchange('purchase_order_id')
    def _onchange_purchase_order_id(self):
        if self.purchase_order_id:
            self.bill_number = self.purchase_order_id.invoice_number or False
        else:
            self.bill_number = False

    # ==============================
    # AUTO COMPUTE DRAFT RECEIPT FROM PO
    # ==============================
    # @api.depends('purchase_order_id')
    # def _compute_receipt(self):
    #     for record in self:
    #         if not record.purchase_order_id:
    #             record.receipt_number = False
    #             continue
    #
    #         po = record.purchase_order_id
    #         draft_receipt = self.env['stock.picking'].search([
    #             ('origin', '=', po.name),
    #             ('picking_type_id.code', '=', 'incoming'),
    #             ('state', '=', 'draft')
    #         ], limit=1)
    #
    #         record.receipt_number = draft_receipt.id if draft_receipt else False

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

    # ==============================
    # ACTION: LOAD PO LINES
    # ==============================
    def action_load_po_lines(self):
        self.ensure_one()
        self.pt_order_line_ids.unlink()
        self.pt_product_summary_ids.unlink()

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

        purchase_order_lines = self.env['purchase.order.line'].sudo().search(domain)

        if not purchase_order_lines:
            raise UserError("No PO Indents available to load.")

        line_commands = []
        summary_dict = {}

        for line in purchase_order_lines:
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

            if line.product_id not in summary_dict:
                summary_dict[line.product_id] = {
                    'total_qty': 0.0,
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
                }
            summary_dict[line.product_id]['total_qty'] += line.product_qty

        self.pt_order_line_ids = line_commands
        self.pt_product_summary_ids = [
            (0, 0, {
                'product_id': product.id,
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
            }) for product, vals in summary_dict.items()
        ]

        self.state = 'progress'
        _logger.info("PO lines loaded successfully for indent %s", self.name)

    # ==============================
    # ACTION: UPDATE RECEIPT QUANTITY
    # ==============================
    def action_update_receipt_quantity(self):
        """Update or create stock moves in draft receipt from PO lines."""
        for record in self:
            if not record.purchase_order_id:
                raise UserError("Please select a Purchase Order first.")
            if not record.receipt_number_current_company:
                raise UserError("No draft receipt found for this Purchase Order.")

            receipt = record.receipt_number_current_company
            po_lines = record.pt_order_line_ids.mapped('pt_po_line_id')

            for line in po_lines:
                move = receipt.move_ids_without_package.filtered(lambda m: m.product_id == line.product_id)
                if move:
                    move.quantity = line.product_qty
                else:
                    self.env['stock.move'].create({
                        'name': line.name,
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.product_qty,
                        'product_uom': line.product_uom.id,
                        'location_id': receipt.location_id.id,
                        'location_dest_id': receipt.location_dest_id.id,
                        'picking_id': receipt.id,
                    })

            _logger.info("Receipt quantities updated for receipt %s", receipt.name)

            self.write({

                'state': 'done'
            })

        return True




