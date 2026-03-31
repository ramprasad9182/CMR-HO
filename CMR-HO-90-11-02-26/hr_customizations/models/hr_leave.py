from odoo import models, fields

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    emp_code = fields.Char(
        string="Employee Code",
        related="employee_id.barcode",
        store=True,
        readonly=True,
    )
