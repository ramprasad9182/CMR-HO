from odoo import models, fields, api

class EmployeeEducation(models.Model):
    _name = 'employee.education'
    _order = 'sequence'
    _description = 'Employee Education Details'

    employee_id = fields.Many2one('hr.employee', string="Employee", ondelete='cascade')
    applicant_employee_id = fields.Many2one('hr.applicant', string="Employee", ondelete='cascade')

    sequence = fields.Integer(string="S.No")
    degree = fields.Selection([
        ('ssc', 'SSC'),
        ('inter', 'Inter'),
        ('graduate', 'Graduate'),
        ('bachelor', 'Bachelor Degree'),
        ('masters', 'Masters Degree'),
        ('doctoral', 'Doctoral Degree'),
    ], string="Degree")
    date_from = fields.Date(string="From Date")
    date_to = fields.Date(string="To Date")
    year_of_passing = fields.Char(string="Year of Passing")




