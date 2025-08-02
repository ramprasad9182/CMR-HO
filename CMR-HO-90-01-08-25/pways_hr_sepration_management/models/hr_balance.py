# -*- coding: utf-8 -*-
from odoo import fields, models, api, exceptions, _
from odoo.exceptions import ValidationError, UserError


class HrLeaveBalance(models.Model):
    _name = 'hr.leave.balance'
    _description = "Hr Leave Balance"

    other_leave_id = fields.Many2one('hr.employee.settlement')
    quantity = fields.Float(string="Quantity",default=1)
    description = fields.Char(string="Description")
    remarks = fields.Char(string="Remarks")
    amount = fields.Float(string="Amount")
    total = fields.Float(string="Total", compute="_compute_total")

    @api.depends('quantity','amount')
    def _compute_total(self):
        for record in self:
            record.total= record.quantity * record.amount

    def report_leave_data(self):
        if self.other_leave_id:
            allocation_id =  self.env['hr.leave.allocation'].search([('employee_id', '=', self.other_leave_id.employee_id.id)], limit=1)
        return allocation_id


class HrGratuityBalance(models.Model):
    _name = 'hr.gratuity.balance'
    _description = "Hr Gratuity Balance"

    description = fields.Char(string="Description")
    remarks = fields.Char(string="Remarks")
    quantity = fields.Float(string="Quantity",default=1)
    amount = fields.Float(string="Amount")
    total = fields.Float(string="Total", compute="_compute_total")
    other_settlement_id = fields.Many2one('hr.employee.settlement')

    @api.depends('quantity','amount')
    def _compute_total(self):
        for record in self:
            record.total= record.quantity * record.amount

class HrOtherBalance(models.Model):
    _name = 'hr.other.balance'
    _description = "Hr Other Balance"

    description = fields.Char(string="Description")
    remarks = fields.Char(string="Remarks")
    quantity = fields.Float(string="Quantity",default=1)
    amount = fields.Float(string="Amount")
    total = fields.Float(string="Total", compute="_compute_total")
    other_settlement_id = fields.Many2one('hr.employee.settlement')

    @api.depends('quantity','amount')
    def _compute_total(self):
        for record in self:
            record.total= record.quantity * record.amount
