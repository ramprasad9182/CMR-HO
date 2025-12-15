import io
import logging
import re
import xlrd
from dateutil.relativedelta import relativedelta

from odoo import models,fields,api,_
import base64
from io import BytesIO
import openpyxl
import pytz
from datetime import datetime, timedelta, time, date
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import calendar
import traceback
_logger = logging.getLogger(__name__)


class Hrupload(models.Model):
    _name = "hr.upload"


    date = fields.Date('Date')
    employee_code = fields.Char('Employee Code')
    your_datetime = fields.Datetime(string='Check in', compute='_compute_your_datetime')
    your_checkout_datetime = fields.Datetime(string='Check-Out', compute='_compute_your_checkout_datetime',
                                             store=True)
    employee_name = fields.Many2one('hr.employee', string="Employee Name", required=True)
    check_in_attendance = fields.Char(string="Check In")
    check_out_attendance = fields.Char(string="Check Out")
    difference_check_in = fields.Char(string="IN Difference (mins)", compute='_compute_attendance', store=True)
    difference_check_out = fields.Char(string="OUT Difference (mins)", compute='_compute_attendance', store=True)
    total_working_hours = fields.Char(string="Total Working Hours", compute='_compute_attendance', store=True)
    attendance_status = fields.Selection([
        ('grace', 'Grace'),
        ('early', 'Early'),
        ('late', 'Late'),
        ('others', 'Others')
    ], string="Attendance Status", compute='_compute_attendance', store=True)
    late_deduction = fields.Char(string="Late Deduction(Rupees)", compute="_compute_late_deduction", store=True)
    overtime_amount = fields.Char(string="Overtime Amount (₹)", compute="_compute_overtime_amount", store=True)
    morning_session = fields.Selection([
        ('Present', 'Present'),
        ('Absent', 'Absent')
    ], string="Morning Session", compute='_compute_full_day_status', store=True)
    afternoon_session = fields.Selection([
        ('Present', 'Present'),
        ('Absent', 'Absent')
    ], string="Afternoon Session", compute='_compute_full_day_status', store=True)

    full_day_status = fields.Char(string="Full Day Status", compute='_compute_full_day_status', store=True)

    ctc_type = fields.Selection([
        ('with_bonus', 'With Bonus'),
        ('without_bonus', 'Without Bonus'),
        ('non_ctc', 'Non Ctc'),
    ], string='CTC Type', related='employee_name.ctc_type', store=True, readonly=True)
    designation_id = fields.Many2one('hr.job', string="Designation", related='employee_name.job_id', store=True,
                                     readonly=True)
    department_id = fields.Many2one('hr.department', string="Department", related='employee_name.department_id', store=True,readonly=True)

    company_id = fields.Many2one('res.company', string="Company", related='employee_name.company_id', store=True,
                                 readonly=True)
    division_id = fields.Many2one(
        'product.category',
        string='Division',
        domain=[('parent_id', '=', False)],
        related='employee_name.division_id', store=True, readonly=True
    )

    overtime_hours = fields.Char(
        string="Overtime (Hours)",
        compute="_compute_overtime_hours",
        store=True,
        help="Shows extra hours worked after 22:00"
    )



    @api.depends('check_out_attendance')
    def _compute_overtime_hours(self):
        for rec in self:
            rec.overtime_hours = "0:00"

            if not rec.check_out_attendance:
                continue

            try:
                # ✅ Get first overtime slab (lowest start_time)
                first_slab = self.env['hr.overtime.master'].search([], order="start_time asc", limit=1)
                if not first_slab:
                    continue

                # Convert string times (HH:MM) to datetime.time
                check_out_time = datetime.strptime(rec.check_out_attendance.strip(), "%H:%M").time()
                start_time = datetime.strptime(first_slab.start_time.strip(), "%H:%M").time()

                # Combine with today's date
                today = datetime.today()
                start_dt = datetime.combine(today, start_time)
                check_out_dt = datetime.combine(today, check_out_time)

                # ✅ If check-out is before start → no OT
                if check_out_time <= start_time:
                    rec.overtime_hours = "0:00"
                    continue

                # ✅ If check-out crosses midnight (e.g. 02:00 next day)
                if check_out_time < start_time:
                    check_out_dt += timedelta(days=1)

                # ✅ Calculate overtime
                diff = check_out_dt - start_dt
                total_minutes = int(diff.total_seconds() / 60)
                hours = total_minutes // 60
                minutes = total_minutes % 60
                rec.overtime_hours = f"{hours}:{minutes:02d}"

            except Exception:
                rec.overtime_hours = "0:00"

    @api.depends('check_out_attendance')
    def _compute_overtime_amount(self):
        for rec in self:
            rec.overtime_amount = 0.0

            if rec.check_out_attendance:
                try:
                    # Convert check_out_attendance (HH:MM) to datetime.time
                    try:
                        check_out_time = datetime.strptime(rec.check_out_attendance, "%H:%M:%S").time()
                    except ValueError:
                        check_out_time = datetime.strptime(rec.check_out_attendance, "%H:%M").time()

                    # Fetch all overtime rules
                    masters = self.env['hr.overtime.master'].search([])

                    for master in masters:
                        try:
                            try:
                                start_time = datetime.strptime(master.start_time, "%H:%M:%S").time()
                                end_time = datetime.strptime(master.end_time, "%H:%M:%S").time()
                            except ValueError:
                                start_time = datetime.strptime(master.start_time, "%H:%M").time()
                                end_time = datetime.strptime(master.end_time, "%H:%M").time()

                            # ✅ If check-out is between start and end → assign overtime amount
                            if start_time <= check_out_time <= end_time:
                                rec.overtime_amount = master.overtime_amount
                                break
                        except Exception:
                            continue

                except Exception:
                    rec.overtime_amount = 0.0
            else:
                rec.overtime_amount = 0.0

    @api.depends(
        'check_in_attendance',
        'check_out_attendance',
        'date',
        'employee_name',
        'employee_name.resource_calendar_id',
        'employee_name.resource_calendar_id.attendance_ids',
        'employee_name.resource_calendar_id.attendance_ids.hour_from',
        'employee_name.resource_calendar_id.attendance_ids.hour_to',
        'employee_name.resource_calendar_id.attendance_ids.day_period',
    )
    def _compute_full_day_status(self):
        for rec in self:
            rec.full_day_status = 'Absent (Full Day)'
            rec.morning_session = 'Absent'
            rec.afternoon_session = 'Absent'

            if not rec.employee_name or not rec.date:
                _logger.debug("hr.upload[%s]: missing employee or date", rec.id)
                continue

            calendar = rec.employee_name.resource_calendar_id
            if not calendar:
                _logger.debug("hr.upload[%s]: employee %s has no calendar", rec.id, rec.employee_name.name)
                continue

            # parse check in/out times robustly (allow 'HH:MM' or 'HH:MM:SS')
            def parse_time_str(tstr):
                if not tstr:
                    return None
                for fmt in ("%H:%M:%S", "%H:%M"):
                    try:
                        return datetime.strptime(tstr, fmt).time()
                    except Exception:
                        continue
                # if already a time/datetime object, handle gracefully
                if isinstance(tstr, datetime):
                    return tstr.time()
                if isinstance(tstr, time):
                    return tstr
                return None

            tin = parse_time_str(rec.check_in_attendance)
            tout = parse_time_str(rec.check_out_attendance)
            if not tin or not tout:
                _logger.debug("hr.upload[%s]: could not parse times: in=%s out=%s", rec.id, rec.check_in_attendance,
                              rec.check_out_attendance)
                continue

            # combine with rec.date so all datetimes share same date
            check_in_dt = datetime.combine(rec.date, tin)
            check_out_dt = datetime.combine(rec.date, tout)

            weekday = rec.date.weekday()
            sessions = calendar.attendance_ids.filtered(lambda a: int(a.dayofweek) == weekday)
            if not sessions:
                _logger.debug("hr.upload[%s]: no sessions for weekday %s", rec.id, weekday)
                continue

            # thresholds
            MORNING_MIN_HOURS = 1.5
            AFTERNOON_MIN_HOURS = 4.5
            EPS = 1e-6  # float tolerance

            for session in sessions:
                # compute session start/end on the same rec.date
                start_time = time(int(session.hour_from), int((session.hour_from % 1) * 60))
                end_time = time(int(session.hour_to), int((session.hour_to % 1) * 60))
                session_start = datetime.combine(rec.date, start_time)
                session_end = datetime.combine(rec.date, end_time)

                # If session_end <= session_start skip invalid slot
                if session_end <= session_start:
                    _logger.warning("hr.upload[%s]: invalid session times %s-%s", rec.id, session.hour_from,
                                    session.hour_to)
                    continue

                # compute overlap (inclusive at boundaries)
                overlap_start = max(check_in_dt, session_start)
                overlap_end = min(check_out_dt, session_end)
                worked_seconds = (overlap_end - overlap_start).total_seconds() if overlap_end > overlap_start else 0.0
                worked_hours = worked_seconds / 3600.0

                _logger.debug(
                    "hr.upload[%s] emp=%s period=%s session=%s-%s check=%s-%s worked=%.3f",
                    rec.id, rec.employee_name.name, session.day_period,
                    session_start.time(), session_end.time(),
                    check_in_dt.time(), check_out_dt.time(), worked_hours
                )

                # apply threshold per session
                if session.day_period == 'morning':
                    if worked_hours + EPS >= MORNING_MIN_HOURS:
                        rec.morning_session = 'Present'
                elif session.day_period == 'afternoon':
                    if worked_hours + EPS >= AFTERNOON_MIN_HOURS:
                        rec.afternoon_session = 'Present'

            # decide final full_day_status
            if rec.morning_session == 'Present' and rec.afternoon_session == 'Present':
                rec.full_day_status = 'Present (Full Day)'
            elif rec.morning_session == 'Present' and rec.afternoon_session == 'Absent':
                rec.full_day_status = 'First Session Present and Second Session Absent'
            elif rec.morning_session == 'Absent' and rec.afternoon_session == 'Present':
                rec.full_day_status = 'First Session Absent and Second Session Present'
            else:
                rec.full_day_status = 'Absent (Full Day)'

    @api.depends(
        'check_in_attendance',
        'check_out_attendance',
        'date',
        'employee_name',
        'employee_name.resource_calendar_id',
    )
    def _compute_attendance(self):
        for rec in self:
            rec.difference_check_in = "0:00"
            rec.difference_check_out = "0:00"
            rec.total_working_hours = "0:00"
            rec.attendance_status = 'others'

            emp = rec.employee_name or rec.employee_id
            if not emp or not emp.resource_calendar_id:
                continue

            base_date = rec.date or fields.Date.today()
            if isinstance(base_date, fields.Date):
                base_date = datetime.strptime(str(base_date), "%Y-%m-%d").date()

            weekday = base_date.weekday()

            shifts_today = emp.resource_calendar_id.attendance_ids.filtered(
                lambda s: int(s.dayofweek) == weekday and not (s.name.lower() in ['break', 'lunch'])
            )
            if not shifts_today:
                continue

            shifts_today = shifts_today.sorted(key=lambda l: l.hour_from)

            def parse_dt(val):
                if not val:
                    return None
                if isinstance(val, datetime):
                    return val
                if isinstance(val, (int, float)):
                    h = int(val)
                    m = int(round((val - h) * 60))
                    return datetime.combine(base_date, time(h, m))
                if isinstance(val, str):
                    m = re.match(r'^(\d{1,2}):(\d{1,2})(?::(\d{1,2}))?$', val.strip())
                    if m:
                        h, min_, sec = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
                        return datetime.combine(base_date, time(h, min_, sec))
                return None

            check_in_dt = parse_dt(rec.check_in_attendance)
            check_out_dt = parse_dt(rec.check_out_attendance)

            if not check_in_dt or not check_out_dt:
                continue

            # ---------- FIND CORRECT SHIFT FOR CHECK-IN ----------
            shift_in = None
            for s in shifts_today:
                s_start = datetime.combine(base_date, time(int(s.hour_from), int(round((s.hour_from % 1) * 60))))
                s_end = datetime.combine(base_date, time(int(s.hour_to), int(round((s.hour_to % 1) * 60))))
                if s_start <= check_in_dt <= s_end:
                    shift_in = s
                    break
            if not shift_in:
                shift_in = shifts_today[0]

            # ---------- FIND CORRECT SHIFT FOR CHECK-OUT ----------
            shift_out = None
            for s in reversed(shifts_today):
                s_start = datetime.combine(base_date, time(int(s.hour_from), int(round((s.hour_from % 1) * 60))))
                s_end = datetime.combine(base_date, time(int(s.hour_to), int(round((s.hour_to % 1) * 60))))
                if s_start <= check_out_dt <= s_end:
                    shift_out = s
                    break
            if not shift_out:
                shift_out = shifts_today[-1]

            # ---------- CALCULATE DIFFERENCE CHECK-IN ----------
            shift_start_in = datetime.combine(base_date,
                                              time(int(shift_in.hour_from), int(round((shift_in.hour_from % 1) * 60))))
            grace_end_in = shift_start_in + timedelta(minutes=15)

            if check_in_dt <= shift_start_in:
                diff_min = int((shift_start_in - check_in_dt).total_seconds() / 60)
                rec.attendance_status = 'early'
            elif shift_start_in < check_in_dt <= grace_end_in:
                diff_min = 0
                rec.attendance_status = 'grace'
            else:
                diff_min = -int((check_in_dt - grace_end_in).total_seconds() / 60)
                rec.attendance_status = 'late'

            # ✅ Convert minutes to HH:MM
            sign = '-' if diff_min < 0 else ''
            abs_min = abs(diff_min)
            h, m = divmod(abs_min, 60)
            rec.difference_check_in = f"{sign}{h}:{m:02d}"

            # ---------- CALCULATE DIFFERENCE CHECK-OUT ----------
            shift_end_out = datetime.combine(base_date,
                                             time(int(shift_out.hour_to), int(round((shift_out.hour_to % 1) * 60))))
            diff_out_min = int((check_out_dt - shift_end_out).total_seconds() / 60)
            sign_out = '-' if diff_out_min < 0 else ''
            abs_min_out = abs(diff_out_min)
            h_out, m_out = divmod(abs_min_out, 60)
            rec.difference_check_out = f"{sign_out}{h_out}:{m_out:02d}"

            # ---------- TOTAL WORKING HOURS ----------
            total_secs = (check_out_dt - check_in_dt).total_seconds()
            if total_secs < 0:
                total_secs += 24 * 3600
            h = int(total_secs // 3600)
            m = int((total_secs % 3600) // 60)
            rec.total_working_hours = f"{h}:{m:02d}"


    @api.depends('check_in_attendance')
    def _compute_late_deduction(self):
        for rec in self:
            rec.late_deduction = 0.0
            if rec.check_in_attendance:
                try:
                    # Convert check_in_attendance (HH:MM) to datetime.time
                    check_in_time = datetime.strptime(rec.check_in_attendance, "%H:%M").time()

                    masters = self.env['hr.late.deduction.master'].search([])
                    for master in masters:
                        start_time = datetime.strptime(master.start_time, "%H:%M").time()
                        end_time = datetime.strptime(master.end_time, "%H:%M").time()

                        if start_time <= check_in_time <= end_time:
                            rec.late_deduction = master.deduction_amount
                            break
                except Exception:
                    rec.late_deduction = 0.0
            else:
                rec.late_deduction = 0.0

    DEFAULT_SERVER_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S "

    @api.depends('date', 'check_in_attendance')
    def _compute_your_datetime(self):
        for record in self:
            if record.date:
                try:
                    check_in_time = record.check_in_attendance or "00:00"

                    # Normalize both formats HH:MM and HH:MM:SS
                    parts = check_in_time.split(':')
                    if len(parts) == 2:  # Only hours and minutes
                        check_in_time = f"{check_in_time}:00"
                    elif len(parts) == 1:  # Just hour (edge case)
                        check_in_time = f"{check_in_time}:00:00"

                    datetime_str = f"{record.date} {check_in_time}"
                    naive_datetime = datetime.strptime(datetime_str, DEFAULT_SERVER_DATETIME_FORMAT)

                    # Convert to UTC based on user's timezone
                    user_tz = self.env.user.tz or 'UTC'
                    local_tz = pytz.timezone(user_tz)
                    local_dt = local_tz.localize(naive_datetime, is_dst=None)
                    utc_dt = local_dt.astimezone(pytz.UTC)

                    record.your_datetime = fields.Datetime.to_string(utc_dt)
                except Exception:
                    record.your_datetime = False
            else:
                record.your_datetime = False

    @api.depends('date', 'check_out_attendance')
    def _compute_your_checkout_datetime(self):
        for record in self:
            if record.date:
                try:
                    checkout_time = record.check_out_attendance or "00:00"

                    # Normalize time to HH:MM:SS
                    parts = checkout_time.split(':')
                    if len(parts) == 2:
                        checkout_time = f"{checkout_time}:00"
                    elif len(parts) == 1:
                        checkout_time = f"{checkout_time}:00:00"

                    datetime_str = f"{record.date} {checkout_time}"
                    naive_datetime = datetime.strptime(datetime_str, DEFAULT_SERVER_DATETIME_FORMAT)

                    # Convert to UTC based on user's timezone
                    user_tz = self.env.user.tz or 'UTC'
                    local_tz = pytz.timezone(user_tz)
                    local_dt = local_tz.localize(naive_datetime, is_dst=None)
                    utc_dt = local_dt.astimezone(pytz.UTC)

                    record.your_checkout_datetime = fields.Datetime.to_string(utc_dt)
                except Exception:
                    record.your_checkout_datetime = False
            else:
                record.your_checkout_datetime = False


    def open_upload_wizard(self):
        return {
            'name': 'Upload HR Data',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.upload.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

class HrUploadWizard(models.TransientModel):
    _name = "hr.upload.wizard"
    _description = "HR Upload Wizard"

    file = fields.Binary(string="File", required=True)
    filename = fields.Char(string="File Name")



    def action_upload(self):
        """Uploads attendance Excel file and creates hr.upload, hr.attendance, and hr.leave records
        with EL/LOP rules and hybrid working schedule–based attendance logic."""
        if not self.file:
            raise UserError(_("Please upload a file."))

        try:
            import base64
            import openpyxl
            from io import BytesIO
            from datetime import datetime, date, time, timedelta
            import pytz

            wb = openpyxl.load_workbook(
                filename=BytesIO(base64.b64decode(self.file)),
                read_only=True
            )
            ws = wb.active

            HrUpload = self.env['hr.upload']
            Employee = self.env['hr.employee']
            Attendance = self.env['hr.attendance']
            Leave = self.env['hr.leave']
            Allocation = self.env['hr.leave.allocation']
            LeaveType = self.env['hr.leave.type']

            # === Leave Type Lookup by Work Entry Code ===
            el_type = LeaveType.search([('work_entry_type_id.code', '=', 'LEAVE120')], limit=1)
            lop_type = LeaveType.search([('work_entry_type_id.code', '=', 'LEAVE90')], limit=1)
            if not el_type or not lop_type:
                raise UserError(
                    _("Please configure Time Off types with work entry codes LEAVE120 (EL) and LEAVE90 (LOP)."))

            # === Set timezone ===
            user_tz = self.env.user.tz or 'Asia/Kolkata'
            tz = pytz.timezone(user_tz)

            def normalize_time(time_value):
                """Convert Excel time or float value to HH:MM format, ignoring seconds."""
                if not time_value:
                    return None
                try:
                    if isinstance(time_value, (datetime, time)):
                        return time_value.strftime("%H:%M")
                    if isinstance(time_value, (int, float)):
                        from openpyxl.utils.datetime import from_excel
                        dt = from_excel(time_value)
                        return dt.strftime("%H:%M")
                    time_str = str(time_value).strip().replace(';', ':').replace('.', ':')
                    parts = time_str.split(':')
                    if len(parts) >= 2:
                        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
                    return None
                except Exception:
                    return None


            # === Process each row ===
            row_number = 1
            for row in ws.iter_rows(min_row=2, values_only=True):
                row_number += 1

                employee_code = row[0]
                employee_name = row[1]
                date_value = row[2]
                check_in = row[3]
                check_out = row[4]

                if not employee_code:
                    raise UserError(_("Row %d: Employee code is missing.") % row_number)
                if not employee_name:
                    raise UserError(_("Row %d: Employee name is missing.") % row_number)

                employee_name = str(employee_name).strip()
                try:
                    employee_code_str = str(int(employee_code))
                except Exception:
                    employee_code_str = str(employee_code).strip()

                employee = Employee.search([
                    ('cmr_code', '=', employee_code_str),
                    ('name', '=', employee_name)
                ], limit=1)
                if not employee:
                    raise UserError(_("Row %d: No employee found with code '%s' and name '%s'.") %
                                    (row_number, employee_code_str, employee_name))

                # === Date Parsing ===
                from openpyxl.utils.datetime import from_excel

                formatted_date = False
                if isinstance(date_value, datetime):
                    formatted_date = date_value.date()
                elif isinstance(date_value, (int, float)):
                    try:
                        formatted_date = from_excel(date_value).date()
                    except Exception:
                        pass
                elif isinstance(date_value, str):
                    date_value = date_value.strip()
                    for fmt in [
                        "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y",
                        "%d/%b/%Y", "%b-%d-%Y", "%d.%m.%Y", "%m/%d/%Y", "%d/%m/%y"
                    ]:
                        try:
                            formatted_date = datetime.strptime(date_value, fmt).date()
                            break
                        except Exception:
                            continue

                if not formatted_date:
                    raise UserError(_("Row %d: Invalid date format '%s'.") % (row_number, date_value))

                check_in = normalize_time(check_in)
                check_out = normalize_time(check_out)

                # === Create hr.upload Record ===
                upload_rec = HrUpload.create({
                    'employee_name': employee.id,
                    'ctc_type': employee.ctc_type,
                    'employee_code': employee_code_str,
                    'date': formatted_date,
                    'check_in_attendance': check_in,
                    'check_out_attendance': check_out,
                })

                if hasattr(upload_rec, '_compute_sessions'):
                    upload_rec._compute_sessions()

                morning = getattr(upload_rec, 'morning_session', '') or ''
                afternoon = getattr(upload_rec, 'afternoon_session', '') or ''
                leave_duration = 0.0
                half_day = False

                if morning == 'Absent' and afternoon == 'Absent':
                    leave_duration = 1.0
                elif morning == 'Absent' or afternoon == 'Absent':
                    leave_duration = 0.5
                    half_day = True

                # === Leave Logic ===
                if leave_duration > 0:
                    existing_leave = Leave.search([
                        ('employee_id', '=', employee.id),
                        ('request_date_from', '=', formatted_date),
                        ('request_date_to', '=', formatted_date),
                        ('state', '!=', 'refuse')
                    ], limit=1)
                    if existing_leave:
                        continue

                    if employee.ctc_type != 'non_ctc':
                        leave_type_to_use = lop_type
                        remaining_el = 0.0
                    else:
                        el_allocations = Allocation.search([
                            ('employee_id', '=', employee.id),
                            ('holiday_status_id', '=', el_type.id),
                            ('state', '=', 'validate')
                        ], limit=1)

                        remaining_el = 0.0
                        if el_allocations:
                            alloc = el_allocations[0]
                            start_date = alloc.date_from
                            accrual_per_month = 0.0

                            if alloc.accrual_plan_id:
                                accrual_level = self.env['hr.leave.accrual.level'].search([
                                    ('accrual_plan_id', '=', alloc.accrual_plan_id.id)
                                ], limit=1)
                                if accrual_level:
                                    accrual_per_month = accrual_level.added_value

                            if not accrual_per_month:
                                raise UserError(_(
                                    "Row %d: No accrual value defined in Accrual Plan for %s."
                                ) % (row_number, employee.name))

                            if start_date and formatted_date >= start_date:
                                months_passed = (formatted_date.year - start_date.year) * 12 + (
                                        formatted_date.month - start_date.month) + 1
                                total_allocated = months_passed * accrual_per_month
                            else:
                                total_allocated = 0.0

                            el_taken = sum(Leave.search([
                                ('employee_id', '=', employee.id),
                                ('holiday_status_id', '=', el_type.id),
                                ('state', 'in', ['validate', 'confirm']),
                                ('request_date_from', '<=', formatted_date)
                            ]).mapped('number_of_days'))

                            remaining_el = max(total_allocated - el_taken, 0.0)
                        else:
                            raise UserError(_(
                                "Row %d: No validated EL allocation found for %s."
                            ) % (row_number, employee.name))

                    def create_and_validate_leave(leave_type, days, half_day=False, period=False):
                        vals = {
                            'name': f"Auto Leave {formatted_date}",
                            'employee_id': employee.id,
                            'holiday_status_id': leave_type.id,
                            'request_date_from': formatted_date,
                            'request_date_to': formatted_date,
                            'number_of_days': days,
                        }
                        if half_day:
                            vals.update({
                                'request_unit_half': True,
                                'request_date_from_period': period,
                            })
                        leave_rec = Leave.create(vals)
                        if leave_rec.state == 'draft':
                            try:
                                leave_rec.action_confirm()
                            except Exception:
                                pass
                        if leave_rec.state in ['confirm', 'validate1', 'validate']:
                            try:
                                leave_rec.action_validate()
                            except Exception:
                                pass

                    if employee.ctc_type == 'non_ctc':
                        if remaining_el >= leave_duration:
                            create_and_validate_leave(
                                el_type, leave_duration, half_day,
                                'am' if half_day and morning == 'Absent' else 'pm' if half_day else False
                            )
                        elif remaining_el > 0:
                            create_and_validate_leave(el_type, remaining_el)
                            create_and_validate_leave(lop_type, leave_duration - remaining_el)
                        else:
                            create_and_validate_leave(
                                lop_type, leave_duration, half_day,
                                'am' if half_day and morning == 'Absent' else 'pm' if half_day else False
                            )
                    else:
                        create_and_validate_leave(
                            lop_type, leave_duration, half_day,
                            'am' if half_day and morning == 'Absent' else 'pm' if half_day else False
                        )

                # === Attendance creation (Hybrid logic) ===
                calendar = employee.resource_calendar_id
                if not calendar:
                    continue

                day_of_week = formatted_date.strftime("%A")
                working_hours = calendar.attendance_ids.filtered(
                    lambda a: a.display_name and day_of_week.lower() in a.display_name.lower()
                )
                if not working_hours:
                    continue

                morning_sched = working_hours.filtered(lambda a: 'morning' in a.display_name.lower())
                afternoon_sched = working_hours.filtered(lambda a: 'afternoon' in a.display_name.lower())

                def to_utc_datetime(date_part, hour_float):
                    hours = int(hour_float)
                    minutes = int(round((hour_float - hours) * 60))
                    local_dt = datetime.combine(date_part, time(hours, minutes))
                    local_dt = tz.localize(local_dt)
                    return local_dt.astimezone(pytz.UTC)

                def to_datetime_local(date_part, time_str):
                    try:
                        t = datetime.strptime(time_str, "%H:%M").time()
                        local_dt = datetime.combine(date_part, t)
                        local_dt = tz.localize(local_dt)
                        return local_dt.astimezone(pytz.UTC)
                    except Exception:
                        return None

                check_in_dt = check_out_dt = None

                # Morning present: actual in, schedule out
                if morning != 'Absent' and morning_sched:
                    sched_out = to_utc_datetime(formatted_date, max(morning_sched.mapped('hour_to')))
                    actual_in = to_datetime_local(formatted_date, check_in) if check_in else None
                    check_in_dt = actual_in or to_utc_datetime(formatted_date, min(morning_sched.mapped('hour_from')))
                    check_out_dt = sched_out

                # Afternoon present: schedule in, actual out
                if afternoon != 'Absent' and afternoon_sched:
                    sched_in = to_utc_datetime(formatted_date, min(afternoon_sched.mapped('hour_from')))
                    actual_out = to_datetime_local(formatted_date, check_out) if check_out else None

                    if check_in_dt and check_out_dt:
                        # merge morning+afternoon
                        check_out_dt = actual_out or to_utc_datetime(formatted_date,
                                                                     max(afternoon_sched.mapped('hour_to')))
                    else:
                        check_in_dt = sched_in
                        check_out_dt = actual_out or to_utc_datetime(formatted_date,
                                                                     max(afternoon_sched.mapped('hour_to')))

                if check_in_dt and check_out_dt and check_out_dt > check_in_dt:
                    open_attendance = Attendance.search([
                        ('employee_id', '=', employee.id),
                        ('check_out', '=', False)
                    ], limit=1)

                    if open_attendance:
                        open_attendance.write({'check_out': fields.Datetime.to_string(check_out_dt)})
                    else:
                        Attendance.create({
                            'employee_id': employee.id,
                            'date': formatted_date,
                            'check_in': fields.Datetime.to_string(check_in_dt),
                            'check_out': fields.Datetime.to_string(check_out_dt),
                            'difference_check_in': upload_rec.difference_check_in,
                            'difference_check_out': upload_rec.difference_check_out,
                            'total_working_hours': upload_rec.total_working_hours,
                            'morning_session': upload_rec.morning_session,
                            'afternoon_session': upload_rec.afternoon_session,
                            'full_day_status': upload_rec.full_day_status,
                        })

        except Exception as e:
            raise UserError(_('Upload failed: %s') % e)

class HrLateDeductionMaster(models.Model):
    _name = "hr.late.deduction.master"
    _description = "Late Deduction Master"
    _order = "start_time asc"

    name = fields.Char(string="Name", required=True)
    start_time = fields.Char(string="Start Time (HH:MM)", required=True)  # Example: 10:10
    end_time = fields.Char(string="End Time (HH:MM)", required=True)  # Example: 10:30
    deduction_amount = fields.Float(string="Deduction Amount", required=True)

class HrMonthlyLateDeduction(models.Model):
    _name = "hr.monthly.late.deduction"
    _description = "Monthly Late Deduction"

    employee_id = fields.Many2one('hr.employee', string="Employee")
    month = fields.Selection(
        [(str(i), calendar.month_name[i]) for i in range(1, 13)],
        string="Month",
        required=True,
        default=lambda self: str(datetime.now().month)
    )

    year = fields.Integer(string="Year", required=True, default=lambda self: datetime.now().year)


    line_ids = fields.One2many(
        'hr.late.deduction.line',
        'monthly_id',
        string="Late Deduction Lines"
    )


    def action_generate_all_employees(self):
        """Generate or refresh monthly employee late deduction lines from hr.upload dynamically."""
        self.ensure_one()

        # Convert month & year safely
        month = int(self.month)
        year = int(str(self.year).replace(',', ''))

        # Compute date range
        start_date = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day)

        # Get all upload records for this month
        uploads = self.env['hr.upload'].search([
            ('date', '>=', start_date.date()),
            ('date', '<=', end_date.date()),
        ])

        if not uploads:
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': 'No upload data found for this period!',
                    'type': 'rainbow_man',
                }
            }

        # Get unique employees from uploads
        employee_ids = uploads.mapped('employee_name.id')

        line_vals = []
        for emp_id in employee_ids:
            emp_uploads = uploads.filtered(lambda u: u.employee_name.id == emp_id)

            # Safely handle any string values in late_deduction
            late_days = len(emp_uploads.filtered(lambda u: float(u.late_deduction or 0) > 0))
            late_hours = sum(
                [float(u.late_hours or 0) for u in emp_uploads]) if 'late_hours' in emp_uploads._fields else 0.0
            deduction_amount = sum(
                [float(u.late_deduction or 0) for u in emp_uploads]) if 'late_deduction' in emp_uploads._fields else 0.0

            line_vals.append((0, 0, {
                'employee_id': emp_id,
                'late_days': late_days,
                'late_hours': late_hours,
                'deduction_amount': deduction_amount,
            }))

        # Replace existing lines with fresh ones
        self.line_ids = [(5, 0, 0)] + line_vals

        return {
            'effect': {
                'fadeout': 'slow',
                'message': f'{len(employee_ids)} Employee Records Recalculated Successfully!',
                'type': 'rainbow_man',
            }
        }

