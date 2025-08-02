from odoo import models, fields, api, _, exceptions
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
from datetime import timedelta


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
    allow_import_order = fields.Boolean('Allow Import', compute='_compute_import_order_lines')
    order_qty = fields.Float(string="Ordered Qty", compute="_compute_qty", store=True)
    received_qty = fields.Float(string="Received Qty", compute="_compute_qty", store=True)
    pending_qty = fields.Float(string="Pending Qty", compute="_compute_qty", store=True)

    @api.depends("order_line.product_qty", "order_line.qty_received")
    def _compute_qty(self):
        for po in self:
            po.order_qty = sum(po.order_line.mapped("product_qty"))
            po.received_qty = sum(po.order_line.mapped("qty_received"))
            po.pending_qty = po.order_qty - po.received_qty

    def _compute_import_order_lines(self):
        if self.env.user and self.env.user.import_purchase_order_line == True:
            self.allow_import_order = True
        else:
            self.allow_import_order = False

    @api.onchange('nhcl_po_type')
    def _onchange_fun_import_order(self):
        self._compute_import_order_lines()

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
                zone_ids = order.order_line.mapped('zone_id')
                unique_zone_ids = set(zone_ids)
                if len(unique_zone_ids) == 1:
                    zone_id = list(unique_zone_ids)[0]
                    if zone_id:
                        order.ho_status = 'logistic'
                        self.env['logistic.screen.data'].create({
                            'vendor': order.partner_id.id,
                            'po_number': order.id,
                            'gst_no': order.partner_id.vat,
                            'no_of_quantity': order.sum_of_quantites,
                            'consignor': order.partner_id.id,
                            'zone_id': zone_id.id,
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
    prod_serial_no = fields.Many2many('stock.lot', string='Lot/Serial No', copy=False)
    prod_barcode = fields.Char('Barcode', copy=False)
    zone_id = fields.Many2one('placement.master.data', string='Zone', copy=False)
    pending_qty = fields.Float(string="Pending Qty", compute="_compute_qty", store=True)
    family = fields.Many2one('product.category', string="Family", domain="[('parent_id','=',False)]")
    category = fields.Many2one(
        'product.category',
        string="Category",
        domain="[('parent_id','=',family)]"
    )

    class_level_id = fields.Many2one(
        'product.category',
        string="Class",
        domain="[('parent_id','=',category)]"
    )

    brick = fields.Many2one(
        'product.category',
        string="Brick",
        domain="[('parent_id','=',class_level_id)]"
    )

    @api.depends("product_qty", "qty_received")
    def _compute_qty(self):
        for po in self:
            po.pending_qty = po.product_qty - po.qty_received

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
