from odoo import models, fields

class GradeMaster(models.Model):
    _name = 'grade.master'
    _description = 'Grade Master'

    name = fields.Char(string='Grade Name', required=True)
    department_id = fields.Many2one('hr.department', string="Department")
    job_id = fields.Many2one('hr.job', string="Designation")