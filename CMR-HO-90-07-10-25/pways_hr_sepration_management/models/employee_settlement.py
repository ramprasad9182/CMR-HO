# -*- coding: utf-8 -*-
import calendar
import datetime
from datetime import  timedelta
from odoo import fields, models, api, exceptions, _
from odoo.exceptions import ValidationError,UserError
date_format = "%Y-%m-%d"


class HrEmployeeSettlements(models.Model):
    _name = 'hr.employee.settlement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "HR Employee Settlements"
    _order = 'id desc'

    state = fields.Selection([('draft', 'Draft'), ('validate', 'Validated'), ('approve', 'Approved'), ('cancel', 'Cancelled'), ('done', 'Done')], default='draft')
    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    employee_ids = fields.Many2many('hr.employee', compute="_compute_employee_ids")
    employee_dept = fields.Many2one('hr.department', string='Department')
    employee_job_id = fields.Many2one('hr.job', string='Job Tittle')
    joined_date = fields.Date(string="Joined Date")
    last_date = fields.Date(string="Last Working Date")
    worked_years = fields.Integer(string="Service Years")
    notice_id = fields.Many2one('notice.period', string="Notice Period", related="employee_id.notice_id")
    leave_balance = fields.Float(string="Leave Balance")
    notice_period_amount = fields.Float(string="Notice Period Amount")
    allowance = fields.Char(string="Dearness Allowance", default=0)
    total_payable_amount = fields.Float(string="Total Payable Amount", compute="_total_payable_amount")
    basic_salary = fields.Float(string="Basic Salary", required=True, default=0)
    last_month_salary = fields.Integer(string="Last Salary", required=True, default=0)
    gratuity_amount = fields.Integer(string="Gratuity Payable", required=True, default=0, readony=True, help=("Gratuity is calculated based on the equation Last salary * Number of years of service * 15 / 26 "))
    reason = fields.Selection([('resign', 'Resignation'), ('terminate', 'Terminate'), ('retirement', 'Retirement')], default="retirement", string="Type of Sepration", required="True")
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.user.company_id.currency_id)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id)
    request_date = fields.Date('Request Date', default=fields.date.today())
    journal_id = fields.Many2one('account.journal', string="Journal", required=True, domain="[('is_salary_wages', '=', True)]")
    gratuity_id = fields.Many2one('hr.employee.gratuity', default=lambda self: self.env['hr.employee.gratuity'].search([('sepration_id.employee_id', '=', self.employee_id.id)], limit=1))
    remarks = fields.Text()
    leave_pay = fields.Float(string="Leave Pay")
    service_days = fields.Float(string="Service Days")
    revealing_date = fields.Date(string="Revealing Date")
    gross_salary = fields.Float(string="Gross Salary")
    gratuity_ids = fields.One2many('hr.gratuity.balance', 'other_settlement_id')
    leave_ids = fields.One2many('hr.leave.balance', 'other_leave_id')
    other_sattlement_ids = fields.One2many('hr.other.balance', 'other_settlement_id')
    sepration_id = fields.Many2one('hr.employee.sepration')
    net_salary = fields.Float(string="Net Amount")
    other_day = fields.Float(string="Other Day", compute="_compute_other_salary", store=True)
    other_salary = fields.Float(string="Other Salary", compute="_compute_other_salary", store=True)
    count_journal_entry = fields.Integer(string="Journal Count", compute="_compute_count_journal_entry")

    @api.model
    def default_get(self, field):
        result = super(HrEmployeeSettlements, self).default_get(field)
        result['employee_ids'] = self.env['hr.employee.sepration'].search([('state', '=', 'approved')]).mapped('employee_id')
        return result

    # assigning the sequence for the record
    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('hr.employee.settlement')
        return super(HrEmployeeSettlements, self).create(vals)

    @api.depends('other_sattlement_ids')
    def _compute_other_salary(self):
        for settlement in self:
            settlement.other_day = sum(settlement.other_sattlement_ids.mapped('quantity'))
            settlement.other_salary = sum(settlement.other_sattlement_ids.mapped('total'))

    def _compute_employee_ids(self):
        for rec in self:
            rec.employee_ids = self.env['hr.employee.sepration'].search([('state', '=', 'approved')]).mapped('employee_id')

    @api.depends('gratuity_ids', 'leave_ids', 'notice_period_amount', 'other_sattlement_ids')
    def _total_payable_amount(self):
        for rec in self:
            gratual_amount = sum(rec.gratuity_ids.mapped('total'))
            leave_amount = sum(rec.leave_ids.mapped('total'))
            other_amount = sum(rec.other_sattlement_ids.mapped('total'))
            total = gratual_amount  + leave_amount + rec.notice_period_amount + other_amount
            rec.total_payable_amount = total

    def _compute_count_journal_entry(self):
        for settlement in self:
            settlement.count_journal_entry = self.env['account.move'].search_count([('emp_settlement_id', '=', self.id)])

    def action_journal_entries(self):
        journal_ids = self.env['account.move'].search([('emp_settlement_id', '=', self.id)])
        return {
            'name': _('Journal Entries'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', journal_ids.ids)],
        }

    def validate_function(self):
        # calculating the years of work by the employee
        if self.employee_id:
            self.write({'state': 'validate'})

    def approve_function(self):
        if not self.allowance.isdigit() :
            raise ValidationError(_('Allowance value should be numeric !!'))
        self.write({'state': 'approve'})
        amount = ((self.last_month_salary + int(self.allowance)) * int(self.worked_years) * 15) / 26
        self.gratuity_amount = round(amount) if self.state == 'approve' else 0
        self.employee_id.active = False

    def cancel_function(self):
        self.write({'state': 'cancel'})

    def draft_function(self):
        self.write({'state': 'draft'})

    def employee_based_on_amount(self):
        per_based_on = self.sepration_id.per_based_on
        amount = 0.0
        if per_based_on == 'basic':
            amount = (self.basic_salary / 30) if self.basic_salary > 0 else 0
        if per_based_on == 'net':
            amount = (self.net_salary / 30) if self.net_salary > 0 else 0
        if per_based_on == 'gross':
             amount = (self.gross_salary / 30) if self.gross_salary > 0 else 0
        return amount

    def compute_function(self):
        # self.get_unpaid_emp_settlements()
        
        # gratuity lines
        gratuity_data = [(5,0,0)]
        employee_gratuity = self.env['hr.employee.gratuity'].search([('sepration_id.employee_id', '=', self.employee_id.id), ('state', '=', 'approve')])
        for gratuity in employee_gratuity:
            gratuity_data.append((0, 0, {
                'description': "Grauity for %s Days" %gratuity.eligible_days,
                'amount': gratuity.gratuity_amount,
            }))
        self.gratuity_ids = gratuity_data
        
        # leave settelement line
        leave_data = [(5,0,0)]
        allocation_ids = self.env['hr.leave.allocation'].search([('employee_id', '=', self.employee_id.id), ('state', '=', 'validate')])
        time_off_ids = self.env['hr.leave'].search([('employee_id', '=', self.employee_id.id), ('state', '=', 'validate')])
        leave_type_ids = allocation_ids.mapped('holiday_status_id')
        for leave_type in leave_type_ids:
            time_off_days = sum(time_off_ids.filtered(lambda x: x.holiday_status_id == leave_type).mapped('number_of_days'))
            total_allocation_days = sum(allocation_ids.filtered(lambda x: x.holiday_status_id == leave_type).mapped('number_of_days_display'))
            total_qty  = abs(total_allocation_days - time_off_days)
            amount = self.employee_based_on_amount()
            if total_qty > 0:
                leave_data.append((0, 0, {
                    'description': '%s for %s Days' % (leave_type.name, total_qty),
                    'quantity': total_qty,
                    'amount': amount,
                }))
            self.leave_ids = leave_data
        self.leave_balance = sum(self.leave_ids.mapped('quantity'))
        amount = self.employee_based_on_amount()
        self.leave_pay = self.leave_balance * amount

    @api.onchange('employee_id')
    def onchange_employee(self):
        if self.employee_id:
            employee_contract = self.env['hr.contract'].search([('employee_id', '=', self.employee_id.id), ('state', '=', 'open')], limit=1)
            if not employee_contract:
                raise ValidationError(("Employee %s does not have any running contract.") % (self.employee_id.name))
            journal_id = self.env['account.journal'].search([('is_salary_wages', '=', True), ('company_id', '=', self.employee_id.company_id.id)], limit=1)
            employee_gratuity = self.env['hr.employee.gratuity'].search([('sepration_id.employee_id', '=', self.employee_id.id), ('state', '=', 'approve')],limit=1)
            employee_resignation = self.env['hr.employee.sepration'].search([('employee_id', '=', self.employee_id.id), ('state', '=', 'approved')], limit=1)
            self.sepration_id = employee_resignation.id
            if employee_resignation:
                self.reason = 'resign'
            # Assgin values
            self.notice_id = employee_resignation.notice_id.id
            self.last_month_salary = employee_gratuity.last_month_salary
            self.worked_years = employee_gratuity.worked_years
            self.employee_dept = self.employee_id.department_id and self.employee_id.department_id.id 
            self.employee_job_id = self.employee_id.job_id and self.employee_id.job_id.id 
            self.joined_date = self.employee_id.joining_date
            self.basic_salary = employee_contract.wage
            self.gratuity_id = employee_gratuity and employee_gratuity.id
            self.journal_id = journal_id and journal_id.id
            self.service_days = employee_gratuity.total_days
            self.revealing_date = self.gratuity_id and self.gratuity_id.revealing_date
            self.gross_salary = employee_contract.gross_amount
            self.net_salary = employee_contract.net_amount
            self.last_date = self.revealing_date - timedelta(days=1) if self.revealing_date else False

    #Create Journal Entries 
    def create_extra_journal_entries(self):
        line_ids = []
        move_id = self.env['account.move'].search([('emp_settlement_id', '=', self.id)], limit=1)
        if move_id:
            return True

        move_obj = self.env['account.move']
        employee_id = self.employee_id
        partner_id = employee_id.user_id.partner_id
        journal_id = self.journal_id
        timenow = fields.Date.today()
        company_id = self.env.user.company_id
        advance_credit_account_id = company_id.sepration_credit_account_id
        advance_debit_account_id = company_id.sepration_debit_account_id
        #Gratuity Entry Create Journal
        for gratuity in self.gratuity_ids:
            move_line_ids = []
            gratuity_move = {
                'ref': gratuity.description,
                'journal_id': journal_id and journal_id.id,
                'date': timenow,
                'state': 'draft',
                'emp_settlement_id': self.id,
                'move_type': 'entry',
            }

            # debit move lines
            move_line_ids.append((0, 0, {
                'name': "%s - %s"%(self.employee_id.name, "Gratuity"),
                'partner_id': partner_id and partner_id.id,
                'account_id': advance_debit_account_id.id,
                'journal_id': journal_id.id,
                'date': timenow,
                'debit': gratuity.total > 0.0 and gratuity.total or 0.0,
                'credit': gratuity.total < 0.0 and -gratuity.total or 0.0,
            }))
            # credit move lines
            move_line_ids.append((0, 0, {
                'name': "%s - %s"%(self.employee_id.name, "Gratuity"),
                'partner_id': partner_id and partner_id.id,
                'account_id': advance_credit_account_id.id,
                'journal_id': journal_id.id,
                'date': timenow,
                'debit': gratuity.total < 0.0 and -gratuity.total or 0.0,
                'credit': gratuity.total > 0.0 and gratuity.total or 0.0,
            }))
            gratuity_move.update({'line_ids': move_line_ids})
            gratuity_move_id = move_obj.create(gratuity_move)

        # leave settelement
        for leave in self.leave_ids:
            move_line_ids = []
            leave_move = {
            'ref': leave.description,
            'journal_id': journal_id and journal_id.id,
            'date': timenow,
            'state': 'draft',
            'emp_settlement_id': self.id,
            'move_type': 'entry',
            }

            # debit move lines
            move_line_ids.append((0, 0, {
                'name': "%s - %s"%(self.employee_id.name, "Leave"),
                'partner_id': partner_id and partner_id.id,
                'account_id': advance_debit_account_id.id,
                'journal_id': journal_id.id,
                'date': timenow,
                'debit': leave.total > 0.0 and leave.total or 0.0,
                'credit': leave.total < 0.0 and -leave.total or 0.0,
            }))
            # credit move lines
            move_line_ids.append((0, 0, {
                'name': "%s - %s"%(self.employee_id.name, "Leave"),
                'partner_id': partner_id and partner_id.id,
                'account_id': advance_credit_account_id.id,
                'journal_id': journal_id.id,
                'date': timenow,
                'debit': leave.total < 0.0 and -leave.total or 0.0,
                'credit': leave.total > 0.0 and leave.total or 0.0,
            }))
            leave_move.update({'line_ids': move_line_ids})
            leave_move_id = move_obj.create(leave_move)

        # Other details journal
        for other in self.other_sattlement_ids:
            move_line_ids = []
            other_move = {
            'ref': other.description,
            'journal_id': journal_id and journal_id.id,
            'date': timenow,
            'state': 'draft',
            'emp_settlement_id': self.id,
            'move_type': 'entry',
            }

            # debit move lines
            move_line_ids.append((0, 0, {
                'name': "%s - %s"%(self.employee_id.name, other.description),
                'partner_id': partner_id and partner_id.id,
                'account_id': advance_debit_account_id.id,
                'journal_id': journal_id.id,
                'date': timenow,
                'debit': other.total > 0.0 and other.total or 0.0,
                'credit': other.total < 0.0 and -other.total or 0.0,
            }))

            # credit move lines
            move_line_ids.append((0, 0, {
                'name': "%s - %s"%(self.employee_id.name, other.description),
                'partner_id': partner_id and partner_id.id,
                'account_id': advance_credit_account_id.id,
                'journal_id': journal_id.id,
                'date': timenow,
                'debit': other.total < 0.0 and -other.total or 0.0,
                'credit': other.total > 0.0 and other.total or 0.0,
            }))
            other_move.update({'line_ids': move_line_ids})
            leave_move_id = move_obj.create(other_move)
        self.write({'state': 'done'})
        return True
