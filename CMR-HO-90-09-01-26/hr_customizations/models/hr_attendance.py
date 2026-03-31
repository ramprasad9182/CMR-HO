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

    employee_code = fields.Char(
        string='Employee Code',
        related='employee_id.cmr_code',
        store=True,
        readonly=True
    )
    designation_id = fields.Many2one(
        'hr.job',
        string="Designation",
        related='employee_id.job_id',
        store=True,
        readonly=True
    )
    department_id = fields.Many2one('hr.department', string="Department", related='employee_id.department_id', store=True,readonly=True)
    ctc_type = fields.Selection([
        ('with_bonus', 'With Bonus'),
        ('without_bonus', 'Without Bonus'),
        ('non_ctc', 'Non Ctc'),
    ],
        string='CTC Type',
        related='employee_id.ctc_type',
        store=True,
        readonly=True
    )

    company_id = fields.Many2one(
        'res.company',
        string="Company",
        related='employee_id.company_id',
        store=True,
        readonly=True
    )

    division_id = fields.Many2one(
        'product.category',
        string='Division',
        domain=[('parent_id', '=', False)],
        related='employee_id.division_id',
        store=True,
        readonly=True
    )
    difference_check_in = fields.Char(string="IN Difference (mins)")
    difference_check_out = fields.Char(string="OUT Difference (mins)")
    total_working_hours = fields.Char(string="Total Working Hours")
    full_day_status = fields.Char(string="Full Day Status")
    lunch_in = fields.Char("Lunch In")
    lunch_out = fields.Char("Lunch Out")
    break_in = fields.Char("Break In")
    break_out = fields.Char("Break Out")
    lunch_delay = fields.Char("Lunch Delay (HH:MM)")
    break_delay = fields.Char("Break Delay (HH:MM)")
    lunch_delay_amount = fields.Float("Lunch Deduction Amount")
    break_delay_amount = fields.Float("Break Deduction Amount")
    lunch_addition_amount = fields.Float(string="Lunch Addition Amount")
