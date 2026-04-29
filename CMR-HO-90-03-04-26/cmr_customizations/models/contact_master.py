from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import re
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    msme = fields.Selection([('yes', 'YES'), ('no', 'NO')], string="MSME", copy=False)
    msme_category_type = fields.Selection([('trading', 'TRADING'), ('service', 'SERVICE'), ('manufacturing', 'MANFACTURING')], string="MSME Vendor Category",copy=False)
    msme_type = fields.Selection([('micro', 'MICRO'), ('small', 'SMALL'), ('medium', 'MEDIUM')], string="MSME Type",copy=False)
    udyam_reg_no = fields.Char(string = " Udyam registation number" )
    vendor_zone = fields.Many2one('placement.master.data', string="Zone", copy=False, tracking=True, )
    wallet_amount = fields.Float('Wallet Amount', compute='nhcl_get_wallet_amount')

    credit_note_ids = fields.One2many("res.partner.credit.note", inverse_name="partner_id")

    # total_amount_credit=fields.Float('Total Amount', compute='nhcl_get_wallet_amount', store=True)
    # total_amount_deducted_credit=fields.Float('Deduction Amount', compute='nhcl_get_wallet_amount', store=True)

    @api.constrains('credit_note_ids')
    @api.depends('credit_note_ids.remaining_amount')
    def nhcl_get_wallet_amount(self):
        for rec in self:
            if rec.credit_note_ids:
                rec.wallet_amount = sum(rec.credit_note_ids.mapped('remaining_amount'))
                # rec.total_amount_credit = sum(rec.credit_note_ids.mapped('total_amount'))
                # rec.total_amount_deducted_credit = sum(rec.credit_note_ids.mapped('deducted_amount'))
            else:
                rec.wallet_amount = 0.0
                # rec.total_amount_credit = 0.0
                # rec.total_amount_deducted_credit = 0.0

    @api.onchange('msme')
    def _onchange_msme(self):
        if self.msme != 'yes':
            self.msme_category_type = False
            self.msme_type = False
            self.udyam_reg_no = False

    @api.onchange('msme_category_type')
    def _onchange_msme_category_type(self):
        if self.msme_category_type:
            self.msme_type = False
            self.udyam_reg_no = False

    @api.onchange('msme_category_type')
    def get_payment_terms_for_non_traders(self):
        set_payment = self.env['account.payment.term'].search([('name', '=', '45 Days')], limit=1)
        # If the payment term doesn't exist, create it
        if not set_payment:
            set_payment = self.env['account.payment.term'].create({'name': '45 Days', })
        for rec in self:
            if rec.msme_category_type != 'trading':
                rec.property_supplier_payment_term_id = set_payment.id
            else:
                rec.property_supplier_payment_term_id = False

    def default_get_group(self):
        search_partner_mode = self.env.context.get('res_partner_search_mode')
        is_customer = search_partner_mode == 'customer'
        is_supplier = search_partner_mode == 'supplier'
        customer_group = self.env['res.partner.category'].search([('name', '=', 'Customer')], limit=1)
        vendor_group = self.env['res.partner.category'].search([('name', '=', 'Vendor')], limit=1)
        if is_customer and not customer_group:
            raise ValidationError(_('Customer is not listed in Contact Tags. Kindly configure it.'))
        elif is_supplier and not vendor_group:
            raise ValidationError(_('Vendor is not available in Contact Tags. Kindly configure it.'))

        group = False

        if customer_group and is_customer:
            group = customer_group.id
        elif vendor_group and is_supplier:
            group = vendor_group.id
        return group

    group_contact = fields.Many2one('res.partner.category', string='Group', tracking=True, default=default_get_group)
    contact_sequence = fields.Char(string="Sequence", copy=False,required=True,default=lambda self: _("New"), tracking=True)

    @api.onchange('group_contact')
    def selecting_group(self):
        if self.group_contact:
            self.category_id = self.group_contact

    @api.model_create_multi
    def create(self, vals_list):
        seq_model = self.env['nhcl.master.sequence']
        partner_model = self.env['res.partner']

        # Step 1: fetch configs once
        seq_map = {
            'customer': seq_model.search([('nhcl_code', '=', 'cmr.customer'), ('nhcl_state', '=', 'activate')],
                                         limit=1),
            'vendor': seq_model.search([('nhcl_code', '=', 'cmr.vendor'), ('nhcl_state', '=', 'activate')], limit=1),
            'transport': seq_model.search([('nhcl_code', '=', 'cmr.transport'), ('nhcl_state', '=', 'activate')],
                                          limit=1),
            'branch': seq_model.search([('nhcl_code', '=', 'cmr.branch'), ('nhcl_state', '=', 'activate')], limit=1),
        }

        branch_group = self.env['res.partner.category'].search([('name', '=', 'Branch')], limit=1)
        if not branch_group:
            raise ValidationError(_("The Branch is not available in Contact Tags. Please configure it."))

        # Step 2: create partners first
        partners = super().create(vals_list)

        # Step 3: fetch existing sequences once
        existing_sequences = set(partner_model.search([]).mapped('contact_sequence'))

        ir_seq = self.env['ir.sequence']

        def get_unique_sequence(code):
            for _ in range(10):  # prevent infinite loop
                seq_number = ir_seq.next_by_code(code) or 'New'
                if seq_number not in existing_sequences:
                    existing_sequences.add(seq_number)
                    return seq_number
            raise ValidationError(_("Unable to generate unique sequence."))

        # Step 4: process each partner
        for partner in partners:
            group_name = partner.group_contact.name if partner.group_contact else False

            if group_name == 'Branch':
                raise ValidationError(_("Branch should not be created from here."))

            if group_name == 'Employee':
                raise ValidationError(_("Employee should not be created from here."))

            # Validation
            if group_name == 'Customer' and not seq_map['customer']:
                raise ValidationError(_("Customer sequence not configured."))
            elif group_name in ['Vendor', 'Agent'] and not seq_map['vendor']:
                raise ValidationError(_("Vendor sequence not configured."))
            elif group_name == 'Transporter' and not seq_map['transport']:
                raise ValidationError(_("Transporter sequence not configured."))
            elif group_name == 'Branch' and not seq_map['branch']:
                raise ValidationError(_("Branch sequence not configured."))

            # Assignment
            if group_name == 'Customer':
                partner.contact_sequence = get_unique_sequence('cmr.customer')
                partner.customer_rank = 1

            elif group_name in ['Vendor', 'Agent']:
                partner.contact_sequence = get_unique_sequence('cmr.vendor')
                partner.supplier_rank = 1

            elif group_name == 'Transporter':
                partner.contact_sequence = get_unique_sequence('cmr.transport')
                partner.customer_rank = 0
                partner.supplier_rank = 0

            elif group_name == 'Branch':
                partner.contact_sequence = get_unique_sequence('cmr.branch')
                partner.customer_rank = 0
                partner.supplier_rank = 0

        return partners

    @api.constrains('phone')
    def _check_phone_digits(self):
        for rec in self:
            if rec.phone and not re.match(r'^\d+$', rec.phone):
                raise ValidationError("Phone number must contain digits only.")

    @api.constrains('mobile')
    def _check_mobile_digits(self):
        for rec in self:
            if rec.mobile and not re.match(r'^\d+$', rec.mobile):
                raise ValidationError("Mobile number must contain digits only.")

class PartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    @api.model_create_multi
    def create(self, vals_list):
        Model = self.env['res.partner.category']

        # Step 1: normalize names
        names = []
        for vals in vals_list:
            if vals.get('name'):
                name = vals['name'].strip()
                vals['name'] = name
                names.append(name)
        # Step 2: check duplicates in DB (exact match)
        if names:
            existing = Model.search([
                ('name', 'in', names)
            ], limit=1)
            if existing:
                raise ValidationError(
                    _("A Group with the name '%s' already exists.") % existing.name
                )
        # Step 3: check duplicates in same batch
        seen = set()
        for name in names:
            key = name.lower()
            if key in seen:
                raise ValidationError(
                    _("Duplicate Group '%s' in same request.") % name
                )
            seen.add(key)
        # Step 4: create records
        return super().create(vals_list)

class Hr(models.Model):
    _inherit = 'hr.employee'

    employee_sequence = fields.Char(string="Sequence", copy=False, default=lambda self: _("New"),
                                   tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        seq_model = self.env['nhcl.master.sequence']
        ir_seq = self.env['ir.sequence']

        # Step 1: validate config once
        employee_group = self.env['res.partner.category'].search(
            [('name', '=', 'Employee')], limit=1
        )
        employee_seq = seq_model.search(
            [('nhcl_code', '=', 'cmr.employee'), ('nhcl_state', '=', 'activate')],
            limit=1)
        if not employee_group:
            raise ValidationError('Employee category is not available in contact categories. Kindly configure it.')
        if not employee_seq:
            raise ValidationError('Employee Sequence is not set in the sequence master. Kindly configure it.')
        # Step 2: prefetch existing sequences (only once)
        existing_sequences = set(self.env['hr.employee'].search([]).mapped('employee_sequence'))
        # Step 3: assign sequence BEFORE create (better)
        for vals in vals_list:
            if not vals.get('employee_sequence') or vals.get('employee_sequence') == 'New':
                for _ in range(5):  # retry limit
                    seq_number = ir_seq.next_by_code('cmr.employee') or 'New'
                    if seq_number not in existing_sequences:
                        vals['employee_sequence'] = seq_number
                        existing_sequences.add(seq_number)
                        break
                else:
                    raise ValidationError(_("Unable to generate unique employee sequence."))
        # Step 4: create employees
        employees = super().create(vals_list)
        # Step 5: update partner (post create)
        for emp in employees:
            if emp.work_contact_id:
                emp.work_contact_id.write({
                    'contact_sequence': emp.employee_sequence,
                    'group_contact': employee_group.id,
                    'category_id': [(4, employee_group.id)]
                })
        return employees

class Company(models.Model):
    _inherit = "res.company"

    nhcl_company_bool = fields.Boolean(string="Is Main Company")
    nhcl_res_cin_no = fields.Integer(string='Cin No')

    @api.model_create_multi
    def create(self, vals_list):
        seq_model = self.env['nhcl.master.sequence']
        partner_model = self.env['res.partner']
        ir_seq = self.env['ir.sequence']
        # Step 1: fetch configs once
        branch_group = self.env['res.partner.category'].search(
            [('name', '=', 'Branch')], limit=1
        )
        branch_seq = seq_model.search(
            [('nhcl_code', '=', 'cmr.branch'), ('nhcl_state', '=', 'activate')],
            limit=1
        )
        if not branch_group:
            raise ValidationError(
                _("The Branch is not available in Contact Tags. Kindly configure it.")
            )
        if not branch_seq:
            raise ValidationError(
                _("Branch Sequence is not set in the sequence master. Kindly configure it.")
            )
        # Step 2: create companies
        companies = super().create(vals_list)
        # Step 3: assign branch sequence to related partners
        for company in companies:
            partner = company.partner_id
            if partner:
                partner.write({
                    'group_contact': branch_group.id,
                    'contact_sequence': ir_seq.next_by_code('cmr.branch') or 'New'
                })
        return companies


class ResPartnerCreditNote(models.Model):
    _name = 'res.partner.credit.note'
    _description = 'Partner Credit Note'

    partner_id = fields.Many2one('res.partner', string="Partner", ondelete="cascade", required=True)
    voucher_number = fields.Char(string="Voucher Number")
    pos_bill_number = fields.Char(string="POS Bill Number")
    pos_bill_date = fields.Date(string="POS Bill Date")
    total_amount = fields.Float(string="Total Amount")
    deducted_amount = fields.Float(string="Deducted Amount")
    remaining_amount = fields.Float(string="Remaining Amount", compute="_compute_remaining_amount",store=True)

    @api.depends('total_amount','deducted_amount')
    def _compute_remaining_amount(self):
        for rec in self:
            rec.remaining_amount = rec.total_amount - rec.deducted_amount