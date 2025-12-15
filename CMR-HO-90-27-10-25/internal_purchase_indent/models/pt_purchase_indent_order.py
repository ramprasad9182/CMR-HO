import logging

from odoo import models, fields, api,_
from odoo.exceptions import ValidationError, UserError
from collections import defaultdict
from datetime import datetime
import requests

_logger = logging.getLogger(__name__)



class PTUploadIndent(models.Model):
    _name = 'pt.upload.indent'
    _description = 'PT Upload Indents'
    _rec_name = 'name'

    name = fields.Char(string='Indent Number', required=True, copy=False, readonly=True, default='New')
    pt_order_line_ids = fields.One2many(
        'pt.upload.indent.orderline',
        'pt_indent_id',
        string="PO Lines")
    # approval_request_id = fields.Many2one("approval.request",string="PI Request")


    pt_product_summary_ids = fields.One2many(
        'pt.product.summary',
        'pt_indent_sum_id',
        string="Product Summary Data"
    )
    company_id = fields.Many2one("res.company",default=lambda self: self.env.company)
    request_owner_id = fields.Many2one("res.users", check_company=True, default=lambda self: self.env.user,)
    store = fields.Many2one("res.company", string="Store", domain="[('nhcl_company_bool', '=', False)]",)
    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    product_category = fields.Many2many(
        "product.category",
        string="Product Category",
        domain="[('parent_id.parent_id.parent_id','!=',False)]",
    )
    product_variant = fields.Many2many(
        'product.product',
        string="Product",
        domain="[('categ_id', '=', product_category)]")
    product_variant_tags = fields.Char(string='Product Variant Tags', compute='_get_variant_tags', store=True)
    store_tags = fields.Char(string='Store Tags', compute='_get_store_tags', store=True)
    # purchase_order_id = fields.Many2one('purchase.order',string='Purchase Orders',copy=False)
    indent_filter_type = fields.Selection([('purchase','Purchase'),('product_category','Product Category')],default='product_category',string='Filter Type',copy=False)
