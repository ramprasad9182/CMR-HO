from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta, datetime


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
    allow_import_order = fields.Boolean('Allow Import', compute='_compute_import_approval_lines')
    terms_conditions = fields.Text(string="Terms and Conditions")

    def _compute_import_approval_lines(self):
        if self.env.user and self.env.user.import_approval_line == True:
            self.allow_import_order = True
        else:
            self.allow_import_order = False

    @api.onchange('pi_type')
    def _onchange_fun_import_approvals(self):
        self._compute_import_approval_lines()

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
                po_line_vals['zone_id'] = line.zone_id.id
                po_line_vals['category'] = line.category.id
                po_line_vals['class_level_id'] = line.Class.id
                po_line_vals['brick'] = line.brick.id
                po_line_vals['family'] = line.family.id
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
    prod_serial_no = fields.Many2many('stock.lot', string='Lot/Serial No', copy=False)
    prod_barcode = fields.Char('Barcode', copy=False)
    zone_id = fields.Many2one('placement.master.data', string='Zone', copy=False)
    nhcl_margin_rsp_type = fields.Selection([('margin', 'Margin'), ('rsp', 'RSP')],
                                            string='RSP Margin Type', default='', copy=False)


    @api.depends('product_id')
    def get_design(self):
        for i in self:
            attribute = self.env['product.attribute'].search([('name', '=', 'Design')])
            if attribute:
                i.approval_attribute_id = attribute.id
            else:
                i.approval_attribute_id = []

    @api.onchange('unit_price','pi_rsp_price')
    def calculate_rsp_margin(self):
        for rec in self:
            if rec.product_id:
                tags = rec.product_id.product_tag_ids
                if not tags:
                    raise ValidationError(f'Please select a tag for this product {rec.product_id.name}.')
                for tag in tags:
                    tag_name = tag.name.title()
                    if tag_name == 'Readymade':
                        if 1049 <= rec.pi_rsp_price <= 1200:
                            raise ValidationError(
                                'For Readymade products, RSP price must not be between 1049 and 1200 (inclusive).')
                    elif tag_name == 'Footware':
                        if 1099 <= rec.pi_rsp_price <= 1200:
                            raise ValidationError(
                                'For Footware products, RSP price must not be between 1099 and 1200 (inclusive).')
                if rec.nhcl_margin_rsp_type != 'margin':
                    tax_ids = rec.product_id.supplier_taxes_id
                    if len(tax_ids) > 1:
                        for tax in tax_ids:
                            if tax.min_amount <= rec.pi_rsp_price <= tax.max_amount:
                                temp_price = rec.pi_rsp_price * (tax.amount / 100.0)
                                tax_temp_price = rec.pi_rsp_price - temp_price
                                rec.enter_rsp_margin = ((tax_temp_price - rec.unit_price) / rec.unit_price) * 100
                                break
                    else:
                        if tax_ids and rec.unit_price > 0:
                            temp_price = rec.pi_rsp_price * (tax_ids.amount / 100.0)
                            tax_temp_price = rec.pi_rsp_price - temp_price
                            rec.enter_rsp_margin = ((tax_temp_price - rec.unit_price) / rec.unit_price) * 100
                        else:
                            if rec.unit_price > 0:
                                rec.enter_rsp_margin = ((rec.pi_rsp_price - rec.unit_price) / rec.unit_price) * 100

    @api.onchange('unit_price')
    def onchange_default_rsp_margin(self):
        for rec in self:
            # Get the margin lines from the 3-level parent category
            margin_lines = rec.product_id.categ_id.parent_id.parent_id.parent_id.product_category_margin_ids
            if margin_lines and rec.product_id and rec.unit_price > 0:
                matched = False
                for line in margin_lines:
                    if line.from_range <= rec.unit_price <= line.to_range:
                        rec.default_rsp_margin = line.margin
                        matched = True
                        break  # Stop after first match
                if not matched:
                    raise ValidationError(
                        _("No margin defined for Unit Price %.2f in the range of Category '%s'.") %
                        (rec.unit_price, rec.product_id.categ_id.parent_id.parent_id.parent_id.name)
                    )

    @api.onchange('enter_rsp_margin')
    def onchange_enter_rsp_margin(self):
        for rec in self:
            temp_price = 0.0
            if rec.nhcl_margin_rsp_type != 'rsp':
                base_price = rec.unit_price or 0
                margin_price = (rec.enter_rsp_margin / 100) * base_price if rec.enter_rsp_margin else 0
                tax_temp_price = round(base_price + margin_price)
                tax_ids = rec.product_id.supplier_taxes_id
                if len(tax_ids) > 1:
                    for tax in tax_ids:
                        if tax.min_amount <= tax_temp_price <= tax.max_amount:
                            temp_price = tax_temp_price * (tax.amount / 100.0) + tax_temp_price
                            break
                else:
                    temp_price = tax_temp_price * (tax_ids.amount / 100.0) + tax_temp_price if tax_ids else temp_price
                # Adjusting the last two digits of the price
                if temp_price:
                    last_two_digits = temp_price % 100
                    if last_two_digits < 50:
                        temp_price = temp_price - last_two_digits + 49
                    else:
                        temp_price = temp_price - last_two_digits + 99
                    if rec.product_id and rec.product_id.product_tag_ids:
                        tags = rec.product_id.product_tag_ids
                        if not tags:
                            raise ValidationError(f'Please select a tag for this product {rec.product_id.name}.')
                        for tag in tags:
                            tag_name = tag.name.title()
                            if tag_name == 'Readymade':
                                if 1049 <= temp_price <= 1200:
                                    raise ValidationError('For Readymade products, RSP price must not be between 1049 and 1200 (inclusive).')
                            elif tag_name == 'Footware':
                                if 1099 <= temp_price <= 1200:
                                    raise ValidationError('For Footware products, RSP price must not be between 1099 and 1200 (inclusive).')
                    else:
                        raise ValidationError(f"Product Template tag is not available for {rec.product_id.name}")
                    rec.pi_rsp_price = temp_price
                else:
                    rec.pi_rsp_price = 0

    @api.onchange('pi_rsp_price')
    def onchange_pi_mrp_price(self):
        temp_price = 0
        for rec in self:
            rec.pi_mrp_price = 0
            if not rec.product_id:
                return
            if self.env['product.tag'].search([('name', 'in', ['Readymade', 'Footware'])]):
                if rec.product_id and rec.product_id.product_tag_ids:
                    tags = rec.product_id.product_tag_ids
                    if not tags:
                        raise ValidationError(f'Please select a tag for this product {rec.product_id.name}.')
                    if tags.filtered(lambda tag: tag.name.capitalize() == 'Readymade'):
                        if 1050 < rec.pi_rsp_price < 1200:
                            raise ValidationError('For ReadyMade products, RSP price must not be between 1050 and 1200.')
                else:
                    raise ValidationError(f"Product Template tag is not available for {rec.product_id.name}")
            else:
                raise ValidationError("Readymade,Footware are not created in the product template tags")

            if not rec.pi_rsp_price or rec.pi_rsp_price <= 0:
                raise ValidationError('Please enter a valid RSP price greater than zero.')

            category = rec.product_id.categ_id
            if not (
                    category and category.parent_id and category.parent_id.parent_id and category.parent_id.parent_id.parent_id):
                raise ValidationError('Product category hierarchy is incomplete.')

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
            record.zone_id = record.product_id.categ_id.parent_id.parent_id.parent_id.zone_id.id


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
            totals = next(iter(tax_results['totals'].values()))
            amount_untaxed = totals['amount_untaxed']
            amount_tax = sum(tax_line['tax_amount'] for tax_line in tax_results.get('tax_lines_to_add', []))

            line.update({
                'nhcl_price_subtotal': amount_untaxed,
                'nhcl_price_tax': amount_tax,
                'nhcl_price_total': amount_untaxed + amount_tax,
            })

    @api.depends('product_id')
    def _compute_product_uom_id(self):
        for line in self:
            line.product_uom_id = line.product_id.uom_po_id

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