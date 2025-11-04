from odoo import models,fields,api

class ProfessionalDetails(models.Model):
    _name = 'professional.details'
    _description = 'Professional Details'
    _order = 'sequence'


    employee_id = fields.Many2one('hr.employee', string="Employee", ondelete='cascade')
    sequence = fields.Integer(string="S.No")
    company_name = fields.Char(string="Company Name")
    designation = fields.Char(string="Designation")
    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    years_experience = fields.Float(string="Years of Experience")

    applicant_id = fields.Many2one('hr.applicant', string="Applicant", ondelete='cascade')


