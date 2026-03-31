# -*- coding: utf-8 -*-
import datetime
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
date_format = "%Y-%m-%d"

class NoticePeriod(models.Model):
    _name = 'notice.period'

    name = fields.Char()
    days = fields.Float()

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    resign_date = fields.Date('Resign Date')
    joining_date = fields.Date(string="Join Date", help='Joining date of the employee')
    notice_id = fields.Many2one('notice.period', string="Notice Period")
    unproductive_days = fields.Float()

class HrEmployeeSepration(models.Model):
    _name = 'hr.employee.sepration'
    _inherit = ['mail.thread','mail.activity.mixin']
    _rec_name = 'employee_id'
    _order = 'id desc'

    def _get_employee_id(self):
        employee_rec = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        return employee_rec.id

    name = fields.Char(string='Name', required=True, copy=False, readonly=True, index=True, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string="Employee", help='Name of the employee for whom the request is creating')
    department_id = fields.Many2one('hr.department', string="Department", related='employee_id.department_id', help='Department of the employee')
    joined_date = fields.Date(string="Join Date", required=True, help='Joining date of the employee')
    revealing_date = fields.Date(string="Releaving Date", required=True, default=fields.Date.today(), help='Date on which he is revealing from the company')
    confirm_date = fields.Date(string="Confirm Date", help='Date on which the request is confirmed')
    approved_date = fields.Date(string="Approved Date", help='The date approved for the releaving')
    reason = fields.Text(string="Reason", help='Specify reason for sepration from company')
    state = fields.Selection([('draft', 'Draft'), ('confirm', 'Confirm'), ('approved', 'Approved'), ('cancel', 'Cancel')], string='Status', default='draft')
    duration_type = fields.Selection([('one', '1 Year'), ('one2five', '1 to 5 Year'), ('morethen5year', 'More Then 5 Year')], string='Duration', compute="_compute_type", store=True)
    notice_id = fields.Many2one('notice.period', string="Notice Period", related="employee_id.notice_id")
    sepration_type = fields.Selection([('resign', 'Resignation'), ('terminate', 'Terminate'), ('retirement', 'Retirement'),('other', 'Other')], default="retirement", string="Type of Sepration", required="True")
    attachment_ids = fields.Many2many("ir.attachment")
    per_based_on = fields.Selection([('basic', 'BASIC'), ('gross', 'GROSS'), ('net', 'NET')], string="Leave Settlement Based On", default="basic")
    count_settlement = fields.Integer(string="Count Settlement", compute='_compute_count_settlemet_gratuity')
    count_gratuity = fields.Integer(string="Count Gratuity", compute='_compute_count_settlemet_gratuity')

    @api.onchange('employee_id')
    def set_join_date(self):
        if self.employee_id and not self.employee_id.joining_date:
            raise ValidationError(_('Please set started date on employee'))
        self.joined_date = self.employee_id.joining_date

    def _compute_count_settlemet_gratuity(self):
        for sepration in self:
            sepration.count_settlement = self.env['hr.employee.settlement'].search_count([('sepration_id', '=', self.id)])
            sepration.count_gratuity = self.env['hr.employee.gratuity'].search_count([('sepration_id', '=', self.id)])

    @api.depends('joined_date')
    def _compute_type(self):
        difference = relativedelta(fields.Date.today(), self.joined_date).years
        if difference <= 1:
            self.duration_type = 'one'
        if difference > 1 and difference <=5:
            self.duration_type = 'one2five'
        if difference > 5:
            self.duration_type = 'morethen5year'

    @api.model
    def create(self, vals):
        # assigning the sequence for the record
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.employee.sepration') or _('New')
        res = super(HrEmployeeSepration, self).create(vals)
        return res

    @api.constrains('employee_id')
    def check_employee(self):
        for rec in self:
            if not self.env.user.has_group('hr.group_hr_user'):
                if rec.employee_id.user_id.id and rec.employee_id.user_id.id != self.env.uid:
                    raise ValidationError(_('You cannot create request for other employees'))


    @api.constrains('joined_date')
    def _check_dates(self):
        # validating the entered dates
        resignation_request = self.env['hr.employee.sepration'].search([('employee_id', '=', self.employee_id.id), ('state', 'in', ['confirm', 'approved'])])
        for rec in self:
            if resignation_request:
                raise ValidationError(_('There is a resignation request in confirmed or'
                                        ' approved state for this employee'))
            if rec.joined_date >= fields.Date.today():
                raise ValidationError(_('Releaving date must be anterior to joining date'))

    def confirm_resignation(self):
        for rec in self:
            rec.state = 'confirm'
            rec.revealing_date = datetime.now() + timedelta(days= rec.notice_id.days)
            rec.confirm_date = datetime.now()
            rec.approved_date = datetime.now()

    def cancel_resignation(self):
        for rec in self:
            rec.state = 'cancel'

    def reject_resignation(self):
        for rec in self:
            rec.state = 'cancel'

    def approve_resignation(self):
        for rec in self:
            if not rec.approved_date:
                raise ValidationError(_('Enter Approved Releaving Date'))
            if rec.approved_date and rec.revealing_date:
                rec.employee_id.write({'resign_date': self.revealing_date})
                rec.state = 'approved'

    def update_employee_status(self):
        resignation = self.env['hr.employee.sepration'].search([('state', '=', 'approved')])
        for rec in resignation:
            if rec.approved_date <= fields.Date.today() and rec.employee_id.active:
                rec.employee_id.resign_date = rec.approved_date

    def get_settlements(self):
        settlement_id = self.env['hr.employee.settlement'].search([('sepration_id', '=', self.id)], limit=1)
        return {
            'name': _('Settlement'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'hr.employee.settlement',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', '=', settlement_id.id)],
        }

    def get_gratuity(self):
        gratuity_id = self.env['hr.employee.gratuity'].search([('sepration_id', '=', self.id)], limit=1)
        return {
            'name': _('Gratuity'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'hr.employee.gratuity',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', '=', gratuity_id.id)],
        }

    def action_create_emp_gratuity(self):
        employee_id = self.employee_id.id
        joined_date = self.joined_date
        return {
                'name': "Create Employee Gratuity",
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'hr.employee.gratuity',
                'view_id': self.env.ref('pways_hr_sepration_management.employee_gratuity_form').id,
                'context': {
                    'default_sepration_id': self.id,
                    'default_reason': 'resign',
                    'default_joined_date': joined_date,
                },
        }