#keerthana
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Orders',
        copy=False,
        domain="[('id', 'not in', already_linked_po_ids)]",
    )

    already_linked_po_ids = fields.Many2many(
        'purchase.order',
        compute='_compute_already_linked_po_ids',
        store=False
    )
    # icode_barcode = fields.Char(string="Barcode")

    @api.depends()
    def _compute_already_linked_po_ids(self):
        """Fetch all POs already linked with other indents (exclude current one)."""
        used_po_ids = self.env['pt.upload.indent'].search([
            ('purchase_order_id', '!=', False),
            ('id', '!=', self.id)
        ]).mapped('purchase_order_id.id')
        for rec in self:
            rec.already_linked_po_ids = [(6, 0, used_po_ids)]
    location_type = fields.Selection(
        [
            ('ho', 'Head Office'),
            ('store', 'Store'),
        ],
        string="Location Type",
        required=True,
        default='ho'
    )
    bill_number = fields.Char(string="Vendor Bill Number", store=True)
    # receipt_number = fields.Char(string="Receipt Number", compute="_compute_receipt", store=True)
    receipt_number = fields.Many2one(
        'stock.picking',
        string="Receipt Number",
        compute="_compute_receipt",
        store=True
    )

    @api.constrains('purchase_order_id')
    def _check_unique_purchase_order(self):
        for rec in self:
            if rec.purchase_order_id:
                other_indent = self.search([
                    ('id', '!=', rec.id),
                    ('purchase_order_id', '=', rec.purchase_order_id.id)
                ], limit=1)
                if other_indent:
                    raise ValidationError(
                        _("Purchase Order %s is already linked with Indent %s. You cannot reuse it.") %
                        (rec.purchase_order_id.display_name, other_indent.name)
                    )

    @api.onchange('purchase_order_id')
    def _onchange_purchase_order_id(self):
        if self.purchase_order_id:
            self.bill_number = self.purchase_order_id.invoice_number  # <-- replace with correct field name
        else:
            self.bill_number = False

    # @api.depends('bill_number')
    # def _compute_receipt(self):
    #     for record in self:
    #
    #         if not record.bill_number:
    #
    #             record.receipt_number = False
    #             continue
    #
    #         # Search the bill by name
    #         bill = self.env['account.move'].search(
    #             [('name', '=', record.bill_number), ('move_type', '=', 'in_invoice')], limit=1)
    #         if not bill:
    #
    #             record.receipt_number = False
    #             continue
    #
    #
    #
    #         # Get linked purchase orders via invoice lines -> purchase_line_id -> order_id
    #         linked_pos = bill.invoice_line_ids.mapped('purchase_line_id.order_id')
    #         if not linked_pos:
    #
    #             record.receipt_number = False
    #             continue
    #
    #         po_names = linked_pos.mapped('name')
    #
    #
    #         # Get all pickings for these POs
    #         pickings = self.env['stock.picking'].search([('origin', 'in', po_names)])
    #         if not pickings:
    #
    #             record.receipt_number = False
    #             continue
    #
    #
    #
    #         # Filter done incoming pickings
    #         done_pickings = pickings.filtered(lambda p: p.state == 'done' and p.picking_type_id.code == 'incoming')
    #         if done_pickings:
    #             receipt_names = ", ".join(done_pickings.mapped('name'))
    #
    #             record.receipt_number = receipt_names
    #         else:
    #             record.receipt_number = ", ".join(pickings.mapped('name'))
    #22222
    # @api.depends('bill_number')
    # def _compute_receipt(self):
    #     for record in self:
    #         if not record.bill_number:
    #             record.receipt_number = False
    #             continue
    #
    #         # Search the bill by name
    #         bill = self.env['account.move'].search(
    #             [('name', '=', record.bill_number), ('move_type', '=', 'in_invoice')], limit=1)
    #         if not bill:
    #             record.receipt_number = False
    #             continue
    #
    #         # Get linked purchase orders via invoice lines -> purchase_line_id -> order_id
    #         linked_pos = bill.invoice_line_ids.mapped('purchase_line_id.order_id')
    #         if not linked_pos:
    #             record.receipt_number = False
    #             continue
    #
    #         po_names = linked_pos.mapped('name')
    #
    #         # Get all pickings for these POs
    #         pickings = self.env['stock.picking'].search([('origin', 'in', po_names),('state', '=', 'assigned')])
    #
    #         if not pickings:
    #             record.receipt_number = False
    #             continue
    #
    #         # Filter done incoming pickings
    #         done_pickings = pickings.filtered(lambda p: p.state == 'done' and p.picking_type_id.code == 'incoming')
    #         if done_pickings:
    #             record.receipt_number = done_pickings[0]  # Take the first done picking
    #         else:
    #             record.receipt_number = pickings[0]  # Take the first picking

    @api.depends('bill_number')
    def _compute_receipt(self):
        for record in self:
            if not record.bill_number:
                record.receipt_number = False
                continue

            # 1️⃣ Find the vendor bill by name
            bill = self.env['account.move'].search(
                [('name', '=', record.bill_number), ('move_type', '=', 'in_invoice')],
                limit=1
            )
            if not bill:
                record.receipt_number = False
                continue

            # 2️⃣ Get linked purchase orders from invoice lines
            linked_pos = bill.invoice_line_ids.mapped('purchase_line_id.order_id')
            if not linked_pos:
                record.receipt_number = False
                continue

            po_names = linked_pos.mapped('name')

            # 3️⃣ Get incoming receipts only (from these POs)
            pickings = self.env['stock.picking'].search([
                ('origin', 'in', po_names),
                ('picking_type_id.code', '=', 'incoming'),
                ('state', '=', 'assigned')  # ✅ only assigned receipts
            ])

            # 4️⃣ Assign the first assigned picking (if any)
            record.receipt_number = pickings[0] if pickings else False

    @api.depends('product_variant')
    def _get_variant_tags(self):
        for rec in self:
            if rec.product_variant:
                product_variant_tags= ','.join([p.display_name for p in rec.product_variant])
            else:
                product_variant_tags = ''
            rec.product_variant_tags=product_variant_tags

    # @api.depends('store')
    # def _get_store_tags(self):
    #     for rec in self:
    #         if rec.store:
    #             store_tags = ','.join([p.display_name for p in rec.store])
    #         else:
    #             store_tags = ''
    #         rec.store_tags = store_tags

    @api.depends('store')
    def _get_store_tags(self):
        for rec in self:
            rec.store_tags = rec.store.display_name if rec.store else ''

    state = fields.Selection([
        ('draft', 'Draft'),
        ('progress', 'On Process'),
        ('done', 'Confirmed'),
        ('cancel', 'Cancelled')
    ], string='Status', readonly=True, index=True, copy=False, default='draft', tracking=True)
    select_all = fields.Boolean(string="Select All", default=False)
    vendor = fields.Many2one('res.partner',string="Vendor",domain="[('group_contact.name','=','Vendor')]")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('internal.purchase.indent') or 'New'
        return super().create(vals)

    @api.constrains('from_date', 'to_date')
    def _check_date_range(self):
        for rec in self:
            if rec.from_date and rec.to_date and rec.from_date > rec.to_date:
                raise ValidationError("From Date cannot be after To Date.")

    # def action_load_po_lines(self):
    #     self.ensure_one()
    #
    #     # Clear existing lines
    #     self.pt_order_line_ids.unlink()
    #     self.pt_product_summary_ids.unlink()
    #
    #     # Build domain
    #     domain = [
    #         ('state', '=', 'draft'),
    #         ('order_id.nhcl_po_type', 'in', ['inter_state', 'intra_state']),
    #         ('date_order', '>=', self.from_date),
    #         ('date_order', '<=', self.to_date),
    #         ('company_id.nhcl_company_bool', '=', False)
    #     ]
    #     if self.store:
    #         domain.append(('company_id', '=', self.store.id))
    #     if self.product_category:
    #         domain.append(('product_id.categ_id', 'in', self.product_category.ids))
    #     if self.product_variant:
    #         domain.append(('product_id', '=', self.product_variant.ids))
    #     if self.purchase_order_id:
    #         domain.append(('order_id', '=', self.purchase_order_id.id))
    #
    #     purchase_order_lines = self.env['purchase.order.line'].sudo().search(domain)
    #
    #     # Exclude lines already linked to other indents
    #     linked_po_lines_other = self.env['pt.upload.indent.orderline'].sudo().search([
    #         ('pt_indent_id', '!=', False),
    #         ('pt_indent_id', '!=', self.id)
    #     ])
    #     linked_po_line_ids_other = linked_po_lines_other.mapped('pt_po_line_id.id')
    #
    #     new_po_lines = purchase_order_lines.filtered(lambda l: l.id not in linked_po_line_ids_other)
    #     if not new_po_lines:
    #         raise UserError("No PO Indents available to load (all are linked to other indents).")
    #
    #     # Build order lines
    #     line_commands = []
    #     summary_dict = defaultdict(float)
    #     barcode_dict = {}
    #
    #     for line in new_po_lines:
    #         line_commands.append((0, 0, {
    #             'pt_po_line_id': line.id,
    #             'pt_indent_id': self.id,
    #             'icode_barcode': line.icode_barcode
    #             # 'icode_barcode' is related, so no need to set here
    #         }))
    #         summary_dict[line.product_id] += line.product_qty
    #         barcode_dict[line.product_id] = line.icode_barcode
    #
    #     self.pt_order_line_ids = line_commands
    #
    #     # Build summary lines with barcode
    #     self.pt_product_summary_ids = [
    #         (0, 0, {
    #             'product_id': product.id,
    #             'icode_barcode': barcode_dict.get(product),
    #             'pi_quantity': total_qty,
    #             'as_of_date': datetime.now(),
    #             'pt_indent_sum_id': self.id,
    #         }) for product, total_qty in summary_dict.items()
    #     ]
    #
    #     self.write({'state': 'progress'})
    #     print("PO lines loaded successfully!")

    def action_load_po_lines(self):
        self.ensure_one()

        # Clear existing lines before loading new ones
        self.pt_order_line_ids.unlink()
        self.pt_product_summary_ids.unlink()

        # Build domain for fetching purchase order lines
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
            domain.append(('product_id', '=', self.product_variant.ids))
        if self.purchase_order_id:
            domain.append(('order_id', '=', self.purchase_order_id.id))

        # Search purchase order lines based on filters
        purchase_order_lines = self.env['purchase.order.line'].sudo().search(domain)

        # Exclude PO lines already linked to other indents
        linked_po_lines_other = self.env['pt.upload.indent.orderline'].sudo().search([
            ('pt_indent_id', '!=', False),
            ('pt_indent_id', '!=', self.id)
        ])
        linked_po_line_ids_other = linked_po_lines_other.mapped('pt_po_line_id.id')

        # Filter out linked lines
        new_po_lines = purchase_order_lines.filtered(lambda l: l.id not in linked_po_line_ids_other)

        if not new_po_lines:
            raise UserError("No PO Indents available to load (all are linked to other indents).")

        # Create order lines and prepare data for summary
        line_commands = []
        summary_dict = {}

        for line in new_po_lines:
            # Add PO line details to order lines
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

            # Group quantities by product
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

        # Assign order lines
        self.pt_order_line_ids = line_commands

        # Build summary lines with all product details
        summary_lines = []
        for product, values in summary_dict.items():
            summary_lines.append((0, 0, {
                'product_id': product.id,
                'icode_barcode': values['icode_barcode'],
                'brand': values['brand'],
                'size': values['size'],
                'design': values['design'],
                'fit': values['fit'],
                'colour': values['colour'],
                'mrp': values['mrp'],
                'rsp': values['rsp'],
                'des5': values['des5'],
                'des6': values['des6'],
                'pi_quantity': values['total_qty'],
                'as_of_date': datetime.now(),
                'pt_indent_sum_id': self.id,
            }))

        # Assign summary lines
        self.pt_product_summary_ids = summary_lines

        # Change state to progress
        self.write({'state': 'progress'})
        print("PO lines loaded successfully!")

    @api.onchange('select_all')
    def _onchange_select_all(self):
        """ On changing the 'select_all' field, set all individual records' 'select' fields accordingly """
        for line in self.pt_product_summary_ids:
            line.select = self.select_all

    # def action_update_receipt_quantity(self):
    #     self.ensure_one()
    #
    #     if not self.receipt_number:
    #         print("receipt", self.receipt_number)
    #         raise UserError("Receipt number not found! Please select a purchase order first.")
    #
    #     receipt = self.env['stock.picking'].search([('name', '=', self.receipt_number)], limit=1)
    #
    #     if not receipt:
    #         raise UserError(f"Receipt {self.receipt_number} not found!")
    #
    #     print(f"=== Updating Receipt Quantities for Indent: {self.name} ===")
    #     print(f"Receipt: {receipt.name}, State: {receipt.state}")
    #
    #     # Only update if picking is not done or canceled
    #     if receipt.state not in ['done', 'cancel']:
    #         for summary in self.pt_product_summary_ids:
    #             product = summary.product_id
    #             pi_quantity = summary.pi_quantity
    #
    #             # Use move_ids_without_package in Odoo 17
    #             move_lines = receipt.move_ids_without_package.filtered(lambda m: m.product_id == product)
    #             if not move_lines:
    #                 print(f"⚠️ No move lines found for product {product.name} in receipt {receipt.name}")
    #                 continue
    #
    #             for move in move_lines:
    #                 # Validation check
    #                 if pi_quantity > move.product_uom_qty:
    #                     raise UserError(
    #                         f"PI Quantity ({pi_quantity}) for product {product.display_name} "
    #                         f"cannot exceed Ordered Quantity ({move.product_uom_qty})."
    #                     )
    #
    #                 print(
    #                     f"Updating move line {move.id} for product {product.name}: "
    #                     f"{getattr(move, 'quantity', 'N/A')} -> {pi_quantity}"
    #                 )
    #                 move.quantity = pi_quantity  # update your custom quantity field
    #
    #         self.state = 'done'
    #         print("✅ Receipt quantities updated successfully!")
    #         return {
    #             'effect': {
    #                 'fadeout': 'slow',
    #                 'message': 'Receipt Quantities Updated Successfully',
    #                 'type': 'rainbow_man',
    #             }
    #         }
    #     else:
    #         raise UserError(f"Picking {receipt.name} is already in state '{receipt.state}'. Cannot update quantities.")

    def action_update_receipt_quantity(self):
        self.ensure_one()

        if not self.receipt_number:
            raise UserError("Receipt number not found! Please select a purchase order first.")

        # Use the existing record directly (no need to search)
        receipt = self.receipt_number

        if not receipt:
            raise UserError(f"Receipt {self.receipt_number.name} not found!")

        print(f"=== Updating Receipt Quantities for Indent: {self.name} ===")
        print(f"Receipt: {receipt.name}, State: {receipt.state}")

        # Only update if picking is not done or canceled
        if receipt.state not in ['done', 'cancel']:
            for summary in self.pt_product_summary_ids:
                product = summary.product_id
                pi_quantity = summary.pi_quantity

                move_lines = receipt.move_ids_without_package.filtered(lambda m: m.product_id == product)
                if not move_lines:
                    print(f"⚠️ No move lines found for product {product.name} in receipt {receipt.name}")
                    continue

                for move in move_lines:
                    if pi_quantity > move.product_uom_qty:
                        raise UserError(
                            f"PI Quantity ({pi_quantity}) for product {product.display_name} "
                            f"cannot exceed Ordered Quantity ({move.product_uom_qty})."
                        )

                    print(
                        f"Updating move line {move.id} for product {product.name}: "
                        f"{getattr(move, 'quantity', 'N/A')} -> {pi_quantity}"
                    )
                    move.quantity = pi_quantity  # update your custom quantity field

            self.state = 'done'
            print("✅ Receipt quantities updated successfully!")
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': 'Receipt Quantities Updated Successfully',
                    'type': 'rainbow_man',
                }
            }
        else:
            raise UserError(f"Picking {receipt.name} is already in state '{receipt.state}'. Cannot update quantities.")

    def update_store_purchase(self):
        for rec in self.pt_order_line_ids:
            company = self.env['stock.warehouse'].search([('name', '=', rec.store_id.name)], limit=1)
            store = self.env['nhcl.ho.store.master'].search(
                [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True),
                 ('nhcl_store_name', '=', company.id)
                 ]
            )
            if not store:
                raise UserError(_("Store not found for the selected company: %s") % rec.store_id.name)
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_purchase_indent_search_ulr = f"http://{store_ip}:{store_port}/api/purchase.order/search"
                purchase_indent_domain = [('name', '=', rec.purchase_indent_id.partner_ref)]
                store_purchase_indent_data_url = f"{store_purchase_indent_search_ulr}?domain={purchase_indent_domain}"
                store_purchase_indent_data = requests.get(store_purchase_indent_data_url, headers=headers_source).json()
                purchase_indent = store_purchase_indent_data.get("data")
                if purchase_indent:
                    indent = purchase_indent[0]["id"]
                    lot_data = {
                        'nhcl_store_status': True,

                    }
                    store_purchase_indent_url_data = f"http://{store_ip}:{store_port}/api/purchase.order/{indent}"
                    response = requests.put(store_purchase_indent_url_data, headers=headers_source, json=lot_data)
                    response.raise_for_status()
                    response_json = response.json()
                    message = response_json.get("message", "No message provided")
                    response_code = response_json.get("responseCode", "No response code provided")
                    if not response_json.get("success", True):
                        store.create_cmr_transaction_server_replication_log('success', message)
                        store.create_cmr_transaction_replication_log(response_json['object_name'], self.id, 200,
                                                                           'add', 'failure', message)
                    else:
                        store.create_cmr_transaction_server_replication_log('success', message)
                        store.create_cmr_transaction_replication_log(response_json['object_name'], self.id, 200,
                                                                           'add', 'success',
                                                                           f"Successfully Updated Status: {message}")

                else:
                    store.create_cmr_transaction_replication_log('purchase.order', self.id, 200,
                                                                       'add', 'failure',
                                                                       f"{self.name, rec.purchase_indent_id.name}Indent Not found")

            except requests.exceptions.RequestException as e:
                store.create_cmr_transaction_server_replication_log('failure', e)