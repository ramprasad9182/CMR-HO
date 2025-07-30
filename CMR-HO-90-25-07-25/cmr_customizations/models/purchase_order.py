from odoo import models, fields, api, _, exceptions
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from datetime import date, timedelta


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    po_approval = fields.Integer("Approval")
    state = fields.Selection([
        ('draft', 'Purchase Indent'),
        ('sent', 'Purchase Indent Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancelled')
    ], string='Status', tracking=True)
    nhcl_po_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'), ('sub_contract', 'Sub Contracting'), ('inter_state','Inter State'), ('intra_state', 'Intra State'), ('others', 'Others')],
        string='PO Type', tracking=True)
    dummy_po_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'),
         ('others', 'Others')], string='Dummy PO Type', compute='_onchange_nhcl_po_type')
    sum_of_quantites = fields.Float(string="Sum of Quantity", compute='_get_sum_of_quantity', tracking=True)
    logistic_count = fields.Integer(string="Count",compute='_compute_logistic_count')
    transport_count = fields.Integer(string="Count",compute='_compute_transport_count')
    delivery_count = fields.Integer(string="Count",compute='_compute_delivery_count')
    parcel_count = fields.Integer(string="Count",compute='_compute_parcel_count')
    verify_po = fields.Boolean(string='Verify PO', copy=False, default=False)
    receipt_invisible = fields.Integer(string="Receipt Invisible", compute='_compute_receipt_invisible')
    ho_status = fields.Selection(
        [('logistic', 'Logistic Entry'), ('transport', 'Transport Check'),
         ('delivery', 'Delivery Check')], string='Logistic Status', tracking=True)
    start_date = fields.Date(string='Start Date', copy=False, tracking=True, default=fields.Date.today)
    end_date = fields.Date(string='End Date', copy=False, tracking=True)
    due_days = fields.Integer(string='Due days', copy=False, tracking=True, compute='_compute_due_days', store=True)
    renewal_date = fields.Date(string='Renewal Date', copy=False, tracking=True)
    advt_status = fields.Selection(
        [('new', 'New'), ('closed', 'Closed'),
         ('renewed', 'Renewed')], string='Advt. Status', tracking=True, copy=False)
    disco = fields.Float('disc')
    street = fields.Char(string="Address", related='partner_id.street', tracking=True, copy=False)
    street2 = fields.Char(related='partner_id.street2', tracking=True, copy=False)
    zip = fields.Char(change_default=True, related='partner_id.zip', tracking=True, copy=False)
    city = fields.Char(related='partner_id.city', tracking=True, copy=False)
    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict',
                               domain="[('country_id', '=?', country_id)]", related='partner_id.state_id', tracking=True, copy=False)
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict', related='partner_id.country_id', tracking=True, copy=False)
    vendor_gst = fields.Char(string="Vendor GST", related='partner_id.vat', tracking=True, copy=False)

    @api.onchange('partner_id', 'order_line')
    def trigger_the_compute_tax_id(self):
        self.ensure_one()
        self.order_line._compute_tax_id()
        self.get_payment_terms_from_vendor()

    def get_payment_terms_from_vendor(self):
        if self.partner_id and self.partner_id.property_supplier_payment_term_id:
            self.payment_term_id = self.partner_id.property_supplier_payment_term_id.id
        else:
            self.payment_term_id = False

    @api.depends('start_date', 'end_date')
    def _compute_due_days(self):
        for record in self:
            if record.start_date and record.end_date:
                start = fields.Date.from_string(record.start_date)
                end = fields.Date.from_string(record.end_date)
                record.due_days = (end - start).days
            else:
                record.due_days = 0

    @api.model
    def _check_end_date_for_alerts(self):
        # Get today's date and calculate the alert date (2 days ahead)
        today = fields.Date.today()
        alert_date = today + timedelta(days=2)

        # Search for purchase orders of type 'advertisement' that are ending in 2 days
        advertisement_orders = self.env['purchase.order'].search(
            [('nhcl_po_type', '=', 'advertisement'), ('end_date', '=', alert_date)])
        for order in advertisement_orders:
            if order.user_id and order.user_id.login:
                self.env['mail.activity'].create({
                    'res_id': order.id,  # ID of the record
                    'res_model_id': self.env.ref('purchase.model_purchase_order').id,
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'summary': 'Advertisement PO Expiring Soon',
                    'note': f"Your Advertisement Purchase Order {order.name} is expiring in 2 days (End Date: {order.end_date.strftime('%d-%m-%Y')}).",
                    'user_id': order.user_id.id,
                    'date_deadline': order.end_date - timedelta(days=2),  # Set the deadline 2 days before end date
                })
            else:
                raise UserError("Responsible User does not have email...")

    def write(self, vals):
        res = super(PurchaseOrder, self).write(vals)
        if self.nhcl_po_type == 'ho_operation':
            self.verify_draft_pi_to_po()
        return res

    def alert_on_payment_terms(self):
        today = fields.Date.today()
        purchase_orders = self.env['purchase.order'].search([('state', '=', 'purchase'), ('payment_term_id', '!=', False)])
        for order in purchase_orders:
            for invoice in order.invoice_ids.filtered(lambda inv: inv.state == 'posted'):
                if invoice.amount_residual > 0:
                    for term in order.payment_term_id.line_ids:
                        due_date = None
                        if term.delay_type == 'days_after':
                            due_date = invoice.invoice_date + relativedelta(days=term.nb_days)
                        if due_date and due_date >= today:
                            order.send_alert_to_responsible_user(invoice)
                            break

    def send_alert_to_responsible_user(self,invoice):
        """Send an alert to the responsible user of the purchase order."""
        account_invoice_group = self.env.ref('account.group_account_invoice')
        account_readonly_group = self.env.ref('account.group_account_readonly')
        account_group = self.env.ref('account.group_account_user')
        account_manager_group = self.env.ref('account.group_account_manager')
        consolidation_user_group = self.env.ref('account_consolidation.group_consolidation_user')
        account_invoice_users = self.env['res.users'].search([('groups_id', 'in', account_invoice_group.ids)])
        account_readonly_users = self.env['res.users'].search([('groups_id', 'in', account_readonly_group.ids)])
        account_users = self.env['res.users'].search([('groups_id', 'in', account_group.ids)])
        account_manager_users = self.env['res.users'].search([('groups_id', 'in', account_manager_group.ids)])
        consolidation_users = self.env['res.users'].search([('groups_id', 'in', consolidation_user_group.ids)])
        combined_list = [*account_invoice_users,*account_readonly_users,*account_users,*account_manager_users,*consolidation_users]
        odoobot_id = self.env['ir.model.data']._xmlid_to_res_id('base.partner_root')
        author = self.env['res.users'].sudo().browse(odoobot_id).partner_id
        purchase_notification_ids = []
        body = _("Purchase Order " + self._get_html_link() + " has payment terms that are due."
                 + "Invoice Number :"+ invoice._get_html_link())
        if self.user_id:
            purchase_notification_ids.append(self.user_id.partner_id.id)
        for i in combined_list:
            purchase_notification_ids.append(i.partner_id.id)
        if purchase_notification_ids:
            name = "Payment Due Alert"
            self.send_msg_to_responsible_user(purchase_notification_ids, author.id, body, name)

    def send_msg_to_responsible_user(self, user_ids, author_id, body, name):
        """
        Helper method to send a message to a channel or create a new one,
        ensuring the channel has the correct users, and remove those who shouldn't be there.
        """
        # Search for an existing channel with the given name and group type
        mail_channel = self.env['discuss.channel'].search(
            [('name', '=', name), ('channel_type', '=', 'group')],limit=1)
        if mail_channel:
            current_user_ids = mail_channel.channel_partner_ids.ids
            # Determine users to add and remove
            users_to_add = [user_id for user_id in user_ids if user_id not in current_user_ids]
            users_to_remove = [user_id for user_id in current_user_ids if user_id not in user_ids]
            # Add new users to the channel
            if users_to_add:
                mail_channel.write({
                    'channel_partner_ids': [(4, user_id) for user_id in users_to_add]
                })
            # Remove users no longer in the group
            if users_to_remove:
                mail_channel.write({
                    'channel_partner_ids': [(3, user_id) for user_id in users_to_remove]
                })
        else:
            # Create a new channel if it doesn't exist
            mail_channel = self.env['discuss.channel'].create({
                'channel_partner_ids': [(4, user_id) for user_id in user_ids],
                'channel_type': 'group',
                'name': name,
            })
        # Post the message to the channel
        mail_channel.message_post(
            author_id=author_id,
            body=body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )

    def reset_product_lines(self):
        for rec in self:
            rec.order_line.unlink()

    def _compute_logistic_count(self):
        self.logistic_count = self.env['logistic.screen.data'].search_count(
            [('po_number', '=', self.id)])

    def _compute_transport_count(self):
        self.transport_count = self.env['transport.check'].search_count(
            [('po_order_id', '=', self.id)])

    def _compute_delivery_count(self):
        self.delivery_count = self.env['delivery.check'].search_count(
            [('po_order_id', '=', self.id)])

    def _compute_parcel_count(self):
        self.parcel_count = self.env['open.parcel'].search_count(
            [('parcel_po_no', '=', self.id)])

    def _compute_receipt_invisible(self):
        self.receipt_invisible = self.env['open.parcel'].search_count(
            [('parcel_po_no', '=', self.id), ('state', '=', 'done')])

    @api.depends('nhcl_po_type')
    def _onchange_nhcl_po_type(self):
        for i in self:
            if i.nhcl_po_type == 'ho_operation':
                i.dummy_po_type = 'ho_operation'
            elif i.nhcl_po_type == 'advertisement':
                i.dummy_po_type = 'advertisement'
            elif i.nhcl_po_type == 'others':
                i.dummy_po_type = 'others'
            elif i.nhcl_po_type == 'inter_state':
                i.dummy_po_type = 'ho_operation'
            elif i.nhcl_po_type == 'intra_state':
                i.dummy_po_type = 'ho_operation'
            elif i.nhcl_po_type == 'sub_contract':
                i.dummy_po_type = 'ho_operation'
            else:
                i.dummy_po_type = ''

    def verify_draft_pi_to_po(self):
        for rec in self:
            if rec.origin and rec.state not in ['draft', 'sent'] and rec.nhcl_po_type == 'ho_operation':
                draft_pi = self.env['approval.request'].search([('name', '=', rec.origin)])
                po_product_quantities = {}
                draft_pi_product_quantities = {}
                product_names = {}
                # Summing the quantities in the Purchase Order
                for rec_line in rec.order_line:
                    product_tmpl_id = rec_line.product_id.product_tmpl_id.id
                    product_name = rec_line.product_id.product_tmpl_id.name
                    product_names[product_tmpl_id] = product_name

                    if product_tmpl_id in po_product_quantities:
                        po_product_quantities[product_tmpl_id] += rec_line.product_qty
                    else:
                        po_product_quantities[product_tmpl_id] = rec_line.product_qty
                # Summing the quantities in the Approval Request
                for line in draft_pi.product_line_ids:
                    product_tmpl_id = line.product_id.product_tmpl_id.id
                    product_name = line.product_id.product_tmpl_id.name
                    product_names[product_tmpl_id] = product_name

                    if product_tmpl_id in draft_pi_product_quantities:
                        draft_pi_product_quantities[product_tmpl_id] += line.quantity
                    else:
                        draft_pi_product_quantities[product_tmpl_id] = line.quantity
                # Compare the quantities
                all_match = True
                for product_tmpl_id, po_qty in po_product_quantities.items():
                    draft_pi_qty = draft_pi_product_quantities.get(product_tmpl_id, 0)
                    if po_qty != draft_pi_qty:
                        all_match = False
                        # Handle the mismatch case
                        raise ValidationError(f'"Mismatch for {product_names[product_tmpl_id]}: PO qty {po_qty}, Draft PI qty {draft_pi_qty}"')
                for product_tmpl_id, draft_pi_qty in draft_pi_product_quantities.items():
                    po_qty = po_product_quantities.get(product_tmpl_id, 0)
                    if po_qty != draft_pi_qty:
                        all_match = False
                        raise ValidationError(f'"Mismatch for {product_names[product_tmpl_id]}: PO qty {po_qty}, Draft PI qty {draft_pi_qty}"')
                if all_match:
                    # rec.verify_po = True
                    message = "All product quantities match between the Purchase Order and the PI."
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'message': message,
                            'type': 'success',
                            'sticky': False,
                        }
                    }


    @api.depends('order_line')
    def _get_sum_of_quantity(self):
        total_purchase = 0
        if self.order_line:
            for rec in self.order_line:
                total_purchase += rec.product_qty
                self.sum_of_quantites = total_purchase
        else:
            self.sum_of_quantites = 0

    def logistic_screen_button(self):
        for record in self:
            domain = [('po_number', '=', record.id)]

            return {
                     'name': 'Logistic Entry',
                     'res_model': 'logistic.screen.data',
                      'view_mode': 'tree,form',
                      'type': 'ir.actions.act_window',
                      'domain': domain,
             }

    def transport_check_button(self):
        for record in self:
            domain = [('po_order_id', '=', record.id)]

            return {
                'name': 'Transport Check',
                'res_model': 'transport.check',
                'view_mode': 'tree,form',
                'type': 'ir.actions.act_window',
                'domain': domain,
            }

    def delivery_check_button(self):
        for record in self:
            domain = [('po_order_id', '=', record.id)]

            return {
                'name': 'Delivery Check',
                'res_model': 'delivery.check',
                'view_mode': 'tree,form',
                'type': 'ir.actions.act_window',
                'domain': domain,
            }

    def open_parcel_button(self):
        for record in self:
            domain = [('parcel_po_no', '=', record.id)]
            return {
                'name': 'Open Parcels',
                'res_model': 'open.parcel',
                'view_mode': 'kanban,tree,form',
                'type': 'ir.actions.act_window',
                'domain': domain,
            }

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        for order in self:
            if order.state not in ['draft', 'sent', 'approval_one', 'approval_two', 'approval_three', 'approval_four']:
                continue
            order.order_line._validate_analytic_distribution()
            order._add_supplier_to_product()
            if order._approval_allowed():
                order.button_approve()
            else:
                order.write({'state': 'to approve'})
            if order.partner_id not in order.message_partner_ids:
                order.message_subscribe([order.partner_id.id])
        return res

    def button_approve(self, force=False):
        res = super(PurchaseOrder, self).button_approve()
        logistic_seq = self.env['nhcl.master.sequence'].search(
            [('nhcl_code', '=', 'logistic.screen.data'), ('nhcl_state', '=', 'activate')], limit=1)
        if not logistic_seq:
            raise exceptions.ValidationError(
                _("Configure the Logistic Screen Sequence in Settings to perform this action."))

        for order in self:
            if order.nhcl_po_type == 'ho_operation':
                order.ho_status = 'logistic'
                logistic_screen_data = self.env['logistic.screen.data'].create({
                    'vendor': order.partner_id.id,
                    'po_number': order.id,
                    'gst_no': order.partner_id.vat,
                    'no_of_quantity': order.sum_of_quantites,
                    'consignor': order.partner_id.id,
                })
        return res

    def _prepare_picking(self):
        if not self.group_id:
            self.group_id = self.group_id.create({
                'name': self.name,
                'partner_id': self.partner_id.id
            })
        if not self.partner_id.property_stock_supplier.id:
            raise UserError(_("You must set a vendor location for this partner.", self.partner_id.name))
        return {
            'picking_type_id': self.picking_type_id.id,
            'partner_id': self.partner_id.id,
            'user_id': False,
            'date': self.date_order,
            'origin': self.name,
            'location_dest_id': self._get_destination_location(),
            'location_id': self.partner_id.property_stock_supplier.id,
            'company_id': self.company_id.id,
            'state': 'draft',
            'stock_type':self.nhcl_po_type,
        }

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    serial_no = fields.Char(string="Serial No")
    product_id = fields.Many2one('product.product', string='Product Variant', domain=[('purchase_ok', '=', True)], change_default=True, index='btree_not_null')
    nhcl_pi_qty = fields.Float(string="PI Qty", copy=False, tracking=True, compute='get_pi_qty')
    hsn_code = fields.Char(string="HSN Code", related='product_template_id.l10n_in_hsn_code')
    purchase_rsp_margin = fields.Integer(string="RSP Margin", copy=False)
    purchase_category_id = fields.Many2one('product.attribute.value', string="Design",
                                           domain=[('attribute_id.name', '=', 'Design')])
    design_id = fields.Many2one('product.attribute.value', string="Design")

    @api.depends('order_id.origin')
    def get_pi_qty(self):
        for rec in self:
            rec.nhcl_pi_qty = 0.0
            if rec.order_id.origin and rec.order_id.nhcl_po_type == 'ho_operation':
                request_approval = self.env['approval.request'].search([('name', '=', rec.order_id.origin)], limit=1)
                for line in request_approval.product_line_ids:
                    if line.product_id == rec.product_id:
                        rec.nhcl_pi_qty = line.quantity  # Set the quantity if product matches
                        break

    @api.onchange('product_id')
    def _onchange_product_id_po(self):
        if self.order_id and not self.order_id.nhcl_po_type:
            # Clear the product_id and raise an error if no stock_type is selected
            self.product_id = False
            raise UserError(
                "Before picking a product, you must first choose a PI Type."
            )

    @api.onchange('price_unit', 'discount')
    def trigger_the_compute_tax_id(self):
        self.ensure_one()
        self._compute_tax_id()

    def unlink(self):
        for rec in self:
            if rec.product_id.name == 'Discount' and rec.order_id.disco > 0:
                raise UserError(
                    _("You are not allowed to unlink Discount Product; if you want to remove discount, use the Reset Discount Button!."))
            else:
                return super(PurchaseOrderLine, rec).unlink()

    @api.depends('product_id', 'company_id', 'price_unit', 'order_id.partner_id', 'discount', 'order_id.nhcl_po_type')
    def _compute_tax_id(self):
        for line in self:
            line = line.with_company(line.company_id)
            if line.order_id.nhcl_po_type == 'intra_state':
                line.taxes_id = False
                continue
            fpos = line.order_id.fiscal_position_id or line.order_id.fiscal_position_id._get_fiscal_position(
                line.order_id.partner_id)
            # filter taxes by company
            taxes = line.product_id.supplier_taxes_id._filter_taxes_by_company(line.company_id)
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
            line.taxes_id = fpos.map_tax(taxes)


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    pi_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'),('others', 'Others')],
        string='PI Type', tracking=True,default='ho_operation')
    dummy_pi_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'),
         ('others', 'Others')], string='Dummy PI Type', compute='_compute_nhcl_pi_type')
    nhcl_tax_totals_json = fields.Binary(compute='_compute_nhcl_tax_totals_json', copy=False)
    currency_id = fields.Many2one('res.currency', 'Currency', required=True, readonly=True,
                                  default=lambda self: self.env.company.currency_id.id, copy=False)
    nhcl_amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all',
                                          tracking=True, copy=False)
    nhcl_amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all', copy=False)
    nhcl_amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all', copy=False)
    fiscal_position_id = fields.Many2one('account.fiscal.position', string='Fiscal Position',
                                         domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",related="partner_id.property_account_position_id")
    from_date = fields.Date(string="From Date/తేదీ నుండి", copy=False, default=lambda self: date.today())
    to_date = fields.Date(string="To Date/తేదీ వరకు", copy=False,
                          default=lambda self: date.today() + timedelta(days=60))
    purchase_type = fields.Selection([('adhoc', 'Adhoc'), ('custom_set', 'Custom Set'),
                                      ('multiple_set', 'Multiple Set')], string='Purchase Type/కొనుగోలు రకం',
                                     tracking=True)
    vendor_id = fields.Many2one('res.partner', string='Parent Category')
    street = fields.Char(string="Address")
    street2 = fields.Char()
    zip = fields.Char(change_default=True)
    city = fields.Char()
    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict',
                               domain="[('country_id', '=?', country_id)]")
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict')
    vendor_gst = fields.Char(string="Vendor GST")
    allowed_category_ids = fields.Many2many('product.category', string='Categories', copy=False)
    request_status = fields.Selection(selection_add=[('margin_approved', 'RSP Margin Approved'), ('approved',), ])
    is_not_margin_approve = fields.Boolean('Margin Approve', copy=False)
    is_requestor = fields.Boolean(string="Requestor", compute="getting_requestor")
    rejection_reason = fields.Text(string='Rejection Reason', tracking=True)
    rejection_reason2 = fields.Text(string='Rejection Reason', tracking=True)
    date = fields.Datetime(string="Date", default=lambda self: datetime.today())

    @api.constrains('from_date', 'to_date')
    def _check_date_constraints(self):
        for record in self:
            today = date.today()
            if record.from_date != today:
                raise ValidationError("From Date must be today's date.")
            if record.date.date() != today:
                raise ValidationError("Date must be today's date.")
            if record.to_date != record.from_date + timedelta(days=60):
                raise ValidationError("To Date must be 60 days after From Date.")

    @api.depends('request_owner_id')
    def getting_requestor(self):
        for rec in self:
            if rec.request_owner_id and rec.request_owner_id.id == self.env.user.id and rec.request_status == 'refused':
                rec.is_requestor = True
            else:
                rec.is_requestor = False


    @api.onchange('request_owner_id')
    def onchange_request_owner_id(self):
        if self.request_owner_id:
            categ_ids = self.env['product.category'].search([('user_ids', 'in', self.request_owner_id.ids)])
            category_lst = []
            for categ_id in categ_ids:
                if categ_id and not categ_id.parent_id:
                    category_lst.append(categ_id.id)
            self.allowed_category_ids = category_lst

    def action_rsp_margin_approve(self):
        if not self.env.user.has_group('cmr_customizations.group_rsp_margin_approver'):
            raise ValidationError("You don't have access to approve the RSP Margin.")
        approvers = self.approver_ids
        if self.approver_sequence:
            approvers = approvers.filtered(lambda a: a.status in ['new', 'pending', 'waiting'])

            approvers[1:].sudo().write({'status': 'waiting'})
            approvers = approvers[0] if approvers and approvers[0].status != 'pending' else self.env[
                'approval.approver']
        else:
            approvers = approvers.filtered(lambda a: a.status == 'new')

        approvers._create_activity()
        approvers.sudo().write({'status': 'pending'})
        self.sudo().write({'date_confirmed': fields.Datetime.now()})

        self.request_status = 'margin_approved'
        self.is_not_margin_approve = True

    def select_product_ids(self):
        allowed_ids = []
        for allowed_category_id in self.allowed_category_ids:
            categ_ids = self.env['product.category'].search([('parent_id', 'ilike', allowed_category_id.name)])
            categ_ids_lst = []
            for categ_id in categ_ids:
                # product_ids = self.env['product.template'].search([('categ_id','=',categ_id.id),('detailed_type','!=','service')])
                if categ_id.id not in categ_ids_lst:
                    categ_ids_lst.append(categ_id.id)
                    allowed_ids.append(categ_id.id)
        return {
            'name': 'Select Products',
            'type': 'ir.actions.act_window',
            'res_model': 'multi.product.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.id,
                'default_categ_ids': allowed_ids,
            }
        }


    def select_product_direct_ids(self):
        allowed_ids = []
        for allowed_category_id in self.allowed_category_ids:
            categ_ids = self.env['product.category'].search([('parent_id', 'ilike', allowed_category_id.name)])
            categ_ids_lst = []
            for categ_id in categ_ids:
                # product_ids = self.env['product.template'].search([('categ_id','=',categ_id.id),('detailed_type','!=','service')])
                if categ_id.id not in categ_ids_lst:
                    categ_ids_lst.append(categ_id.id)
                    allowed_ids.append(categ_id.id)
        return {
            'name': 'Select Products',
            'type': 'ir.actions.act_window',
            'res_model': 'multi.product.wizard.direct',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_request_id': self.id,
                'default_categ_ids': allowed_ids,
            }
        }


    @api.depends('partner_id')
    @api.onchange('partner_id', 'company_id','vendor_id')
    def onchange_partner_id(self):
        # Ensures all properties and fiscal positions
        # are taken with the company of the order
        # if not defined, with_company doesn't change anything.
        self = self.with_company(self.company_id)
        default_currency = self._context.get("default_currency_id")
        if not self.partner_id:
            self.fiscal_position_id = False
            self.currency_id = default_currency or self.env.company.currency_id.id
        else:
            self.fiscal_position_id = self.env['account.fiscal.position']._get_fiscal_position(self.partner_id)
            self.currency_id = default_currency or self.env.company.currency_id.id
            self.vendor_gst = self.partner_id.vat
            self.street = self.partner_id.street
            self.street2 = self.partner_id.street2
            self.zip = self.partner_id.zip
            self.city = self.partner_id.city
            self.state_id = self.partner_id.state_id.id
            self.country_id = self.partner_id.country_id.id
        return {}

    @api.onchange('fiscal_position_id', 'company_id')
    def _compute_tax_id(self):
        """
        Trigger the recompute of the taxes if the fiscal position is changed on the PO.
        """
        self.product_line_ids._compute_tax_id()

    @api.depends('product_line_ids.nhcl_price_total')
    def _amount_all(self):
        for order in self:
            order_lines = order.product_line_ids
            amount_untaxed = amount_tax = 0.00
            print(order_lines, 'order')
            if order_lines:
                tax_results = self.env['account.tax']._compute_taxes([
                    line._convert_to_tax_base_line_dict()
                    for line in order_lines
                ])
                totals = tax_results['totals']
                amount_untaxed = totals.get(order.currency_id, {}).get('nhcl_amount_untaxed', 0.0)
                amount_tax = totals.get(order.currency_id, {}).get('nhcl_amount_tax', 0.0)
            order.nhcl_amount_untaxed = amount_untaxed
            order.nhcl_amount_tax = amount_tax
            order.nhcl_amount_total = order.nhcl_amount_untaxed + order.nhcl_amount_tax

    @api.depends('product_line_ids.nhcl_taxes_id', 'product_line_ids.nhcl_price_total', 'nhcl_amount_total',
                 'nhcl_amount_untaxed')
    def _compute_nhcl_tax_totals_json(self):
        for order in self:
            order.nhcl_tax_totals_json = self.env['account.tax']._prepare_tax_totals(
                [x._convert_to_tax_base_line_dict() for x in order.product_line_ids],
                order.currency_id or order.nhcl_company_id.currency_id,
            )

    @api.depends('pi_type')
    def _compute_nhcl_pi_type(self):
        if self.pi_type == 'ho_operation':
            self.dummy_pi_type = 'ho_operation'
        elif self.pi_type == 'advertisement':
            self.dummy_pi_type = 'advertisement'
        elif self.pi_type == 'others':
            self.dummy_pi_type = 'others'
        else:
            self.dummy_pi_type = ''

    def action_create_purchase_orders(self):
        """Create and/or modify Purchase Orders."""
        self.ensure_one()
        # self.product_line_ids._check_products_vendor()
        new_purchase_order = self.env['purchase.order']

        for line in self.product_line_ids:
            seller = line._get_seller_id()
            vendor = self.partner_id

            # Always create a new purchase order, regardless of existing lines/orders.
            po_vals = line._get_purchase_order_values(vendor)
            if not new_purchase_order:
                new_purchase_order = self.env['purchase.order'].create(po_vals)

            po_line_vals = self.env['purchase.order.line']._prepare_purchase_order_line(
                line.product_id,
                line.quantity,
                line.product_uom_id,
                line.company_id,
                seller,
                new_purchase_order,
            )
            if line.unit_price:
                po_line_vals['price_unit'] = line.unit_price
                po_line_vals['purchase_rsp_margin'] = line.enter_rsp_margin
                po_line_vals['purchase_category_id'] = line.design_category_id.id
                po_line_vals['design_id'] = line.design_category_id.id
            new_po_line = self.env['purchase.order.line'].create(po_line_vals)
            line.purchase_order_line_id = new_po_line.id
            new_purchase_order.order_line = [(4, new_po_line.id)]
            new_purchase_order.order_line._compute_tax_id()

            # Add the request name to the purchase order `origin` field.
            new_origin = set([self.name])
            if new_purchase_order.origin:
                missing_origin = new_origin - set(new_purchase_order.origin.split(', '))
                if missing_origin:
                    new_purchase_order.write(
                        {'origin': new_purchase_order.origin + ', ' + ', '.join(missing_origin)})
            else:
                new_purchase_order.write({'origin': ', '.join(new_origin)})

            # Call _compute_tax_id on the new purchase order line after it's created
            new_purchase_order.order_line._compute_tax_id()

    def open_rejection_manager_wizard(self):
        return {
            'name': 'Reject Request',
            'type': 'ir.actions.act_window',
            'res_model': 'approval.rejection.wizard2',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_approval_id': self.id,
            },
        }


    def open_rejection_wizard(self):
        return {
            'name': 'Reject Request',
            'type': 'ir.actions.act_window',
            'res_model': 'approval.rejection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_approval_id': self.id,
            },
        }

    def nhcl_approver_reject(self):
        self.write({
            'request_status':'refused'
        })


    def action_confirm(self):
        self.ensure_one()
        for rec in self:
            for line in rec.product_line_ids:
                if line.unit_price <= 0:
                    raise ValidationError("Unit Price should not be Zero.")
                if line.enter_rsp_margin <= 0:
                    raise ValidationError("RSP Margin should not be Zero.")
                if line.pi_rsp_price <= 0:
                    raise ValidationError("RSP should not be Zero.")
                if line.pi_mrp_price <= 0:
                    raise ValidationError("MRP should not be Zero.")
            if rec.category_id.manager_approval == 'required':
                employee = self.env['hr.employee'].search([('user_id', '=', rec.request_owner_id.id)], limit=1)
                if not employee.parent_id:
                    raise UserError(
                        _('This request needs to be approved by your manager. There is no manager linked to your employee profile.'))
                if not employee.parent_id.user_id:
                    raise UserError(
                        _('This request needs to be approved by your manager. There is no user linked to your manager.'))
                if not rec.approver_ids.filtered(lambda a: a.user_id.id == employee.parent_id.user_id.id):
                    raise UserError(
                        _('This request needs to be approved by your manager. Your manager is not in the approvers list.'))
            if len(rec.approver_ids) < rec.approval_minimum:
                raise UserError(
                    _("You have to add at least %s approvers to confirm your request.", rec.approval_minimum))
            if rec.requirer_document == 'required' and not rec.attachment_number:
                raise UserError(_("You have to attach at lease one document."))
            if rec.approval_type == 'purchase' and not rec.product_line_ids:
                raise UserError(_("You cannot create an empty purchase request."))

            product_lines = rec.product_line_ids.filtered(lambda x: x.enter_rsp_margin < x.default_rsp_margin)
            if product_lines:
                approver_ids = self.env.ref('cmr_customizations.group_rsp_margin_approver').users
                for approver in approver_ids:
                    rec.activity_schedule(
                        'approvals.mail_activity_data_approval',
                        user_id=approver.id)
            else:
                approvers = rec.approver_ids
                if rec.approver_sequence:
                    approvers = approvers.filtered(lambda a: a.status in ['new', 'pending', 'waiting'])

                    approvers[1:].sudo().write({'status': 'waiting'})
                    approvers = approvers[0] if approvers and approvers[0].status != 'pending' else self.env[
                        'approval.approver']
                else:
                    approvers = approvers.filtered(lambda a: a.status == 'new')

                approvers._create_activity()
                approvers.sudo().write({'status': 'pending'})
                rec.is_not_margin_approve = True
            rec.sudo().write({'date_confirmed': fields.Datetime.now(), 'request_status': 'pending'})


    def default_get(self, fields_list):
        res = super(ApprovalRequest, self).default_get(fields_list)
        if 'terms_conditions' in fields_list:
            res['terms_conditions'] = ("Terms & Conditions \n"
                            "1. GST  : 18% Extra As Applicable. \n"
                            "2. Packing  : Included with Polythene Sheet. \n"
                            "3. Payment Terms for Supply : 50% advance with PO, 50 % Agreement.\n"
                            "4. Doors Installation  : Included.\n"
                            "5. Transportation  : Extra.\n"
                            "6. Delivery period  : in 40 days.\n"
                            "7. Warranty  : One year.\n"
                            " For CMR Textiles and Jewellers Pvt Ltd.\n"
                            " Authorized Signatory \n")
        return res


    def reset_approval_product_lines(self):
        for rec in self.product_line_ids:
            rec.unlink()



