from odoo import models, fields,api,_
import logging
_logger = logging.getLogger(__name__)
class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    division_id = fields.Many2one(
        'product.category',
        string='Division',
        domain=[('parent_id', '=', False)],
        help="Select division from top-level product categories (no parent)."
    )

    ifsc_code = fields.Char(string='IFSC Code')
    blood_group = fields.Selection([
        ('a+', 'A+'), ('a-', 'A-'),
        ('b+', 'B+'), ('b-', 'B-'),
        ('ab+', 'AB+'), ('ab-', 'AB-'),
        ('o+', 'O+'), ('o-', 'O-')
    ], string="Blood Group")


    insurance = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string="Insurance", default='no')
    nominee_ids = fields.One2many('hr.employee.nominee', 'employee_id', string="Nominee Details")
    family_detail_ids = fields.One2many('family.details', 'employee_id', string='Family Details')
    total_experience = fields.Float(string="Total Years of Experience")
    professional_ids = fields.One2many('professional.details', 'employee_id', string="Professional Details")

    marital = fields.Selection([
        ('single', 'Single'),
        ('married', 'Married'),
        ('cohabitant', 'Legal Cohabitant'),
        ('widower', 'Widower'),
        ('divorced', 'Divorced')
    ], string='Marital Status', default='single')
    spouse_complete_name = fields.Char(string="Spouse Complete Name")
    spouse_birthdate = fields.Date(string="Spouse Birthdate")
    children = fields.Integer(string='Number of Dependent Children')

    permanent_street = fields.Char(string="Permanent Address")
    permanent_street2 = fields.Char(string="Permanent Street 2")
    permanent_city = fields.Char(string="Permanent City")
    permanent_state_id = fields.Many2one('res.country.state', string="Permanent State")
    permanent_zip = fields.Char(string="Permanent ZIP")
    permanent_country_id = fields.Many2one('res.country', string="Permanent Country")
    same_as_private = fields.Boolean(string="Same as Private Address")

    reference_ids = fields.One2many('employee.reference', 'employee_id', string="References")

    education_ids = fields.One2many('employee.education', 'employee_id', string="Educational Details")
    asset_ids = fields.One2many('account.asset', 'employee_id_nhcl_xpath', string='Asset')
    leave_eligibility = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string="Leave Eligibility", default='no')

    probation_confirmation_date = fields.Date(string="Probation Confirmation Date")

    grade_id = fields.Char(string="Grade",compute='_compute_grade', store=True)

    check_list_ids = fields.Many2many("check.list")
    bank_account = fields.Char(string="Bank Account Number")
    age = fields.Integer(string="Age")

    pf_num = fields.Char(string="PF Number")
    insurance_num = fields.Char(string="Insurance Number")

    ctc = fields.Float(string="CTC (Per Annum)")
    basic = fields.Float(string="BASIC (Per Annum)")
    hra = fields.Float(string="HRA (Per Annum)")
    other_allowance = fields.Float(string="OTHER ALLOWANCE (Per Annum)")
    pf = fields.Float(string="PF (Per Annum)")
    pt = fields.Float(string="PT (Per Annum)")
    net_take_home = fields.Float(string="NET TAKE HOME (Per Annum)")
    family_insurance = fields.Float(string="FAMILY INSURANCE (Per Annum)")
    bonus = fields.Float(string="BONUS (Per Annum)")

    # Monthly Fields
    ctc_m = fields.Float(string="CTC (Per Month)")
    basic_m = fields.Float(string="BASIC (Per Month)")
    hra_m = fields.Float(string="HRA (Per Month)")
    other_allowance_m = fields.Float(string="OTHER ALLOWANCE (Per Month)")
    pf_m = fields.Float(string="PF (Per Month)")
    pt_m = fields.Float(string="PT (Per Month)")
    net_take_home_m = fields.Float(string="NET TAKE HOME (Per Month)")
    family_insurance_m = fields.Float(string="FAMILY INSURANCE (Per Month)")

    uniform = fields.Boolean(string="Uniform")
    cmr_code = fields.Char(string='EMP Code')

    # @api.model
    # def create(self, vals):
    #     employee = super(HrEmployee, self).create(vals)
    #
    #     # Check if contract already exists (to avoid duplicates)MG
    #     existing_contract = self.env['hr.contract'].search([('employee_id', '=', employee.id)], limit=1)
    #     if not existing_contract:
    #         self.env['hr.contract'].create({
    #             'name': f"{employee.name}",
    #             'employee_id': employee.id,
    #             'job_id': employee.job_id.id,
    #             'wage': employee.ctc_m,
    #             'department_id': employee.department_id.id,
    #         })
    #     return employee

    @api.model
    def create(self, vals):
        if 'cmr_code' not in vals or not vals.get('cmr_code'):
            vals['cmr_code'] = self.env['ir.sequence'].next_by_code('hr.employee.cmr') or '/'

        employee = super().create(vals)


        if employee:
            existing = self.env['hr.contract'].search([('employee_id', '=', employee.id)], limit=1)
            if not existing:
                self.env['hr.contract'].create({
                    'name': employee.name,
                    'employee_id': employee.id,
                    'department_id': employee.department_id.id if employee.department_id else False,
                    'job_id': employee.job_id.id if employee.job_id else False,
                    'date_start': fields.Date.today(),
                    'wage': employee.ctc_m or 0.0,
                    'basic': employee.basic_m or 0.0,
                    'p_tax': employee.pt_m or 0.0,
                    'cost_to_company': employee.ctc or 0.0,
                    'net_salary': employee.net_take_home_m or 0.0,
                    'provident_fund': employee.pf_m or 0.0,
                    'l10n_in_house_rent_allowance_metro_nonmetro': employee.hra_m or 0.0,
                    'l10n_in_esic_amount': employee.basic_m * 0.0075 or 0.0,
                    'other_allowance': employee.other_allowance or 0.0,
                })
        return employee

    @api.depends('department_id', 'job_id')
    def _compute_grade(self):
        for rec in self:
            if rec.department_id and rec.job_id:
                grade = self.env['grade.master'].search([
                    ('department_id', '=', rec.department_id.id),
                    ('job_id', '=', rec.job_id.id)
                ], limit=1)
                rec.grade_id = grade.name if grade else False
            else:
                rec.grade_id = False

    @api.onchange('same_as_private')
    def _onchange_same_as_private(self):
        if self.same_as_private:
            self.permanent_street = self.private_street
            self.permanent_street2 = self.private_street2
            self.permanent_city = self.private_city
            self.permanent_state_id = self.private_state_id
            self.permanent_zip = self.private_zip
            self.permanent_country_id = self.private_country_id
        else:
            # Clear permanent address if unchecked
            self.permanent_street = False
            self.permanent_street2 = False
            self.permanent_city = False
            self.permanent_state_id = False
            self.permanent_zip = False
            self.permanent_country_id = False

    @api.onchange('nominee_ids', 'family_detail_ids','education_ids','professional_ids')
    def _onchange_employee_lines(self):
        """Auto-assign sequence numbers for both educational and professional lines."""
        for idx, line in enumerate(self.nominee_ids, start=1):
            line.sequence = idx
        for idx, line in enumerate(self.family_detail_ids, start=1):
            line.sequence = idx
        for idx, line in enumerate(self.education_ids, start=1):
            line.sequence = idx
        for idx, line in enumerate(self.professional_ids, start=1):
            line.sequence = idx

