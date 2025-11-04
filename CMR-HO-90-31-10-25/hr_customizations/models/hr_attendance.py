from odoo import models,fields,api,_


class HrAttendance(models.Model):
    _inherit = "hr.attendance"


    date = fields.Date('Date ')
    check_in_attendance = fields.Datetime(string="Check In", default=fields.Datetime.now, required=False, tracking=False)
    check_out_attendance = fields.Datetime(string="Check Out", tracking=False)
    ctc_type = fields.Selection([
        ('with_bonus', 'With Bonus'),
        ('without_bonus', 'Without Bonus'),
        ('non_ctc', 'Non Ctc'),
    ], string='CTC Type', related='employee_id.ctc_type', store=True)
    morning_session = fields.Selection([
        ('Present', 'Present'),
        ('Absent', 'Absent')
    ], string="Morning Session")
    afternoon_session = fields.Selection([
        ('Present', 'Present'),
        ('Absent', 'Absent')
    ], string="Afternoon Session")
