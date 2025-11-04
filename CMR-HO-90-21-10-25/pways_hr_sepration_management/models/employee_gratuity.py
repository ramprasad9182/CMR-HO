# -*- coding: utf-8 -*-
from odoo import fields, models, api, exceptions, _
from odoo.exceptions import ValidationError, UserError
import datetime
from datetime import timedelta


class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    is_paid = fields.Boolean(string="Paid leave")

class HrEmployeeGratuity(models.Model):
    _name = 'hr.employee.gratuity'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Hr Employee Gratuity"
    _order = 'id desc'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('validate', 'Validated'),
        ('approve', 'Approved'),
        ('cancel', 'Cancelled')],
        default='draft')

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    sepration_id = fields.Many2one('hr.employee.sepration', string='Employee', required=True, domain="[('state', '=', 'approved')]")
    revealing_date = fields.Date(related='sepration_id.revealing_date')
    joined_date = fields.Date(string="Joined Date", readonly=True)
    worked_years = fields.Integer(string="Total Work Years", readonly=True)
    last_month_salary = fields.Integer(string="Basic Salary", default=0)
    allowance = fields.Char(string="Dearness Allowance", default=0)
    gratuity_amount = fields.Integer(string="Gratuity Payable", required=True, default=0, readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.user.company_id.currency_id)
    company_id = fields.Many2one('res.company', 'Company',  default=lambda self: self.env.user.company_id)
    unproductive_days = fields.Float(default=0)
    total_days = fields.Integer('Service Days', default=0)
    eligible_days = fields.Integer('Eligible Days', default=0)
    attachment_ids = fields.Many2many("ir.attachment")
    reason = fields.Text(string="Reason", help='Specify reason for gratuity from company')
    count_settlement = fields.Integer(string="Count Settlement", compute="_compute_count_settlement")

    # assigning the sequence for the record
    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('hr.employee.gratuity')
        return super(HrEmployeeGratuity, self).create(vals)

    # Check whether any Gratuity request already exists
    @api.onchange('sepration_id')
    @api.depends('sepration_id')
    def check_request_existence(self):
        for rec in self.filtered(lambda x:x.sepration_id):
            gratuity_request = self.env['hr.employee.gratuity'].search([('sepration_id', '=', rec.sepration_id.id), ('state', 'in', ['draft', 'validate', 'approve'])])
            if gratuity_request:
                raise ValidationError(_('Gratuity request is already processed for this employee'))

    def action_open_settelement(self):
        return {
            'name': _('Settlements'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'hr.employee.settlement',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('gratuity_id', '=', self.id)],
        }

    def _compute_count_settlement(self):
        for gratuity in self:
            gratuity.count_settlement = self.env['hr.employee.settlement'].search_count([('gratuity_id', '=', self.id)])

    def action_create_emp_settement(self):
        employee_id = self.sepration_id.employee_id
        joined_date = employee_id.joining_date
        notice_id = employee_id.notice_id
        settlement_id = self.env['hr.employee.settlement'].search([('gratuity_id', '=', self.id)], limit=1)
        if settlement_id:
            raise ValidationError(_('Employee settelement is already created'))
        journal_id = self.env['account.journal'].search([('is_salary_wages','=', True)], limit=1)
        end_date = fields.Date.today()
        if joined_date and notice_id:
            end_date = fields.Datetime.from_string(joined_date) + timedelta(days=notice_id.days)
        return {
                'name': "Create Employee Settlement",
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'hr.employee.settlement',
                'view_id': self.env.ref('pways_hr_sepration_management.hr_employee_settlements_form').id,
                'context': {
                    'default_from_gratuity': True,
                    'default_gratuity_id': self.id,
                    'default_sepration_id': self.sepration_id and self.sepration_id.id,
                    'default_employee_id': employee_id and employee_id.id, 
                    'default_reason': 'resign',
                    'default_notice_id' : notice_id and notice_id.id,
                    'default_joined_date': joined_date,
                    'default_last_date': end_date,
                    'default_journal_id': journal_id.id if journal_id else False
                },
        }


    def validate_function(self):
        # calculating the years of work by the employee
        amount = 0.0
        self.unproductive_days = self.sepration_id.employee_id.unproductive_days
        worked_years = int(self.revealing_date.year) - int(self.joined_date.year)
        self.worked_years = worked_years
        self.total_days = ((self.revealing_date - self.joined_date).days)
        self.eligible_days = self.total_days - self.unproductive_days

        employee_contract = self.sepration_id.employee_id.contract_ids.filtered(lambda x: x.state == 'open')
        last_month_salary = employee_contract.wage
        allowance_amount = 0.0

        if self.eligible_days < 365:
            self.last_month_salary = last_month_salary
            self.allowance = allowance_amount
            amount = 0

        if self.eligible_days >= 365 and self.eligible_days <= 1825:
            self.last_month_salary = last_month_salary
            self.allowance = allowance_amount
            amount = (self.last_month_salary * (12/365)) * ((21/365) * self.eligible_days) 

        if self.eligible_days > 1825:
            self.last_month_salary = last_month_salary
            self.allowance = allowance_amount
            more_then_five = worked_years - 5
            eligible_days = self.eligible_days - 1825
            less_five_amount = ((self.last_month_salary * (12/365)) * ((21/365 * 1825)))
            more_five_amount = ((self.last_month_salary * (12/365)) * (30/365 * eligible_days))
            amount = less_five_amount + more_five_amount

        self.gratuity_amount = round(amount)
        self.write({'state': 'validate'})

    def approve_function(self):
        self.write({'state': 'approve'})

    def cancel_function(self):
        self.write({'state': 'cancel'})

    def draft_function(self):
        self.write({'state': 'draft'})

    # assigning the join date of the selected employee
    @api.onchange('sepration_id')
    def _on_change_employee_name(self):
        sepration = self.env['hr.employee.sepration'].search([['id', '=', self.sepration_id.id]],limit=1)
        if sepration:
            self.joined_date = sepration.joined_date
