from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
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

    @api.model
    def create(self, vals_list):
        res = super(ResPartner, self).create(vals_list)

        # Retrieve sequences from nhcl.master.sequence model
        customer_seq = self.env['nhcl.master.sequence'].search(
            [('nhcl_code', '=', 'cmr.customer'), ('nhcl_state', '=', 'activate')], limit=1)
        transport_seq = self.env['nhcl.master.sequence'].search(
            [('nhcl_code', '=', 'cmr.transport'), ('nhcl_state', '=', 'activate')], limit=1)
        vendor_seq = self.env['nhcl.master.sequence'].search(
            [('nhcl_code', '=', 'cmr.vendor'), ('nhcl_state', '=', 'activate')], limit=1)
        branch_group = self.env['res.partner.category'].search([('name', '=', 'Branch')], limit=1)
        branch_seq = self.env['nhcl.master.sequence'].search(
            [('nhcl_code', '=', 'cmr.branch'), ('nhcl_state', '=', 'activate')], limit=1)

        # Check if the Branch group is available
        if not branch_group:
            raise ValidationError("The Branch is not available in the Contact Tags. Kindly configure it.")
        if res.group_contact.name == 'Branch':
            raise ValidationError("Branch should not create from here. You should create from master.")
        if res.group_contact.name == 'Employee':
            raise ValidationError("Employee should not create from here. You should create from master.")

        # Validation for sequence existence based on contact type
        if res.group_contact.name == 'Customer' and not customer_seq:
            raise ValidationError("Customer sequence is not configured in the Sequence Master. Kindly configure it.")
        elif res.group_contact.name in ['Vendor', 'Agent'] and not vendor_seq:
            raise ValidationError(
                "Vendor sequence is not configured in the Sequence Master. Kindly configure it.")
        elif res.group_contact.name == 'Transporter' and not transport_seq:
            raise ValidationError(
                "Transporter sequence is not configured in the Sequence Master. Kindly configure it.")
        elif res.group_contact.name == 'Branch' and not branch_seq:
            raise ValidationError(_('Branch Sequence is not set in the sequence master. Kindly configure it.'))

        def get_unique_sequence(sequence_code):
            while True:
                seq_number = self.env['ir.sequence'].next_by_code(sequence_code) or 'New'
                if not self.env['res.partner'].search([('contact_sequence', '=', seq_number)]):
                    return seq_number
                else:
                    # If the sequence number is already used, log a warning and regenerate
                    logger.warning(f"Sequence number {seq_number} already exists. Regenerating...")

        # Assign unique sequence numbers based on the contact type
        if res.group_contact.name == 'Customer' and customer_seq:
            res.contact_sequence = get_unique_sequence('cmr.customer')
            res.customer_rank = 1
        elif res.group_contact.name in ['Vendor', 'Agent'] and vendor_seq:
            res.contact_sequence = get_unique_sequence('cmr.vendor')
            res.supplier_rank = 1
        elif res.group_contact.name == 'Transporter' and transport_seq:
            res.contact_sequence = get_unique_sequence('cmr.transport')
            res.supplier_rank = 0
            res.customer_rank = 0
        elif res.group_contact.name == 'Branch' and branch_seq:
            res.contact_sequence = get_unique_sequence('cmr.branch')
            res.supplier_rank = 0
            res.customer_rank = 0

        return res

class PartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    @api.model
    def create(self,vals):
        if 'name' in vals:
            existing_group = self.env['res.partner.category'].search([('name', 'ilike', vals['name'])])
            if existing_group:
                raise ValidationError(_("A Group with the name '%s' already exists.") % vals['name'])
        product = super(PartnerCategory, self).create(vals)
        return product

class Hr(models.Model):
    _inherit = 'hr.employee'

    employee_sequence = fields.Char(string="Sequence", copy=False, default=lambda self: _("New"),
                                   tracking=True)

    @api.model
    def create(self, vals_list):
        res = super(Hr, self).create(vals_list)
        employee_group = self.env['res.partner.category'].search([('name', '=', 'Employee')], limit=1)
        employee_seq = self.env['nhcl.master.sequence'].search(
            [('nhcl_code', '=', 'cmr.employee'), ('nhcl_state', '=', 'activate')], limit=1)
        if not employee_group:
            raise ValidationError(_('Employee category is not available in contact categories. Kindly configure it.'))

        if not employee_seq:
            raise ValidationError(_('Employee Sequence is not set in the sequence master. Kindly configure it.'))

        def get_unique_sequence(sequence_code):
            while True:
                seq_number = self.env['ir.sequence'].next_by_code(sequence_code) or 'New'
                if not self.env['hr.employee'].search([('employee_sequence', '=', seq_number)]):
                    return seq_number
                else:
                    # If the sequence number is already used, log a warning and regenerate
                    logger.warning(f"Sequence number {seq_number} already exists. Regenerating...")

        if res.employee_sequence == 'New':
            res.employee_sequence = get_unique_sequence('cmr.employee')
        if res.work_contact_id:
            res.work_contact_id.write({
                'contact_sequence': res.employee_sequence,
                'group_contact': employee_group.id,
                'category_id': employee_group.ids
            })
        return res

class Company(models.Model):
    _inherit = "res.company"

    nhcl_company_bool = fields.Boolean(string="Is Main Company")
    nhcl_res_cin_no = fields.Integer(string='Cin No')

    def create(self, vals):
        branch_group = self.env['res.partner.category'].search([('name', '=', 'Branch')], limit=1)
        branch_seq = self.env['nhcl.master.sequence'].search(
            [('nhcl_code', '=', 'cmr.branch'), ('nhcl_state', '=', 'activate')], limit=1)
        if not branch_group:
            raise ValidationError("The Branch is not available in the Contact Tags. Kindly configure it.")

        if not branch_seq:
            raise ValidationError(_('Branch Sequence is not set in the sequence master. Kindly configure it.'))
        res = super(Company, self).create(vals)
        branch_group = self.env['res.partner.category'].search([('name', '=', 'Branch')], limit=1)
        if not branch_group:
            raise ValidationError("The Branch is not available in the Contact Tags. Kindly configure it.")
        def get_unique_sequence(sequence_code):
            while True:
                seq_number = self.env['ir.sequence'].next_by_code(sequence_code) or 'New'
                if not self.env['res.partner'].search([('contact_sequence', '=', seq_number)]):
                    return seq_number
                else:
                    # If the sequence number is already used, log a warning and regenerate
                    logger.warning(f"Sequence number {seq_number} already exists. Regenerating...")

        contact = self.env['res.partner'].browse(res.partner_id.id)
        branch_sequence = get_unique_sequence('cmr.branch')
        contact.write({
            'group_contact': branch_group.id,
            'contact_sequence': branch_sequence
        })
        return res