from datetime import datetime, timedelta
import base64
import io
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import xlsxwriter
from odoo.tools import format_date
from odoo import models, fields,api
from odoo.tools.safe_eval import pytz, time
from odoo.exceptions import ValidationError
from datetime import date


class StoreTargetReport(models.TransientModel):  # Persistent model
    _name = "store.target.report"
    _description = "Store Target Report"


    name = fields.Char(string="Reference", readonly=True, default='New')
    store_id = fields.Many2one(
        'res.company',
        string="Store",
        domain=[('nhcl_company_bool', '!=', True)]
    )
    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    line_ids = fields.One2many(
        'store.target.report.line',
        'report_id',
        string="Report Lines"
    )
    day_month_selection = fields.Selection([
        ('day', 'Day'),
        ('month', 'Month')
    ], string="Day/Month", required=True, default='day')

    @api.constrains('from_date', 'to_date')
    def _check_date_validation(self):
        for rec in self:
            # Both dates required
            # if rec.from_date and not rec.to_date:
            #     raise ValidationError("Please select To Date.")
            #
            # if rec.to_date and not rec.from_date:
            #     raise ValidationError("Please select From Date.")

            # From Date should not be greater than To Date
            if rec.from_date and rec.to_date:
                if rec.from_date > rec.to_date:
                    raise ValidationError("From Date cannot be greater than To Date.")

            # Optional: Prevent future date
            if rec.to_date and rec.to_date > date.today():
                raise ValidationError("To Date cannot be a future date.")

    # @api.model
    # def create(self, vals):
    #     if vals.get('name', 'New') == 'New':
    #         vals['name'] = self.env['ir.sequence'].next_by_code('store.wise.data') or 'New'
    #     return super(StoreTargetReport, self).create(vals)
    @staticmethod
    def get_day_bounds(date_value, tz_name="UTC"):
        """Return the start and end datetime for a given date in a specific timezone."""
        # Ensure input is a date
        if isinstance(date_value, datetime):
            date_value = date_value.date()

        # Get timezone object
        tz = pytz.timezone(tz_name)

        # Start of the day
        start_date = tz.localize(datetime.combine(date_value, datetime.min.time()))
        # End of the day (23:59:59)
        end_date = tz.localize(datetime.combine(date_value, datetime.max.time()))

        # Convert to UTC for database queries
        start_date_utc = start_date.astimezone(pytz.UTC)
        end_date_utc = end_date.astimezone(pytz.UTC)

        return start_date_utc, end_date_utc

    def action_fetch_data(self):
        """Fetch data based on Store Wise Data and Invoices - Credit Notes."""

        self.line_ids = [(5, 0, 0)]  # Clear old lines
        result_dict = {}

        if not self.store_id:
            raise ValidationError("Please select the store.")
        if not self.from_date or  not self.to_date:
            raise ValidationError("Please Enter the date")

        # DAY MODE
        if self.day_month_selection == 'day':

            current_date = self.from_date

            while current_date <= self.to_date:

                # Get Store Wise Data for that date
                store_data = self.env['store.wise.data'].search([
                    ('store_id', '=', self.store_id.id),
                    ('from_date', '<=', current_date),
                    ('to_date', '>=', current_date),
                ])

                for rec in store_data:
                    for division_line in rec.division_line_ids:

                        division_name = division_line.division_name

                        invoice_lines = self.env['account.move.line'].search([
                            ('move_id.company_id', '=', self.store_id.id),
                            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                            ('move_id.state', '=', 'posted'),
                            ('move_id.invoice_date', '=', current_date),
                            ('product_id.categ_id.parent_id.parent_id.parent_id.name', '=', division_name),
                        ])

                        invoice_total = 0.0
                        refund_total = 0.0

                        for line in invoice_lines:
                            if line.move_id.move_type == 'out_invoice':
                                invoice_total += line.price_total
                            else:
                                refund_total += line.price_total

                        achievement = invoice_total - refund_total

                        key = (current_date.strftime('%d/%m/%Y'), division_name)

                        result_dict[key] = {
                            'division_name': f"{current_date.strftime('%d/%m/%Y')} - {division_name}",
                            'target_price': achievement,
                            'regular': division_line.regular_per_day,
                            'festival': division_line.festival_per_day,
                            'Per_day_target': division_line.day_target,
                            'per_month_target': 0.0,
                        }

                current_date += timedelta(days=1)

        # MONTH MODE
        elif self.day_month_selection == 'month':

            current_date = self.from_date

            while current_date <= self.to_date:

                month_start = current_date

                if month_start.month == 12:
                    month_end = month_start.replace(
                        year=month_start.year + 1, month=1, day=1
                    ) - timedelta(days=1)
                else:
                    month_end = month_start.replace(
                        month=month_start.month + 1, day=1
                    ) - timedelta(days=1)

                if month_end > self.to_date:
                    month_end = self.to_date

                store_data = self.env['store.wise.data'].search([
                    ('store_id', '=', self.store_id.id),
                    ('from_date', '<=', month_end),
                    ('to_date', '>=', month_start),
                ])

                for rec in store_data:
                    for division_line in rec.division_line_ids:

                        division_name = division_line.division_name

                        invoice_lines = self.env['account.move.line'].search([
                            ('move_id.company_id', '=', self.store_id.id),
                            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                            ('move_id.state', '=', 'posted'),
                            ('move_id.invoice_date', '>=', month_start),
                            ('move_id.invoice_date', '<=', month_end),
                            ('product_id.categ_id.parent_id.parent_id.parent_id.name', '=', division_name),
                        ])

                        invoice_total = 0.0
                        refund_total = 0.0

                        for line in invoice_lines:
                            if line.move_id.move_type == 'out_invoice':
                                invoice_total += line.price_total
                            else:
                                refund_total += line.price_total

                        achievement = invoice_total - refund_total

                        key = (month_start.strftime('%B %Y'), division_name)

                        result_dict[key] = {
                            'division_name': f"{month_start.strftime('%B %Y')} - {division_name}",
                            'target_price': achievement,
                            'regular_excess_month': division_line.regular_excess_month,
                            'festival_excess_month': division_line.festival_excess_month,
                            'Per_day_target': 0.0,
                            'per_month_target': division_line.month_target,
                        }

                if month_start.month == 12:
                    current_date = month_start.replace(
                        year=month_start.year + 1, month=1, day=1
                    )
                else:
                    current_date = month_start.replace(
                        month=month_start.month + 1, day=1
                    )

        # Final Write
        self.line_ids = [(0, 0, vals) for vals in result_dict.values()]


    def action_to_reset(self):
        self.store_id = False
        self.from_date = False
        self.to_date = False
        self.line_ids.unlink()

    def action_print_pdf(self):
        """Return the PDF report action."""
        return self.env.ref('nhcl_ho_store_cmr_integration.action_report_store_target').report_action(self)

    def get_excel_sheet(self):
        """Export Store Target Report Lines to Excel with conditional columns."""
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet("Store Target Report")

        # Formats
        bold = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
        date_format = workbook.add_format({'num_format': 'dd-mm-yyyy'})
        text_format = workbook.add_format({'align': 'left'})

        # Dynamic headers
        headers = ['S.No', 'Store Name','Division']
        if self.day_month_selection == 'month':
            headers += ['Regular Excess Month', 'Festival Excess Month', 'Month Target']
        else:  # self.day_month_selection == 'day'
            headers += ['Regular', 'Festival', 'Day Target']
        headers.append('Achievement')

        # Write headers
        for col, header in enumerate(headers):
            worksheet.write(0, col, header, bold)

        # Write data rows
        for row, line in enumerate(self.line_ids, start=1):
            col = 0
            worksheet.write(row, col, line.s_no)
            col += 1
            worksheet.write(row, col, line.report_id.store_id.name or '', text_format)
            col += 1
            worksheet.write(row, col, line.division_name or '')
            col += 1

            if self.day_month_selection == 'day':
                worksheet.write(row, col, line.regular or 0.0)
                col += 1
                worksheet.write(row, col, line.festival or 0.0)
                col += 1
                worksheet.write(row, col, line.Per_day_target or 0.0)
                col += 1
            else:
                worksheet.write(row, col, line.regular_excess_month or 0.0)
                col += 1
                worksheet.write(row, col, line.festival_excess_month or 0.0)
                col += 1
                worksheet.write(row, col, line.per_month_target or 0.0)
                col += 1

            worksheet.write(row, col, line.target_price or 0.0)

        # Close workbook
        workbook.close()
        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        # Encode and create attachment
        encoded_data = base64.b64encode(excel_data)
        attachment = self.env['ir.attachment'].create({
            'name': f'Store_Target_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Store_Target_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }



class StoreTargetReportLine(models.TransientModel):
    _name = "store.target.report.line"
    _description = "Store Target Report Line"

    s_no = fields.Integer(string="Row No", compute="_compute_s_no")
    report_id = fields.Many2one('store.target.report', string="Report", ondelete='cascade')
    division_name = fields.Char(string="Division")
    target_price = fields.Float(string="Achievement")
    regular = fields.Float(string="Regular")
    festival = fields.Float(string="Festival")
    regular_excess_month = fields.Float(string="Regular Excess Month")
    festival_excess_month = fields.Float(string="Festival Excess Month")
    Per_day_target = fields.Float(string="Day Target")
    per_month_target = fields.Float(string="Month Target")

    @api.depends('report_id.line_ids')
    def _compute_s_no(self):
        for rec in self.report_id:
            for index, line in enumerate(rec.line_ids, start=1):
                line.s_no = index






