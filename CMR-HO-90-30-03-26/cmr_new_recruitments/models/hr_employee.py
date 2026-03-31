from odoo import models, fields,api,_
import logging

from odoo.exceptions import ValidationError

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
    ], string="Leave Eligibility", default='yes')

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
    employer_pf = fields.Float(string="Employer PF(Per Annum)")
    pt = fields.Float(string="PT (Per Annum)")
    net_take_home = fields.Float(string="NET TAKE HOME (Per Annum)")
    family_insurance = fields.Float(string="FAMILY INSURANCE (Per Annum)")
    bonus = fields.Float(string="BONUS (Per Annum)")
    esic = fields.Float(string="ESIC (Per Annum)")

    # Monthly Fields
    ctc_m = fields.Float(string="CTC (Per Month)")
    basic_m = fields.Float(string="BASIC (Per Month)")
    hra_m = fields.Float(string="HRA (Per Month)")
    other_allowance_m = fields.Float(string="OTHER ALLOWANCE (Per Month)")
    pf_m = fields.Float(string="PF (Per Month)")
    employer_pf_m = fields.Float(string="Employer PF(Per Month)")
    pt_m = fields.Float(string="PT (Per Month)")
    net_take_home_m = fields.Float(string="NET TAKE HOME (Per Month)")
    family_insurance_m = fields.Float(string="FAMILY INSURANCE (Per Month)")
    bonus_m = fields.Float(string="BONUS (Per Month)")
    esic_m = fields.Float(string="ESIC (Per Month)")

    uniform_m = fields.Float(string="Uniform")
    cmr_code = fields.Char(string='EMP Code')
    ctc_type = fields.Selection([
        ('with_bonus', 'With Bonus'),
        ('without_bonus', 'Without Bonus'),
        ('non_ctc', 'Non Ctc'),
    ], string='CTC Type')
    date_of_joining = fields.Date(string='Date Of Joining')
    bank_name = fields.Char(string="Bank Name")
    timeoff_allocated = fields.Float("Allocated Leaves ", compute="_compute_timeoff_balance")
    timeoff_used = fields.Float("Used Leaves ", compute="_compute_timeoff_balance")
    timeoff_balance = fields.Float("Remaining Leaves", compute="_compute_timeoff_balance")
    statutory_type = fields.Selection(
        [
            ('pf', 'PF'),
            ('non_pf', 'Non PF'),
            ('esi', 'ESI'),
            ('pf_employer', 'PF Employer'),
        ],
        string="Statutory Type",
        required=True,
        default='pf_employer'
    )

    def _compute_timeoff_balance(self):
        Leave = self.env['hr.leave']
        Allocation = self.env['hr.leave.allocation']
        LeaveType = self.env['hr.leave.type']

        # EL type (Earned Leave)
        el_type = LeaveType.search([('work_entry_type_id.code', '=', 'LEAVE120')], limit=1)
        # LOP type (Loss of Pay)
        lop_type = LeaveType.search([('work_entry_type_id.code', '=', 'LEAVE90')], limit=1)

        for emp in self:
            # Allocated EL only
            emp.timeoff_allocated = sum(Allocation.search([
                ('employee_id', '=', emp.id),
                ('holiday_status_id', '=', el_type.id),
                ('state', '=', 'validate'),
            ]).mapped('number_of_days')) if el_type else 0.0

            # Used = EL + LOP (approved & confirm)
            used_el = sum(Leave.search([
                ('employee_id', '=', emp.id),
                ('holiday_status_id', '=', el_type.id),
                ('state', 'in', ['validate', 'confirm']),
            ]).mapped('number_of_days')) if el_type else 0.0

            used_lop = sum(Leave.search([
                ('employee_id', '=', emp.id),
                ('holiday_status_id', '=', lop_type.id),
                ('state', 'in', ['validate', 'confirm']),
            ]).mapped('number_of_days')) if lop_type else 0.0

            emp.timeoff_used = used_el + used_lop

            # Remaining EL
            emp.timeoff_balance = emp.timeoff_allocated - emp.timeoff_used

    @api.model
    def create(self, vals):
        if not vals.get('barcode'):
            vals['barcode'] = (
                    self.env['ir.sequence'].next_by_code('hr.employee.cmr') or '/'
            )
        employee = super().create(vals)

        # Create contract if DOJ exists
        if employee.date_of_joining:
            contract = self.env['hr.contract'].search(
                [('employee_id', '=', employee.id)],
                limit=1
            )
            if not contract:
                self.env['hr.contract'].create(
                    employee._get_contract_vals_from_employee(employee)
                )

        return employee

    # --------------------------------------------------
    # WRITE
    # --------------------------------------------------
    def write(self, vals):
        res = super().write(vals)

        for employee in self:
            # If DOJ added later → create contract
            if 'date_of_joining' in vals and vals.get('date_of_joining'):
                contract = self.env['hr.contract'].search(
                    [('employee_id', '=', employee.id)],
                    limit=1
                )
                if not contract:
                    self.env['hr.contract'].create(
                        employee._get_contract_vals_from_employee(employee)
                    )

            # Sync salary fields → Contract
            if (
                    'ctc_m' in vals or
                    'basic_m' in vals or
                    'pt_m' in vals or
                    'hra_m' in vals or
                    'esic_m' in vals or
                    'pf_m' in vals or
                    'net_take_home_m' in vals or
                    'other_allowance_m' in vals or
                    'employer_pf_m' in vals or
                    'bonus_m' in vals or
                    'department_id' in vals or
                    'job_id' in vals or
                    'statutory_type' in vals
            ):
                contract = self.env['hr.contract'].search([
                    ('employee_id', '=', employee.id),
                    ('state', 'in', ['draft', 'open', 'running'])
                ], limit=1)

                if contract:
                    contract.write(
                        employee._get_salary_vals(employee)
                    )

        return res

    # --------------------------------------------------
    # CONTRACT CREATE VALUES (FROM EMPLOYEE)
    # --------------------------------------------------
    def _get_contract_vals_from_employee(self, employee):
        return {
            'name': employee.name,
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'statutory_type': employee.statutory_type,
            'department_id': employee.department_id.id if employee.department_id else False,
            'job_id': employee.job_id.id if employee.job_id else False,
            'date_start': employee.date_of_joining,
            'work_entry_source': 'attendance',
            'resource_calendar_id':
                employee.resource_calendar_id.id
                if employee.resource_calendar_id else False,

            # Salary
            'wage': employee.ctc_m or 0.0,
            'basic': employee.basic_m or 0.0,
            'actual_bonus': employee.bonus_m or 0.0,
            'p_tax': employee.pt_m or 0.0,
            'net_salary': employee.net_take_home_m or 0.0,
            'provident_fund': employee.pf_m or 0.0,
            'l10n_in_house_rent_allowance_metro_nonmetro':
                employee.hra_m or 0.0,
            'l10n_in_esic_amount': employee.esic_m or 0.0,
            'other_allowance': employee.other_allowance_m or 0.0,
            'employer_pf': employee.employer_pf_m or 0.0,
            'employer_esic': employee.basic_m * 0.0325 or 0.0,
            'cost_to_company': employee.ctc_m or 0.0,
        }

    # --------------------------------------------------
    # UPDATE
    # --------------------------------------------------
    def _get_salary_vals(self, employee):
        return {
            'department_id': employee.department_id.id if employee.department_id else False,
            'job_id': employee.job_id.id if employee.job_id else False,
            'wage': employee.ctc_m or 0.0,
            'basic': employee.basic_m or 0.0,
            'actual_bonus': employee.bonus_m or 0.0,
            'p_tax': employee.pt_m or 0.0,
            'net_salary': employee.net_take_home_m or 0.0,
            'provident_fund': employee.pf_m or 0.0,
            'l10n_in_house_rent_allowance_metro_nonmetro': employee.hra_m or 0.0,
            'l10n_in_esic_amount': employee.esic_m or 0.0,
            'other_allowance': employee.other_allowance_m or 0.0,
            'employer_pf': employee.employer_pf_m or 0.0,
            'employer_esic': employee.basic_m * 0.0325 or 0.0,
            'cost_to_company': employee.ctc_m or 0.0,
            'statutory_type': employee.statutory_type,
        }


    # @api.model
    # def create(self, vals):
    #     if 'cmr_code' not in vals or not vals.get('cmr_code'):
    #         vals['cmr_code'] = self.env['ir.sequence'].next_by_code('hr.employee.cmr') or '/'
    #     employee = super().create(vals)
    #     if employee:
    #         existing = self.env['hr.contract'].search([('employee_id', '=', employee.id)], limit=1)
    #         if not existing and employee.date_of_joining:
    #             self.env['hr.contract'].create({
    #                 'name': employee.name,
    #                 'employee_id': employee.id,
    #                 'company_id': employee.company_id.id,
    #                 'department_id': employee.department_id.id if employee.department_id else False,
    #                 'job_id': employee.job_id.id if employee.job_id else False,
    #                 'date_start': employee.date_of_joining,
    #                 'wage': employee.ctc_m or 0.0,
    #                 'basic': employee.basic_m or 0.0,
    #                 'p_tax': employee.pt_m or 0.0,
    #                 'cost_to_company': employee.ctc_m or 0.0,
    #                 'net_salary': employee.net_take_home_m or 0.0,
    #                 'provident_fund': employee.pf_m or 0.0,
    #                 'l10n_in_house_rent_allowance_metro_nonmetro': employee.hra_m or 0.0,
    #                 'l10n_in_esic_amount': employee.esic_m or 0.0,
    #                 'other_allowance': employee.other_allowance_m or 0.0,
    #                 'work_entry_source': 'attendance',
    #                 'employer_pf': employee.employer_pf_m,
    #                 'employer_esic': employee.basic_m * 0.0325 or 0.0
    #             })
    #     return employee
    #
    # def write(self, vals):
    #     res = super().write(vals)
    #
    #     for employee in self:
    #
    #         #  Common salary values used for create/update
    #         contract_vals = {
    #             'name': employee.name,
    #             'company_id': employee.company_id.id,
    #             'department_id': employee.department_id.id if employee.department_id else False,
    #             'job_id': employee.job_id.id if employee.job_id else False,
    #             'date_start': employee.date_of_joining,
    #             'wage': employee.ctc_m or 0.0,
    #             'basic': employee.basic_m or 0.0,
    #             'p_tax': employee.pt_m or 0.0,
    #             'cost_to_company': employee.ctc_m or 0.0,
    #             'net_salary': employee.net_take_home_m or 0.0,
    #             'provident_fund': employee.pf_m or 0.0,
    #             'l10n_in_house_rent_allowance_metro_nonmetro': employee.hra_m or 0.0,
    #             'l10n_in_esic_amount': employee.esic_m or 0.0,
    #             'other_allowance': employee.other_allowance_m or 0.0,
    #             'work_entry_source': 'attendance',
    #             'employer_pf': employee.employer_pf_m or 0.0,
    #             'employer_esic': employee.basic_m * 0.0325 or 0.0,
    #         }
    #
    #         # Condition: Only when joining date is updated
    #         if vals.get('date_of_joining'):
    #             contract = self.env['hr.contract'].search([
    #                 ('employee_id', '=', employee.id),
    #                 ('state', 'in', ['draft', 'open'])
    #             ], limit=1, order="id desc")
    #
    #             if contract:
    #                 # Update contract
    #                 contract.write(contract_vals)
    #             else:
    #                 # ✨ Create new contract
    #                 contract_vals.update({
    #                     'employee_id': employee.id,
    #                 })
    #                 self.env['hr.contract'].create(contract_vals)
    #
    #     return res
    #

    # def write(self, vals):
    #     res = super().write(vals)
    #
    #     for employee in self:
    #
    #         if vals.get('date_of_joining') and not employee.contract_ids:
    #             self.env['hr.contract'].create({
    #                 'name': employee.name,
    #                 'employee_id': employee.id,
    #                 'department_id': employee.department_id.id if employee.department_id else False,
    #                 'job_id': employee.job_id.id if employee.job_id else False,
    #                 'date_start': employee.date_of_joining,
    #                 'wage': employee.ctc_m or 0.0,
    #                 'basic': employee.basic_m or 0.0,
    #                 'p_tax': employee.pt_m or 0.0,
    #                 'cost_to_company': employee.ctc_m or 0.0,
    #                 'net_salary': employee.net_take_home_m or 0.0,
    #                 'provident_fund': employee.pf_m or 0.0,
    #                 'l10n_in_house_rent_allowance_metro_nonmetro': employee.hra_m or 0.0,
    #                 'l10n_in_esic_amount': employee.esic_m or 0.0,
    #                 'other_allowance': employee.other_allowance_m or 0.0,
    #                 'work_entry_source': 'attendance',
    #                 'employer_pf': employee.employer_pf_m,
    #                 'employer_esic': employee.basic_m * 0.0325 or 0.0
    #             })
    #
    #     return res

    # @api.model
    # def create(self, vals):
    #     if 'cmr_code' not in vals or not vals.get('cmr_code'):
    #         vals['cmr_code'] = self.env['ir.sequence'].next_by_code('hr.employee.cmr') or '/'
    #     employee = super().create(vals)
    #     if employee:
    #         existing = self.env['hr.contract'].search([('employee_id', '=', employee.id)], limit=1)
    #         if not existing  and employee.date_of_joining:
    #             self.env['hr.contract'].create({
    #                 'name': employee.name,
    #                 'employee_id': employee.id,
    #                 'department_id': employee.department_id.id if employee.department_id else False,
    #                 'job_id': employee.job_id.id if employee.job_id else False,
    #                 'date_start': employee.date_of_joining,
    #                 'wage': employee.ctc_m or 0.0,
    #                 'basic': employee.basic_m or 0.0,
    #                 'p_tax': employee.pt_m or 0.0,
    #                 'cost_to_company': employee.ctc_m or 0.0,
    #                 'net_salary': employee.net_take_home_m or 0.0,
    #                 'provident_fund': employee.pf_m or 0.0,
    #                 'l10n_in_house_rent_allowance_metro_nonmetro': employee.hra_m or 0.0,
    #                 'l10n_in_esic_amount': employee.basic_m * 0.0075 or 0.0,
    #                 'other_allowance': employee.other_allowance_m or 0.0,
    #                 'work_entry_source': 'attendance',
    #                 'employer_pf': employee.basic_m * 0.12 or 0.0,
    #                 'employer_esic': employee.basic_m * 0.0325 or 0.0
    #             })
    #     return employee
    #
    # def write(self, vals):
    #     res = super().write(vals)
    #
    #     for employee in self:
    #         if vals.get('date_of_joining') and not employee.contract_ids:
    #             self.env['hr.contract'].create({
    #                 'name': employee.name,
    #                 'employee_id': employee.id,
    #                 'date_start': vals.get('date_of_joining'),
    #                 'wage': employee.ctc_m or 0.0,
    #                 'work_entry_source': 'attendance',
    #                 # 'date_of_joining' : employee.date_of_joining
    #             })
    #
    #     return res

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