class ApprovalProductLine(models.Model):
    _inherit = 'approval.product.line'

    unit_price = fields.Float(string='Cost Price/ ధర', copy=False)
    nhcl_pr_line_id = fields.Many2one('approval.request', string='Ref Request Id')
    nhcl_price_total = fields.Monetary(compute='_compute_amount', string='Total(Tax inc) /టోటల్ విత్ టాక్స్', store=True)
    nhcl_price_subtotal = fields.Monetary(compute='_compute_amount', string='Total(Tax exclu) /టోటల్ వితౌట్ టాక్స్',
                                          store=True)
    nhcl_price_tax = fields.Float(compute='_compute_amount', string='Tax/టాక్స్', store=True)
    nhcl_taxes_id = fields.Many2many('account.tax', string='Tax/టాక్స్',
                                     domain=['|', ('active', '=', False), ('active', '=', True)])
    currency_id = fields.Many2one("res.currency", string="Currency", required=True,
                                  related='nhcl_pr_line_id.currency_id')
    # nhcl_price_untaxed = fields.Monetary(compute='price_with_tax', string='Total(Incl.tax)/టోటల్ విత్ టాక్స్',
    #                                      store=True)
    family = fields.Many2one('product.category', string="Family/ఫ్యామిలీ", domain="[('parent_id','=',False)]")
    category = fields.Many2one(
        'product.category',
        string="Category/కేటగిరీ",
        domain="[('parent_id','=',family)]"
    )

    Class = fields.Many2one(
        'product.category',
        string="Class/క్లాస్",
        domain="[('parent_id','=',category)]"
    )

    brick = fields.Many2one(
        'product.category',
        string="Brick/బ్రిక్",
        domain="[('parent_id','=',Class)]"
    )
    product_id = fields.Many2one(
        'product.product',
        string="Products",
        check_company=True,
        domain="[('categ_id','=', brick), ('product_tmpl_id.nhcl_type','=', parent.dummy_pi_type),('detailed_type','!=','service')]"
    )
    nhcl_hsn_code = fields.Char(related='product_id.product_tmpl_id.l10n_in_hsn_code')
    product_domain = fields.Char(compute="_compute_product_domain")

    pi_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'), ('others', 'Others')],
        string='PI Type',
        related='approval_request_id.pi_type',  # Assuming a relation exists
        store=True,
    )
    default_rsp_margin = fields.Integer(string="Default Margin", copy=False)
    enter_rsp_margin = fields.Integer(string="Enter Margin", copy=False)
    pi_rsp_price = fields.Float(string="RSP Price", copy=False)
    pi_mrp_price = fields.Float(string="MRP Price", copy=False)
    image = fields.Image(string="Image")
    approval_attribute_id = fields.Many2one('product.attribute', string="Attribute", copy=False, compute='get_design',
                                            store=True)
    design_category_id = fields.Many2one('product.attribute.value', string="Design")

    @api.depends('product_id')
    def get_design(self):
        for i in self:
            attribute = self.env['product.attribute'].search([('name', '=', 'Design')])
            if attribute:
                i.approval_attribute_id = attribute.id
            else:
                i.approval_attribute_id = []

    @api.onchange('unit_price')
    def onchange_default_rsp_margin(self):
        for rec in self:
            if rec.product_id.categ_id.parent_id.parent_id.parent_id.product_category_margin_ids:
                for line in rec.product_id.categ_id.parent_id.parent_id.parent_id.product_category_margin_ids:
                    if line.from_range <= rec.unit_price <= line.to_range:
                        rec.default_rsp_margin = line.margin

    @api.onchange('enter_rsp_margin')
    def onchange_enter_rsp_margin(self):
        for rec in self:
            base_price = rec.unit_price or 0
            margin_price = (rec.enter_rsp_margin / 100) * base_price if rec.enter_rsp_margin else 0
            temp_price = round(base_price + margin_price)
            if temp_price:
                last_two_digits = temp_price % 100
                if last_two_digits < 50:
                    temp_price = temp_price - last_two_digits + 49
                else:
                    temp_price = temp_price - last_two_digits + 99

                rec.pi_rsp_price = temp_price
            else:
                rec.pi_rsp_price = 0

    @api.onchange('pi_rsp_price')
    def onchange_pi_mrp_price(self):
        for rec in self:
            rec.pi_mrp_price = 0
            if not rec.product_id:
                return

            if not rec.pi_rsp_price or rec.pi_rsp_price <= 0:
                return {
                    'warning': {
                        'title': 'Invalid Price',
                        'message': 'Please enter a valid RSP price greater than zero.'
                    }
                }

            category = rec.product_id.categ_id
            if not (
                    category and category.parent_id and category.parent_id.parent_id and category.parent_id.parent_id.parent_id):
                return {
                    'warning': {
                        'title': 'Category Error',
                        'message': 'Product category hierarchy is incomplete.'
                    }
                }

            mrp_lines = category.parent_id.parent_id.parent_id.product_category_mrp_ids
            if not mrp_lines:
                return {
                    'warning': {
                        'title': 'MRP Setup Missing',
                        'message': 'No MRP rules configured in the product category.'
                    }
                }
            for line in mrp_lines:
                if line.from_range <= rec.pi_rsp_price <= line.to_range:
                    margin = line.margin or 0
                    if margin != 0:
                        margin_price = (margin / 100.0) * rec.pi_rsp_price
                        temp_price = round(rec.pi_rsp_price + margin_price)
                        if temp_price:
                            last_two = temp_price % 100
                            if last_two < 50:
                                rec.pi_mrp_price = temp_price - last_two + 49
                            else:
                                rec.pi_mrp_price = temp_price - last_two + 99
                    return
            return {
                'warning': {
                    'title': 'No Match Found',
                    'message': 'No matching MRP range was found for the entered RSP price.'
                }
            }

    @api.depends('brick', 'pi_type', 'approval_request_id.allowed_category_ids')
    def _compute_product_domain(self):
        for record in self:
            domain = [('type', '!=', 'service')]
            # Add brick filter
            if record.brick:
                domain.append(('categ_id', '=', record.brick.id))
            # Add PI type filter
            if record.pi_type == 'advertisement':
                domain.append(('nhcl_type', '=', 'advertisement'))
            elif record.pi_type == 'others':
                domain.append(('nhcl_type', '=', 'others'))
            # Optimize allowed categories
            allowed_category_ids = record.approval_request_id.allowed_category_ids
            if allowed_category_ids:
                # Get all matching subcategories in one go
                first_child_categs = self.env['product.category'].search([
                    ('parent_id.name', '=', allowed_category_ids.mapped('name'))
                ])
                second_child_categs = self.env['product.category'].search([
                    ('parent_id.name', '=', first_child_categs.mapped('name'))
                ])
                third_child_categs = self.env['product.category'].search([
                    ('parent_id.name', '=', second_child_categs.mapped('name'))
                ])
                # Combine allowed categories and their children
                all_categ_ids = list(set(allowed_category_ids.ids + third_child_categs.ids))
                # Build product domain based on categories only (not full product search)
                domain.append(('categ_id', 'in', list(set(all_categ_ids))))
            record.product_domain = str(domain)


    @api.onchange('family')
    def _onchange_family(self):
        self.category = False
        self.Class = False
        self.brick = False
        self.product_id = False

    @api.onchange('category')
    def _onchange_category(self):
        self.Class = False
        self.brick = False
        self.product_id = False

    @api.onchange('Class')
    def _onchange_class(self):
        self.brick = False
        self.product_id = False

    @api.onchange('unit_price','product_id')
    def trigger_the_compute_tax_id(self):
        self.ensure_one()
        self._compute_tax_id()

    @api.depends('product_id', 'company_id', 'unit_price', 'approval_request_id.partner_id')
    def _compute_tax_id(self):
        for line in self:
            line = line.with_company(line.company_id)
            fpos = line.approval_request_id.fiscal_position_id or line.approval_request_id.fiscal_position_id._get_fiscal_position(
                line.approval_request_id.partner_id)
            # filter taxes by company
            taxes = line.product_id.supplier_taxes_id._filter_taxes_by_company(line.company_id)
            if len(taxes) >= 2:
                for tax in taxes:
                    if tax.min_amount <= line.unit_price <= tax.max_amount:
                        taxes = tax
                        break
            line.nhcl_taxes_id = fpos.map_tax(taxes)

    @api.depends('quantity', 'unit_price', 'nhcl_taxes_id')
    def _compute_amount(self):
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes([line._convert_to_tax_base_line_dict()])
            print('1st', tax_results)
            totals = next(iter(tax_results['totals'].values()))
            print(totals, 'Totals')
            amount_untaxed = totals['amount_untaxed']
            amount_tax = sum(tax_line['tax_amount'] for tax_line in tax_results.get('tax_lines_to_add', []))

            print(f"amount_untaxed: {amount_untaxed}, amount_tax: {amount_tax}")
            # amount_tax = sum(tax['tax_amount'] for tax in tax_results['tax_lines_to_add'])
            line.update({
                'nhcl_price_subtotal': amount_untaxed,
                'nhcl_price_tax': amount_tax,
                'nhcl_price_total': amount_untaxed + amount_tax,
            })

    @api.depends('quantity', 'unit_price')
    def price_with_tax(self):
        """Compute the price without tax as quantity * unit_price."""
        for line in self:
            if line.quantity and line.unit_price:
                line.nhcl_price_untaxed = line.quantity * line.unit_price
            else:
                line.nhcl_price_untaxed = 0.0

    # updating the price unit,currency,req qty,product,partner
    def _convert_to_tax_base_line_dict(self):
        # Hook method to returns the different argument values for the
        # compute_all method, due to the fact that discounts mechanism
        # is not implemented yet on the purchase orders.
        # This method should disappear as soon as this feature is
        # also introduced like in the sales module.
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            price_unit=self.unit_price,
            currency=self.nhcl_pr_line_id.currency_id,
            quantity=self.quantity,
            product=self.product_id,
            taxes=self.nhcl_taxes_id,
            price_subtotal=self.nhcl_price_subtotal,
        )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.approval_request_id and not self.approval_request_id.pi_type:
            # Clear the product_id and raise an error if no stock_type is selected
            self.product_id = False
            raise ValidationError("You must select a PI Type before selecting a product.")
        if self.approval_request_id and not self.approval_request_id.fiscal_position_id:
            raise ValidationError("You must select a Fiscal Position before selecting a product.")

    def _get_purchase_order_values(self, vendor):
        """ Get some values used to create a purchase order.
        Called in approval.request `action_create_purchase_orders`.

        :param vendor: a res.partner record
        :return: dict of values
        """
        self.ensure_one()
        vals = {
            'origin': self.approval_request_id.name,
            'nhcl_po_type': self.approval_request_id.pi_type,
            'partner_id': vendor.id,
            'company_id': self.company_id.id,
            'payment_term_id': vendor.property_supplier_payment_term_id.id,
            'fiscal_position_id':self.env['account.fiscal.position']._get_fiscal_position(vendor).id,
        }
        return vals