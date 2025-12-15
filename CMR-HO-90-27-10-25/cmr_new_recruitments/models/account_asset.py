from odoo import models, fields

class AccountAsset(models.Model):

    _inherit = 'account.asset'

    employee_id_nhcl_xpath=fields.Many2one('hr.employee',string='Employee')


