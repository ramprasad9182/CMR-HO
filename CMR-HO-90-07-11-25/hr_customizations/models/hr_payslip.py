from odoo import models, fields, api
from datetime import date, timedelta
from calendar import monthrange
import logging
from datetime import datetime, time
import pytz

_logger = logging.getLogger(__name__)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # --- Related Fields from Employee & Contract ---
    pf_no = fields.Char(string="PF No", related="employee_id.pf_num", store=True, readonly=True)
    uan_no = fields.Char(string="UAN No", related="employee_id.l10n_in_uan", store=True, readonly=True)
    esi_no = fields.Char(string="ESI No", related="employee_id.l10n_in_esic_number", store=True, readonly=True)
    bank_name = fields.Char(string="Bank Name", related="employee_id.bank_name", store=True, readonly=True)
    ifsc_code = fields.Char(string="IFSC Code", related="employee_id.ifsc_code", store=True, readonly=True)
    account_no = fields.Char(string="Account No", related="employee_id.bank_account", store=True, readonly=True)
    emp_code = fields.Char(string="EMP CODE", related="employee_id.cmr_code", store=True, readonly=True)
    designation = fields.Many2one(string="Designation", related="employee_id.job_id", store=True, readonly=True)
    department = fields.Many2one('hr.department', string="Department", related="employee_id.department_id", store=True, readonly=True)
    work_location = fields.Many2one(string="Work Location", related="employee_id.work_location_id", store=True, readonly=True)
    grade = fields.Char(string="Grade", related="employee_id.grade_id", store=True, readonly=True)
    ctc = fields.Float(string="Actual CTC", related="contract_id.cost_to_company", store=True, readonly=True)

    # --- Computed Fields ---
    month_days = fields.Float(string="Month Days", default=30.0, readonly=True)

    paid_days = fields.Float(string="Paid Days", compute="_compute_paid_days", store=True)
    # absent_days = fields.Float(string="Absent Days", compute='_compute_absent_days', store=True)
    el_days = fields.Float(string="EL Days") # , related='contract_id.el_used', store=True


    # --- Actual Components from Contract ---
    actual_basic = fields.Float(string="Actual BASIC", related="contract_id.basic", store=True, readonly=True)
    actual_hra = fields.Float(string="Actual HRA", related="contract_id.l10n_in_house_rent_allowance_metro_nonmetro", store=True, readonly=True)
    actual_bonus = fields.Float(string="Actual Bonus", related="contract_id.actual_bonus", store=True, readonly=True)
    tds = fields.Float(string="TDS", related="contract_id.l10n_in_tds", store=True, readonly=True)
    insurance = fields.Float(string="INSURANCE", related="contract_id.family_insurance_m", store=True, readonly=True)
    p_tax = fields.Float(string="P.TAX", related="contract_id.p_tax", store=True, readonly=True)
    uniform = fields.Float(string="Uniform Deduction", related="contract_id.uniform", store=True, readonly=True)

    # --- Derived Salary Components (from rules) ---
    basic_salary = fields.Float(string="BASIC", compute="_compute_all_salary_components", store=True, readonly=False)
    hra = fields.Float(string="HRA", compute="_compute_all_salary_components", store=True, readonly=False)
    bonus = fields.Float(string="BONUS", compute="_compute_all_salary_components", store=True, readonly=False)
    earned_gross = fields.Float(string="Earned Gross", compute="_compute_all_salary_components", readonly=True)
    total_earnings = fields.Float(string="Total Earnings", compute="_compute_all_salary_components", readonly=True)
    mng_deduction = fields.Float(string="MNG DED", compute="_compute_all_salary_components", readonly=True)
    pf_er = fields.Float(string="PF ER", compute="_compute_all_salary_components", readonly=True)
    esi = fields.Float(string="ESI", compute="_compute_all_salary_components", readonly=True)
    sal_adv = fields.Float(
        string="SALARY ADVANCE",

        store=True
    )
    loan_adv = fields.Float(
        string="LOAN ADVANCE",

        store=True
    )

    total_deduction = fields.Float(string="Total Deductions", compute="_compute_all_salary_components", readonly=True)
    arrear_days = fields.Float(string="Arrear Days", compute="_compute_all_salary_components", readonly=True)
    arrear_amt = fields.Float(string="Arrear Amt", compute="_compute_all_salary_components", readonly=True)
    net_pay = fields.Float(string="Net Pay", compute="_compute_all_salary_components", readonly=True)
    total_bonus_amt = fields.Float(string="Total Bonus Amount", compute="_compute_all_salary_components", readonly=True)
    payable_amt = fields.Float(string="Payable Amount", compute="_compute_all_salary_components", readonly=True)
    absent_amount = fields.Float(string="Absent Amount", compute="_compute_all_salary_components", readonly=True)


    # --- Custom Components ---
    overtime_cmr = fields.Float(string="Overtime", compute="_compute_overtime_cmr", store=True, readonly=True)
    late_deduction = fields.Float(string="Late Deduction (₹)", compute="_compute_late_deduction", store=True, readonly=True)


    lop_work_entry_count = fields.Integer(
        string="LOP Work Entry Count",
        compute="_compute_lop_work_entry_count",
        store=True,
    )

    present_days = fields.Float(string="Present Days", compute="_compute_present_days", store=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # Only set if not already defined from a contract
        if not res.get('struct_id'):
            regular_struct = self.env['hr.payroll.structure'].search([('name', '=', 'Regular Pay')], limit=1)
            if regular_struct:
                res['struct_id'] = regular_struct.id
        return res





    # ---------------------------------------------------------------
    # COMPUTE METHODS
    # ---------------------------------------------------------------

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_lop_work_entry_count(self):
        """Compute LOP days from validated Time Offs with code 'LEAVE90' within the payslip period."""
        Leave = self.env['hr.leave']

        for payslip in self:
            lop_work_entry_count = 0.0

            if not payslip.employee_id or not payslip.date_from or not payslip.date_to:
                payslip.lop_work_entry_count = 0.0
                continue

            # Fetch all approved Time Offs (LEAVE90) overlapping with payslip duration
            leaves = Leave.search([
                ('employee_id', '=', payslip.employee_id.id),
                ('state', '=', 'validate'),
                ('holiday_status_id.name', '=', 'LOP'),
                ('request_date_from', '<=', payslip.date_to),
                ('request_date_to', '>=', payslip.date_from),
            ])

            # Sum up number_of_days_display from matching leaves
            lop_work_entry_count = sum(leaves.mapped('number_of_days_display'))

            payslip.lop_work_entry_count = lop_work_entry_count

            _logger.info(
                f"Payslip {payslip.name or payslip.id} - Employee {payslip.employee_id.name} "
                f"LOP Days (Time Off LEAVE90): {lop_work_entry_count}"
            )

    @api.depends('line_ids.total')
    def _compute_all_salary_components(self):
        """Map all rule totals into payslip fields."""
        line_values = (self._origin)._get_line_values([
            'CTC', 'BASIC_K', 'HRA', 'BONUS', 'EARNED_GROSS', 'TOTAL_EARNINGS',
            'MNG DED', 'PF_ER', 'SALARY_ADVANCE', 'LOAN_ADVANCE',
            'TOTAL_DEDUCTIONS', 'ARREAR_DAYS', 'ARREAR_AMT',
            'NET_PAY', 'TOTAL_BONUS_AMOUNT', 'PAYABLE_AMOUNT', 'ABSENT_AMT', 'LATE_DEDUCTION','OVER_TIME', 'ESI'
        ])
        for payslip in self:
            pid = payslip._origin.id
            payslip.ctc = line_values['CTC'][pid]['total']
            payslip.basic_salary = line_values['BASIC_K'][pid]['total']
            payslip.hra = line_values['HRA'][pid]['total']
            payslip.bonus = line_values['BONUS'][pid]['total']
            payslip.earned_gross = line_values['EARNED_GROSS'][pid]['total']
            payslip.total_earnings = line_values['TOTAL_EARNINGS'][pid]['total']
            payslip.mng_deduction = line_values['MNG DED'][pid]['total']
            payslip.pf_er = line_values['PF_ER'][pid]['total']
            payslip.sal_adv = line_values['SALARY_ADVANCE'][pid]['total']
            payslip.loan_adv = line_values['LOAN_ADVANCE'][pid]['total']
            payslip.total_deduction = line_values['TOTAL_DEDUCTIONS'][pid]['total']
            payslip.arrear_days = line_values['ARREAR_DAYS'][pid]['total']
            payslip.arrear_amt = line_values['ARREAR_AMT'][pid]['total']
            payslip.net_pay = line_values['NET_PAY'][pid]['total']
            payslip.total_bonus_amt = line_values['TOTAL_BONUS_AMOUNT'][pid]['total']
            payslip.payable_amt = line_values['PAYABLE_AMOUNT'][pid]['total']
            payslip.absent_amount = line_values['ABSENT_AMT'][pid]['total'] if 'ABSENT_AMT' in line_values else 0.0
            payslip.late_deduction = line_values['LATE_DEDUCTION'][pid]['total'] if 'LATE_DEDUCTION' in line_values else 0.0
            payslip.overtime_cmr = line_values['OVER_TIME'][pid]['total'] if 'OVER_TIME' in line_values else 0.0
            payslip.esi = line_values['ESI'][pid]['total'] if 'ESI' in line_values else 0.0


    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_late_deduction(self):
        """Compute total late deduction for this employee and month."""
        for rec in self:
            amount = 0.0
            if rec.employee_id and rec.date_from:
                month = rec.date_from.month
                year = rec.date_from.year
                late_lines = self.env['hr.late.deduction.line'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('month', '=', str(month)),
                    ('year', '=', year),
                ])
                amount = sum(l.deduction_amount for l in late_lines)
            rec.late_deduction = amount

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_overtime_cmr(self):
        """Compute overtime amount for the employee and payslip month."""
        for rec in self:
            overtime = 0.0
            if rec.employee_id and rec.date_from:
                month = rec.date_from.month
                year = rec.date_from.year
                overtime_line = self.env['hr.overtime.line'].search([
                    ('employee_id', '=', rec.employee_id.id),
                    ('month', '=', str(month)),
                    ('year', '=', year),
                ], limit=1)
                overtime = overtime_line.overtime_amount if overtime_line else 0.0
                print("overtime")
            rec.overtime_cmr = overtime

    # @api.depends('employee_id', 'date_from', 'date_to')
    # def _compute_absent_days(self):
    #     """Compute number of unpaid leaves (LEAVE90, LEAVE120)."""
    #     for payslip in self:
    #         if not payslip.employee_id or not payslip.date_from or not payslip.date_to:
    #             payslip.absent_days = 0.0
    #             continue
    #         leaves = self.env['hr.leave'].search([
    #             ('employee_id', '=', payslip.employee_id.id),
    #             ('state', '=', 'validate'),
    #             ('request_date_from', '>=', payslip.date_from),
    #             ('request_date_to', '<=', payslip.date_to),
    #             ('holiday_status_id.work_entry_type_id.code', 'in', ['LEAVE90', 'LEAVE120'])
    #         ])
    #         total_days = sum(leaves.mapped('number_of_days_display')) - payslip.contract_id.leaves_available
    #         payslip.absent_days = total_days



    @api.depends('month_days', 'lop_work_entry_count')
    def _compute_paid_days(self):
        """Compute paid days as total month days minus LOP work entry count."""
        for rec in self:
            if rec.month_days and rec.lop_work_entry_count is not None:
                rec.paid_days = rec.month_days - rec.lop_work_entry_count
            else:
                rec.paid_days = 0.0

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_present_days(self):
        """Compute Present Days = Total Days in month - Total Time Off days."""
        Leave = self.env['hr.leave']

        for payslip in self:
            if not payslip.employee_id or not payslip.date_from or not payslip.date_to:
                payslip.present_days = 0.0
                continue

            # Get all approved leaves in the payslip period (any type)
            leaves = Leave.search([
                ('employee_id', '=', payslip.employee_id.id),
                ('state', '=', 'validate'),
                ('request_date_from', '<=', payslip.date_to),
                ('request_date_to', '>=', payslip.date_from),
            ])

            total_leave_days = sum(leaves.mapped('number_of_days_display'))

            # Compute total days in payslip period (month)
            total_days_in_month = (payslip.date_to - payslip.date_from).days + 1

            # Present days = total days - total leave days
            present_days = total_days_in_month - total_leave_days
            payslip.present_days = present_days

            _logger.info(
                f"Payslip {payslip.name or payslip.id} - Employee {payslip.employee_id.name} | "
                f"Total Month Days: {total_days_in_month} | Leaves: {total_leave_days} | "
                f"Present Days: {present_days}"
            )
    @api.model
    def get_salary_components(self, employee_id, date_from):
        """Return salary component totals for a given employee and year."""
        domain = [('id', '=', employee_id)]
        print(date_from,employee_id)
        if date_from:
            # restrict to that year
            # start_date = f"{year}-01-01"
            # end_date = f"{year}-12-31"
            # domain += [('date_from', '>=', start_date), ('date_to', '<=', end_date)]
            domain += [('date_from', '=', date_from)]

        payslips = self.search(domain)


        hra = 0
        basic = 0
        bonus = 0
        ge_basic=0
        pf=0
        simple_hra=0
        esi=0
        bn=0
        p_tax=0
        total_pf=0
        total_tax_pf=0
        total_bonous_amnt=0
        total_bonous=0

        for slip in payslips:

            print(slip,"llllllllllll")
            for line in slip.line_ids:
                print(line.code,"code.............")
                if line.code == 'ACTUAL_BASIC':
                    basic += line.total
                    print(basic,"actual basic")
                elif line.code == 'ACTUAL_HRA':
                    hra += line.total
                    print(hra,"hra value")
                elif line.code == 'ACTUAL_BONUS':
                    bonus += line.total
                    print(bonus,"bonus value")
                elif line.code == 'BASIC_K':
                    ge_basic += line.total
                    print(ge_basic,"basic")
                elif line.code == 'PF_ER':
                    pf += line.total
                    print(pf,"pf amount")
                elif line.code == 'HRA':
                    simple_hra += line.total
                elif line.code == 'ESI':
                    esi += line.total
                elif line.code == 'BONUS':
                    bn += line.total
                elif line.code == 'P_TAX':
                    p_tax += line.total
                elif line.code == 'TOTAL_BONUS_AMOUNT':
                    total_bonous += line.total


        return {
            'hra': hra,
            'basic': basic,
            'bonus': bonus,
            'ge_basic': ge_basic,
            'pf': pf,
            'simple_hra': simple_hra,
            'esi': esi,
            'bn': bn,
            'total_pf':ge_basic+simple_hra+bn,
            'total_tax_pf':pf+esi+p_tax,
            'TOTAL_BONUS_AMOUNT':total_bonous,
            'p_tax': p_tax,
            'total_bonous_amnt':(ge_basic+simple_hra+bn)-(pf+esi+p_tax),
            'total_months': len(payslips),
            'amount':((ge_basic+simple_hra+bn)-(pf+esi+p_tax))+total_bonous,
        }





