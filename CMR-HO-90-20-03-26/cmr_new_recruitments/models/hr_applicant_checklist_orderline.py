from odoo import models,fields,api,_

class HrApplicant(models.Model):
    _name = 'hr.applicant.checklist.orderline'

    sequence = fields.Integer(string="S.No")

    check_list_id = fields.Many2one("hr.applicant")
    check_list_master_id = fields.Many2one("check.list")

    selection = fields.Selection([('yes', 'YES'), ('no', 'NO')], string="Yes/No")
