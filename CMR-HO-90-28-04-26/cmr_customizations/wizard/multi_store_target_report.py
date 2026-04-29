from datetime import datetime, timedelta, date
import base64
import io
import xlsxwriter

from odoo import models, fields, api
from odoo.exceptions import ValidationError
from collections import defaultdict


class MultiStoreTargetReport(models.TransientModel):
    _name = "multi.store.target.report"
    _description = "Multi Store Target Report"

    store_ids = fields.Many2many(
        'res.company',
        string="Stores",
        domain=[('nhcl_company_bool', '!=', True)]
    )
    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    day_month_selection = fields.Selection([
        ('day', 'Day'),
        ('month', 'Month')
    ], required=True, default='day')

    line_ids = fields.One2many(
        'multi.store.target.report.line',
        'report_id',
        string="Report Lines"
    )
    # name = fields.Char(string='Name', default='Multi Store Target Report')

    @api.constrains('from_date', 'to_date')
    def _check_date_validation(self):
        for rec in self:
            if rec.from_date and rec.to_date and rec.from_date > rec.to_date:
                raise ValidationError("From Date cannot be greater than To Date.")
            if rec.to_date and rec.to_date > date.today():
                raise ValidationError("To Date cannot be future date.")

    def action_fetch_multi_store_data(self):

        self.line_ids = [(5, 0, 0)]
        result_dict = {}
        any_store_data_found = False

        if not self.store_ids:
            raise ValidationError("Please select at least one store.")
        if not self.from_date or not self.to_date:
            raise ValidationError("Please Enter the date")

        AML = self.env['account.move.line']

        for store in self.store_ids:

            # ================= DAY MODE =================
            if self.day_month_selection == 'day':

                current_date = self.from_date

                while current_date <= self.to_date:

                    store_data = self.env['store.wise.data'].search([
                        ('store_id', '=', store.id),
                        ('from_date', '<=', current_date),
                        ('to_date', '>=', current_date),
                    ])

                    if store_data:
                        any_store_data_found = True

                    divisions = {
                        dl.division_name: dl
                        for rec in store_data
                        for dl in rec.division_line_ids
                    }

                    # 🔥 AML search ONCE for the date
                    aml_lines = AML.search([
                        ('move_id.company_id', '=', store.id),
                        ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                        ('move_id.state', '=', 'posted'),
                        ('move_id.invoice_date', '=', current_date),
                    ])

                    grouped = defaultdict(lambda: {'invoice': 0.0, 'refund': 0.0})

                    for line in aml_lines:
                        div = line.product_id.categ_id.parent_id.parent_id.parent_id.name
                        if div in divisions:
                            if line.move_id.move_type == 'out_invoice':
                                print("iiiiiinvoice", line.price_total)
                                grouped[div]['invoice'] += line.price_total
                            elif line.move_id.move_type == 'out_refund':
                                print("iiiiiinvoicerrrr", line.price_total)
                                grouped[div]['refund'] += line.price_total

                    for div_name, div_line in divisions.items():
                        invoice_total = grouped[div_name]['invoice']
                        refund_total = grouped[div_name]['refund']

                        achievement = invoice_total - refund_total

                        key = (store.id, current_date.strftime('%d/%m/%Y'), div_name)

                        result_dict[key] = {
                            'store_id': store.id,
                            'division_name': f"{current_date.strftime('%d/%m/%Y')} - {div_name}",
                            'target_price': achievement,
                            'regular': div_line.regular_per_day,
                            'festival': div_line.festival_per_day,
                            'Per_day_target': div_line.day_target,
                            'per_month_target': 0.0,
                        }

                    current_date += timedelta(days=1)

            # ================= MONTH MODE =================
            else:

                current_date = self.from_date

                while current_date <= self.to_date:

                    month_start = current_date.replace(day=1)
                    if month_start.month == 12:
                        month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
                    else:
                        month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)

                    if month_end > self.to_date:
                        month_end = self.to_date

                    store_data = self.env['store.wise.data'].search([
                        ('store_id', '=', store.id),
                        ('from_date', '<=', month_end),
                        ('to_date', '>=', month_start),
                    ])

                    if store_data:
                        any_store_data_found = True

                    divisions = {
                        dl.division_name: dl
                        for rec in store_data
                        for dl in rec.division_line_ids
                    }

                    # 🔥 AML search ONCE for the month
                    aml_lines = AML.search([
                        ('move_id.company_id', '=', store.id),
                        ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                        ('move_id.state', '=', 'posted'),
                        ('move_id.invoice_date', '>=', month_start),
                        ('move_id.invoice_date', '<=', month_end),
                    ])

                    grouped = defaultdict(lambda: {'invoice': 0.0, 'refund': 0.0})

                    for line in aml_lines:
                        div = line.product_id.categ_id.parent_id.parent_id.parent_id.name
                        if div in divisions:
                            if line.move_id.move_type == 'out_invoice':
                                grouped[div]['invoice'] += line.price_total
                            else:
                                grouped[div]['refund'] += line.price_total

                    for div_name, div_line in divisions.items():
                        invoice_total = grouped[div_name]['invoice']
                        refund_total = grouped[div_name]['refund']
                        achievement = invoice_total - refund_total

                        key = (store.id, month_start.strftime('%B %Y'), div_name)

                        result_dict[key] = {
                            'store_id': store.id,
                            'division_name': f"{month_start.strftime('%B %Y')} - {div_name}",
                            'target_price': achievement,
                            'regular_excess_month': div_line.regular_excess_month,
                            'festival_excess_month': div_line.festival_excess_month,
                            'Per_day_target': 0.0,
                            'per_month_target': div_line.month_target,
                        }

                    current_date = month_end + timedelta(days=1)

        if not any_store_data_found:
            raise ValidationError("No Store Wise Target Data found for the selected period.")

        self.line_ids = [(0, 0, vals) for vals in result_dict.values()]

    def action_to_reset(self):
        self.store_ids = False
        self.from_date = False
        self.to_date = False
        self.line_ids.unlink()

    def get_multi_store_excel_sheet(self):
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet("Store Target Report")

        # Formats
        bold = workbook.add_format({'bold': True, 'bg_color': '#D3D3D3'})
        text_format = workbook.add_format({'align': 'left'})

        # Headers
        headers = ['S.No', 'Store Name', 'Division']
        if self.day_month_selection == 'month':
            headers += ['Regular Excess Month', 'Festival Excess Month', 'Month Target']
        else:
            headers += ['Regular', 'Festival', 'Day Target']
        headers.append('Achievement')

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, bold)

        # Sort lines by store then division for better readability
        lines = self.line_ids.sorted(lambda l: (l.store_id.name, l.division_name))

        row = 1
        for idx, line in enumerate(lines, start=1):
            col = 0

            worksheet.write(row, col, idx)
            col += 1

            # Use line.store_id (not wizard store)
            worksheet.write(row, col, line.store_id.name or '', text_format)
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

            row += 1

        workbook.close()
        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        attachment = self.env['ir.attachment'].create({
            'name': f'Multi_Store_Target_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(excel_data),
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_print_pdf(self):
        """Return the PDF report action."""
        return self.env.ref('cmr_customizations.action_report_multi_stores_target').report_action(self)

    # def action_fetch_data(self):
    #     self.line_ids = [(5, 0, 0)]
    #
    #     if not self.store_ids:
    #         raise ValidationError("Please select at least one store.")
    #     if not self.from_date or not self.to_date:
    #         raise ValidationError("Please enter date range.")
    #
    #     result_dict = {}
    #
    #     for store in self.store_ids:
    #
    #         if self.day_month_selection == 'day':
    #             current_date = self.from_date
    #
    #             while current_date <= self.to_date:
    #
    #                 store_data = self.env['store.wise.data'].search([
    #                     ('store_id', '=', store.id),
    #                     ('from_date', '<=', current_date),
    #                     ('to_date', '>=', current_date),
    #                 ])
    #
    #                 for rec in store_data:
    #                     for division_line in rec.division_line_ids:
    #
    #                         division_name = division_line.division_name
    #
    #                         invoice_lines = self.env['account.move.line'].search([
    #                             ('move_id.company_id', '=', store.id),
    #                             ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
    #                             ('move_id.state', '=', 'posted'),
    #                             ('move_id.invoice_date', '=', current_date),
    #                             ('product_id.categ_id.parent_id.parent_id.parent_id.name', '=', division_name),
    #                         ])
    #
    #                         invoice_total = sum(l.price_total for l in invoice_lines if l.move_id.move_type == 'out_invoice')
    #                         refund_total = sum(l.price_total for l in invoice_lines if l.move_id.move_type == 'out_refund')
    #
    #                         achievement = invoice_total - refund_total
    #
    #                         key = (store.id, current_date, division_name)
    #
    #                         result_dict[key] = {
    #                             'store_id': store.id,
    #                             'division_name': f"{current_date.strftime('%d/%m/%Y')} - {division_name}",
    #                             'target_price': achievement,
    #                             'regular': division_line.regular_per_day,
    #                             'festival': division_line.festival_per_day,
    #                             'Per_day_target': division_line.day_target,
    #                             'per_month_target': 0.0,
    #                         }
    #
    #                 current_date += timedelta(days=1)
    #
    #         else:
    #             current_date = self.from_date
    #
    #             while current_date <= self.to_date:
    #
    #                 month_start = current_date
    #                 if month_start.month == 12:
    #                     month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
    #                 else:
    #                     month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)
    #
    #                 if month_end > self.to_date:
    #                     month_end = self.to_date
    #
    #                 store_data = self.env['store.wise.data'].search([
    #                     ('store_id', '=', store.id),
    #                     ('from_date', '<=', month_end),
    #                     ('to_date', '>=', month_start),
    #                 ])
    #
    #                 for rec in store_data:
    #                     for division_line in rec.division_line_ids:
    #
    #                         division_name = division_line.division_name
    #
    #                         invoice_lines = self.env['account.move.line'].search([
    #                             ('move_id.company_id', '=', store.id),
    #                             ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
    #                             ('move_id.state', '=', 'posted'),
    #                             ('move_id.invoice_date', '>=', month_start),
    #                             ('move_id.invoice_date', '<=', month_end),
    #                             ('product_id.categ_id.parent_id.parent_id.parent_id.name', '=', division_name),
    #                         ])
    #
    #                         invoice_total = sum(l.price_total for l in invoice_lines if l.move_id.move_type == 'out_invoice')
    #                         refund_total = sum(l.price_total for l in invoice_lines if l.move_id.move_type == 'out_refund')
    #
    #                         achievement = invoice_total - refund_total
    #
    #                         key = (store.id, month_start, division_name)
    #
    #                         result_dict[key] = {
    #                             'store_id': store.id,
    #                             'division_name': f"{month_start.strftime('%B %Y')} - {division_name}",
    #                             'target_price': achievement,
    #                             'regular_excess_month': division_line.regular_excess_month,
    #                             'festival_excess_month': division_line.festival_excess_month,
    #                             'Per_day_target': 0.0,
    #                             'per_month_target': division_line.month_target,
    #                         }
    #
    #                 if month_start.month == 12:
    #                     current_date = month_start.replace(year=month_start.year + 1, month=1, day=1)
    #                 else:
    #                     current_date = month_start.replace(month=month_start.month + 1, day=1)
    #
    #     self.line_ids = [(0, 0, vals) for vals in result_dict.values()]


class MultiStoreTargetReportLine(models.TransientModel):
    _name = "multi.store.target.report.line"
    _description = "Multi Store Target Report Line"

    report_id = fields.Many2one('multi.store.target.report', ondelete='cascade')
    store_id = fields.Many2one('res.company', string="Store")

    s_no = fields.Integer(string="Row No", compute="_compute_s_no")
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
        for rec in self.mapped('report_id'):
            for index, line in enumerate(rec.line_ids, start=1):
                line.s_no = index