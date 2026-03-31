from datetime import datetime, timedelta
import base64
import io
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import xlsxwriter
from odoo.tools import format_date
from odoo import models, fields,api
from odoo.tools.safe_eval import pytz, time


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
        """Fetch data from store.wise.data and populate lines."""
        self.line_ids = [(5, 0, 0)]  # Clear old lines
        result_dict = {}  # {(date_or_month, division_name): {...}}
        division_names = self.env['product.category'].search([('parent_id', '=', False)]).mapped('name')


        if self.day_month_selection == 'day':
            current_date = self.from_date
            while current_date <= self.to_date:
                # Step 1: Store wise data
                store_data = self.env['store.wise.data'].search([
                    ('store_id', '=', self.store_id.id),
                    ('from_date', '<=', current_date),
                    ('to_date', '>=', current_date)
                ])
                division_targets = {}
                for rec in store_data:
                    for line in rec.division_line_ids:
                        division_targets[line.division_name] = {
                            'regular': line.regular_per_day,
                            'festival': line.festival_per_day,
                        }

                start_date_utc, end_date_utc = self.get_day_bounds(current_date)

                start_date = fields.Datetime.to_datetime(current_date)
                end_date = start_date + timedelta(days=1)
                # Step 2: Stock move lines for the day
                move_lines = self.env['stock.move.line'].search([
                    ('picking_id.location_id.company_id.id', '=', self.store_id.id),
                    ('picking_id.stock_picking_type', '=', 'pos_order'),('state','=','done'),
                    ('create_date', '>=', start_date),
                    ('create_date', '<', end_date)
                ])

                # Step 3: Per division
                for division_name in division_names:
                    lots_in_division = move_lines.filtered(
                        lambda ml: ml.lot_id.product_id.family_categ_id.name == division_name
                    ).mapped('lot_id')
                    total_rsp_value = sum(lot.rs_price for lot in lots_in_division if lot.rs_price)
                    regular_target = division_targets.get(division_name, {}).get('regular', 0.0)
                    festival_target = division_targets.get(division_name, {}).get('festival', 0.0)

                    key = (current_date.strftime('%d/%m/%Y'), division_name)
                    if key in result_dict:
                        result_dict[key]['target_price'] += total_rsp_value
                    else:
                        result_dict[key] = {
                            'division_name': f"{current_date.strftime('%d/%m/%Y')} - {division_name}",
                            'target_price': total_rsp_value,
                            'regular': regular_target,
                            'festival': festival_target,
                        }

                current_date += timedelta(days=1)


        elif self.day_month_selection == 'month':
            current_date = self.from_date
            while current_date <= self.to_date:
                # Take month_start as current_date (not forced to 1st of month)
                month_start = current_date
                # Calculate natural month end from current_date
                if month_start.month == 12:
                    month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
                else:
                    month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)

                # Restrict to self.to_date (so it does not overshoot)
                if month_end > self.to_date:
                    month_end = self.to_date

                # Step 1: Find store.wise.data covering this custom month range
                store_data = self.env['store.wise.data'].search([
                    ('store_id', '=', self.store_id.id),
                    ('from_date', '<=', month_end),
                    ('to_date', '>=', month_start)

                ])

                division_targets = {}
                if store_data:
                    for line in store_data.division_line_ids:
                        division_targets[line.division_name] = {
                            'regular': line.regular_excess_month,
                           'festival': line.festival_excess_month,
                        }

                # Convert to UTC datetime range
                # month_start_dt = fields.Datetime.to_datetime(month_start)
                # month_end_dt = fields.Datetime.to_datetime(month_end) + timedelta(days=1)
                # print(month_start_dt)
                # print(month_end_dt)

                month_start_dt, _ = self.get_day_bounds(month_start, self.env.user.tz or 'UTC')
                _, month_end_dt = self.get_day_bounds(month_end, self.env.user.tz or 'UTC')
                print(month_start_dt)
                print(month_end_dt)
                # Step 2: Stock move lines in this range
                move_lines = self.env['stock.move.line'].search([
                    ('picking_id.location_id.company_id.id', '=', self.store_id.id),
                    ('picking_id.stock_picking_type', '=', 'pos_order'),
                    ('state', '=', 'done'),
                    ('create_date', '>=', month_start_dt),
                    ('create_date', '<=', month_end_dt),
                ])

                # Step 3: Per division
                for division_name in division_names:
                    lots_in_division = move_lines.filtered(
                        lambda ml: ml.lot_id.product_id.family_categ_id.name == division_name
                    ).mapped('lot_id')

                    total_rsp_value = sum(lot.rs_price for lot in lots_in_division if lot.rs_price)
                    print("total_rsp_value",total_rsp_value)
                    regular_target = division_targets.get(division_name, {}).get('regular', 0.0)
                    festival_target = division_targets.get(division_name, {}).get('festival', 0.0)

                    # ✅ Key will show month name instead of raw date range

                    key = (f"{month_start.strftime('%B %Y')}", division_name)
                    if key in result_dict:
                        result_dict[key]['target_price'] += total_rsp_value
                    else:
                        result_dict[key] = {
                            'division_name': f"{month_start.strftime('%B %Y')} - {division_name}",
                            'target_price': total_rsp_value,
                            'regular_excess_month': regular_target,
                            'festival_excess_month': festival_target,

                        }

                # Jump to the **first day of next month**
                if month_start.month == 12:
                    current_date = month_start.replace(year=month_start.year + 1, month=1, day=1)
                else:
                    current_date = month_start.replace(month=month_start.month + 1, day=1)

        # Final write
        self.line_ids = [(0, 0, vals) for vals in result_dict.values()]


    def action_to_reset(self):
        self.store_id = False
        self.from_date = False
        self.to_date = False
        self.line_ids.unlink()

    def action_print_pdf(self):
        """Return the PDF report action."""
        return self.env.ref('cmr_customizations.action_report_store_target').report_action(self)

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
            headers += ['Regular Excess Month', 'Festival Excess Month']
        else:  # self.day_month_selection == 'day'
            headers += ['Regular', 'Festival']
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
            else:
                worksheet.write(row, col, line.regular_excess_month or 0.0)
                col += 1
                worksheet.write(row, col, line.festival_excess_month or 0.0)
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

    @api.depends('report_id.line_ids')
    def _compute_s_no(self):
        for rec in self.report_id:
            for index, line in enumerate(rec.line_ids, start=1):
                line.s_no = index