class HrLateDeductionLine(models.Model):
    _name = "hr.late.deduction.line"
    _description = "Late Deduction Line"

    monthly_id = fields.Many2one('hr.monthly.late.deduction', string="Monthly Record")
    employee_id = fields.Many2one('hr.employee', string="Employee")
    late_days = fields.Integer(string="Late Days")
    late_hours = fields.Float(string="Late Hours")
    deduction_amount = fields.Float(string="Deduction Amount (₹)", compute="_compute_total_late_deduction",store=True)

    month = fields.Selection(
        related='monthly_id.month',
        string="Month",
        store=True,
        readonly=True
    )
    year = fields.Integer(
        related='monthly_id.year',
        string="Year",
        store=True,
        readonly=True
    )


    @api.depends('employee_id', 'monthly_id.month', 'monthly_id.year')
    def _compute_total_late_deduction(self):
        """Compute total monthly deduction for each employee based on hr.upload."""
        for rec in self:
            rec.deduction_amount = 0.0  # default
            if not rec.employee_id or not rec.monthly_id:
                continue

            # Safely get month & year
            try:
                month = int(rec.month)
                year = int(str(rec.year).replace(',', ''))
            except Exception:
                continue

            start_date = datetime(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end_date = datetime(year, month, last_day)

            # ✅ Search all hr.upload entries for that employee in the month
            uploads = self.env['hr.upload'].search([
                ('employee_name', '=', rec.employee_id.name),
                ('date', '>=', start_date.date()),
                ('date', '<=', end_date.date()),
            ])

            # ✅ Compute total late deduction
            rec.deduction_amount = sum(float(u.late_deduction or 0) for u in uploads)

            # Optional: if you want to count number of days with deductions

class HrOvertimeMaster(models.Model):
    _name = "hr.overtime.master"
    _description = "Overtime Master"
    _order = "start_time asc"

    name = fields.Char(string="Name", required=True)
    start_time = fields.Char(string="Start Time (HH:MM)", required=True)  # e.g. 18:00
    end_time = fields.Char(string="End Time (HH:MM)", required=True)      # e.g. 20:00
    overtime_amount = fields.Float(string="Overtime Amount (₹)")

class HrMonthlyOvertime(models.Model):
    _name = "hr.monthly.overtime"
    _description = "Monthly Overtime"

    employee_id = fields.Many2one('hr.employee', string="Employee")
    month = fields.Selection(
        [(str(i), calendar.month_name[i]) for i in range(1, 13)],
        string="Month",
        required=True,
        default=lambda self: str(datetime.now().month)
    )
    year = fields.Integer(string="Year", required=True, default=lambda self: datetime.now().year)

    line_ids = fields.One2many('hr.overtime.line', 'monthly_id', string="Overtime Lines")

    def action_generate_all_employees(self):
        """Generate or refresh monthly employee overtime summary dynamically from hr.upload."""
        self.ensure_one()

        # ✅ Convert month & year properly
        month = int(self.month)
        year = int(str(self.year).replace(',', ''))

        # ✅ Compute date range
        start_date = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_date = datetime(year, month, last_day)

        # ✅ Fetch hr.upload records for this month
        uploads = self.env['hr.upload'].search([
            ('date', '>=', start_date.date()),
            ('date', '<=', end_date.date()),
        ])

        if not uploads:
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': 'No uploaded employees found for this period!',
                    'type': 'rainbow_man',
                }
            }

        employee_ids = uploads.mapped('employee_name.id')
        line_vals = []

        for emp_id in employee_ids:
            emp_uploads = uploads.filtered(lambda u: u.employee_name.id == emp_id)

            # ✅ Safely calculate total overtime (handles str/None types)

            overtime_amount = sum(float(u.overtime_amount or 0) for u in emp_uploads if hasattr(u, 'overtime_amount'))

            line_vals.append((0, 0, {
                'employee_id': emp_id,

                'overtime_amount': overtime_amount,
            }))

        # ✅ Clear existing lines and add new ones
        self.line_ids = [(5, 0, 0)] + line_vals

        return {
            'effect': {
                'fadeout': 'slow',
                'message': f'{len(employee_ids)} Employee Overtime Records Calculated!',
                'type': 'rainbow_man',
            }
        }

