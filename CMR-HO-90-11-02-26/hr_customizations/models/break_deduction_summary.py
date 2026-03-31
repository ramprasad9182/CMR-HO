from odoo import models, fields, api
from dateutil.relativedelta import relativedelta

class BreakDeductionSummary(models.Model):
    _name = "break.deduction.summary"
    _description = "Break Deduction Summary"

    month = fields.Selection([
        ('1','January'),('2','February'),('3','March'),
        ('4','April'),('5','May'),('6','June'),
        ('7','July'),('8','August'),('9','September'),
        ('10','October'),('11','November'),('12','December'),
    ], required=True)

    year = fields.Char(required=True)
    line_ids = fields.One2many("break.deduction.summary.line", "master_id")
    select_all = fields.Boolean()

    @api.onchange('select_all')
    def _onchange_select_all(self):
        for l in self.line_ids:
            l.is_selected = self.select_all

    def generate_report(self):
        self.line_ids.unlink()
        start_date = fields.Date.from_string(f"{self.year}-{self.month}-01")
        end_date = start_date + relativedelta(months=1, days=-1)

        uploads = self.env["hr.upload"].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ])

        data = {}
        for u in uploads:
            emp = u.employee_name
            if emp.id not in data:
                data[emp.id] = {
                    'employee_id': emp.id,
                    'employee_code': u.employee_code,
                    'break_total': 0.0,
                }
            data[emp.id]['break_total'] += u.break_delay_amount or 0.0

        for vals in data.values():
            self.env["break.deduction.summary.line"].create({
                "master_id": self.id,
                **vals
            })


    def delete_selected_lines(self):
        for rec in self:
            selected = rec.line_ids.filtered(lambda l: l.is_selected)
            selected.unlink()


class BreakDeductionSummaryLine(models.Model):
    _name = "break.deduction.summary.line"

    master_id = fields.Many2one("break.deduction.summary")
    employee_id = fields.Many2one("hr.employee")
    employee_code = fields.Char()
    break_total = fields.Float()
    is_selected = fields.Boolean(default=True)
