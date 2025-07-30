from odoo import models, fields, api,_
from odoo.exceptions import ValidationError, UserError
from collections import defaultdict
from datetime import datetime
import requests


class InternalPurchaseIndent(models.Model):
    _name = 'internal.purchase.indent'
    _description = 'Internal Purchase Indent'
    _rec_name = 'name'





    name = fields.Char(string='Indent Number', required=True, copy=False, readonly=True, default='New')
    order_line_ids = fields.One2many(
        'internal.purchase.indent.orderline',
        'indent_id',
        string="PO Lines"
    )


    approval_request_id = fields.Many2one("approval.request",string="PI Request")

    product_summary_ids = fields.One2many(
        'product.summary',
        'indent_sum_id',
        string="Product Summary Data"
    )

    company_id = fields.Many2one("res.company",default=lambda self: self.env.company)

    request_owner_id = fields.Many2one("res.users", check_company=True, default=lambda self: self.env.user,)
    store = fields.Many2many("res.company", string="Store", domain="[('nhcl_company_bool', '=', False)]",)
    from_date = fields.Date(string="From Date", required=True,)
    to_date = fields.Date(string="To Date",required=True)
    product_category = fields.Many2one(
        "product.category",
        string="Product Category",
        domain="[('parent_id.parent_id.parent_id','!=',False)]", required=True,
    )

    product_variant = fields.Many2many(
        'product.product',
        string="Product",
        domain="[('categ_id', '=', product_category)]")

    product_variant_tags = fields.Char(string='Product Variant Tags', compute='_get_variant_tags', store=True)
    store_tags = fields.Char(string='Store Tags', compute='_get_store_tags', store=True)


    @api.depends('product_variant')
    def _get_variant_tags(self):
        for rec in self:
            if rec.product_variant:
                product_variant_tags= ','.join([p.display_name for p in rec.product_variant])
            else:
                product_variant_tags = ''
            rec.product_variant_tags=product_variant_tags

    @api.depends('store')
    def _get_store_tags(self):
        for rec in self:
            if rec.store:
                store_tags = ','.join([p.display_name for p in rec.store])
            else:
                store_tags = ''
            rec.store_tags = store_tags

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

    def action_load_po_lines(self):
        self.ensure_one()
        self.order_line_ids.unlink()
        self.product_summary_ids.unlink()

        domain = [
            ('state', '=', 'draft'),
            ('order_id.nhcl_po_type', 'in', ['inter_state', 'intra_state']),
            ('date_order', '>=', self.from_date),
            ('date_order', '<=', self.to_date),
            ('company_id.nhcl_company_bool','=',False)
        ]

        if self.store:
            domain.append(('company_id', 'in', self.store.ids))

        if self.product_category:
            domain.append(('product_id.categ_id', '=', self.product_category.id))

        if self.product_variant:
            domain.append(('product_id', '=', self.product_variant.ids))

        purchase_order_lines = self.env['purchase.order.line'].sudo().search(domain)

        # Get PO lines already linked to any indent (where indent_id is not False)
        linked_po_line_ids = self.env['internal.purchase.indent.orderline'].sudo().search([
            ('indent_id', '!=', False)
        ]).mapped('po_line_id.id')

        # Filter PO lines not linked to any indent
        new_po_lines = purchase_order_lines.filtered(lambda l: l.id not in linked_po_line_ids)



        if not new_po_lines:
            raise UserError("No PO Indents in the given date range")




        # Build new lines
        line_commands = []
        summary_dict = defaultdict(float)

        for line in new_po_lines:
            line_commands.append((0, 0, {
                'po_line_id': line.id,
                'indent_id': self.id,
            }))
            summary_dict[line.product_id] += line.product_qty

        self.order_line_ids = line_commands

        self.product_summary_ids = [
            (0, 0, {
                'product_id': product.id,
                'pi_quantity': total_qty,
                'on_hand': product.qty_available,
                'forecast_quantity': product.virtual_available,
                'incoming_quantity': product.incoming_qty,
                'outgoing_quantity': product.outgoing_qty,
                'as_of_date': datetime.now(),
                'indent_sum_id': self.id,
            }) for product, total_qty in summary_dict.items()
        ]



        return



    @api.onchange('select_all')
    def _onchange_select_all(self):
        """ On changing the 'select_all' field, set all individual records' 'select' fields accordingly """
        for line in self.product_summary_ids:
            line.select = self.select_all

    def create_pi_request(self):
        self.ensure_one()

        pi_request = self.env['approval.request']

        if not self.vendor:
            raise UserError("Select a vendor first.")


        selected_lines = self.product_summary_ids.filtered(lambda line: line.select)

        if not selected_lines:
            raise UserError("No lines selected.")


        invalid_lines = selected_lines.filtered(lambda line: line.quantity_to_raise == 0)
        if invalid_lines:
            raise UserError("Quantity to raise cannot be 0 for selected lines.")

        # Fetch the approval category
        approval_category = self.env["approval.category"].search([('approval_type', '=', 'purchase')], limit=1)

        # Create the PI request
        reuest_id = pi_request.create({
            'request_owner_id': self.request_owner_id.id,
            'pi_type': "ho_operation",
            'category_id': approval_category.id,
            'partner_id': self.vendor.id,
            'street': self.vendor.street,
            'street2': self.vendor.street2,
            'zip': self.vendor.zip,
            'city': self.vendor.city,
            'state_id': self.vendor.state_id.id,
            'country_id': self.vendor.country_id.id,
            'date': datetime.now(),
            'vendor_gst':  self.vendor.vat,
            'product_line_ids': [
                                    (5, 0, 0)  # Clear existing product lines
                                ] + [
                                    (0, 0, {
                                        'product_id': line.product_id.id,
                                        'quantity': line.quantity_to_raise,
                                        'family': line.product_id.categ_id.parent_id.parent_id.parent_id.id,
                                        'category': line.product_id.categ_id.parent_id.parent_id.id,
                                        'Class': line.product_id.categ_id.parent_id.id,
                                        'brick': line.product_id.categ_id.id,
                                    }) for line in selected_lines
                                ]
        })



        self.approval_request_id = reuest_id.id
        self.state = 'progress'

    def action_cancel(self):
        self.ensure_one()
        self.write({'state': 'cancel'})

    def action_confirm(self):
        self.ensure_one()
        self.write({'state': 'done'})

    def update_store_purchase(self):
        for rec in self.order_line_ids:
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