class HrOvertimeLine(models.Model):
    _name = "hr.overtime.line"
    _description = "Overtime Line"

    monthly_id = fields.Many2one('hr.monthly.overtime', string="Monthly Record")
    employee_id = fields.Many2one('hr.employee', string="Employee")

    overtime_amount = fields.Float(string="Overtime Amount (₹)", compute="_compute_total_overtime", store=True)

    month = fields.Selection(related='monthly_id.month', store=True, readonly=True)
    year = fields.Integer(related='monthly_id.year', store=True, readonly=True)

    @api.depends('employee_id', 'monthly_id.month', 'monthly_id.year')
    def _compute_total_overtime(self):
        """Compute total monthly overtime for each employee based on hr.upload."""
        for rec in self:
            rec.overtime_amount = 0.0
            if not rec.employee_id or not rec.monthly_id:
                continue

            try:
                # ✅ Always take month/year from monthly_id (not from rec)
                month = int(rec.monthly_id.month)
                year = int(str(rec.monthly_id.year).replace(',', ''))
            except Exception:
                continue

            # ✅ Compute date range safely
            start_date = datetime(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            end_date = datetime(year, month, last_day)

            # ✅ Search all hr.upload entries for that employee
            uploads = self.env['hr.upload'].search([
                ('employee_name', '=', rec.employee_id.name),
                ('date', '>=', start_date.date()),
                ('date', '<=', end_date.date()),
            ])

            # ✅ Safely sum overtime amount (handles str/None)
            rec.overtime_amount = sum(float(u.overtime_amount or 0) for u in uploads)

