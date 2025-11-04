from odoo import models,fields

class FamilyDetails(models.Model):
    _name = 'family.details'
    _description = 'Family Details'
    _order = 'sequence'

    sequence = fields.Integer(string="S.No")
    name = fields.Char(string="Name")
    dob = fields.Date(string="Date of Birth")
    aadhar_no = fields.Char(string="Aadhaar Number")
    relationship = fields.Selection([
        ('mother', 'Mother'),
        ('father', 'Father'),
        ('husband', 'Husband'),
        ('wife', 'Wife'),
        ('son', 'Son'),
        ('daughter', 'Daughter'),
        ('brother', 'Brother'),
        ('sister', 'Sister'),
    ], string="Relationship")

    employee_id = fields.Many2one('hr.employee', string='Employee')
    applicant_employee_id = fields.Many2one('hr.applicant', string='Employee')
