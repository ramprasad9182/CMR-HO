from odoo import models, fields

class EmployeeReference(models.Model):
    _name = 'employee.reference'
    _description = 'Employee Reference'

    employee_id = fields.Many2one('hr.employee', string="Employee", ondelete="cascade")
    applicant_employee_id = fields.Many2one('hr.applicant', string="Employee", ondelete="cascade")

    name = fields.Char(string="Reference Name", required=True)
    phone = fields.Char(string="Phone Number")
