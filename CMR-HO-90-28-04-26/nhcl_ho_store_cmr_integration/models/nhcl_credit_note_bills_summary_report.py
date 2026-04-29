from odoo import models, fields, api, _

import base64
import io

import datetime
import xlsxwriter
from odoo.tools import format_date


class NHCLCreditNoteBillsReport(models.Model):
    _name = 'nhcl.credit.notes.bills.report'
    _description = "NHCL Credit Note Bills Report"
    _rec_name = 'nhcl_company_id'

    def _default_stores(self):
        return self.env['nhcl.ho.store.master'].search([
            ('nhcl_active', '=', True),
            ('nhcl_store_type', '!=', 'ho')
        ]).ids

    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    credit_note_bills_report_ids = fields.One2many('nhcl.credit.notes.bills.report.line', 'credit_note_bills_report_id')
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string="Company", default=_default_stores)
    total_order_quantity = fields.Float(compute="_compute_nhcl_show_totals", string='Total Quantities')
    # total_discount_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Discount')
    total_amount_total = fields.Float(compute="_compute_nhcl_show_totals", string='Net Total')
    total_tax_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Tax')
    total_in_amount_total = fields.Float(compute="_compute_nhcl_show_totals", string='Gross Total')

    @api.depends('nhcl_store_id')
    def _compute_company_domain(self):
        for rec in self:
            company_ids = rec.nhcl_store_id.mapped(
                'nhcl_store_name.company_id.id'
            )

            if company_ids:
                rec.company_domain = str([
                    ('id', 'in', company_ids)
                ])
            else:
                rec.company_domain = str([
                    ('id', '=', 0)
                ])

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.credit_note_bills_report_ids
            # rec.total_order_quantity = sum(lines.mapped('nhcl_order_quantity'))
            # rec.total_discount_amount = sum(lines.mapped('nhcl_discount_amount'))
            rec.total_amount_total = sum(lines.mapped('nhcl_amount_total'))
            rec.total_tax_amount = sum(lines.mapped('nhcl_tax_amount'))
            rec.total_in_amount_total = sum(lines.mapped('nhcl_in_amount_total'))

    def action_load_data(self):
        self.credit_note_bills_report_ids.unlink()

        for store in self:

            start_dt = datetime.datetime.combine(store.from_date, datetime.time.min)
            end_dt = datetime.datetime.combine(store.to_date, datetime.time.max)

            company_ids = store.nhcl_store_id.mapped(
                'nhcl_store_name.company_id.id'
            )

            if not company_ids:
                continue

            pickings = self.env['stock.picking'].search([
                ('stock_picking_type', '=', 'exchange'),
                ('state', '=', 'done'),
                ('date_done', '>=', start_dt),
                ('date_done', '<=', end_dt),
                ('company_id', 'in', company_ids)
            ])

            vals_list = []

            for picking in pickings:

                if picking.company_type == 'same':
                    order = picking.nhcl_pos_order
                else:
                    order = self.env['pos.order'].search([
                        ('pos_reference', '=', picking.store_pos_order)
                    ], limit=1)

                if not order:
                    continue

                net = sum(order.lines.mapped('price_subtotal'))
                gross = sum(order.lines.mapped('price_subtotal_incl'))
                tax = gross - net

                vals_list.append({
                    'nhcl_order_ref': picking.name,
                    'config_id': order.config_id.id,
                    # 'partner_phone': order.partner_phone,
                    # 'nhcl_order_quantity': picking.total_quantity,
                    'nhcl_amount_total': net,
                    'nhcl_in_amount_total': gross,
                    # 'nhcl_discount_amount': total_discount,
                    'nhcl_tax_amount': tax,
                    'nhcl_date_order': picking.date_done,
                    'nhcl_company_id': picking.company_id.id,
                    'credit_note_bills_report_id': store.id,
                })

            if vals_list:
                self.env['nhcl.credit.notes.bills.report.line'].create(vals_list)

    def action_to_reset(self):
        self.write({
            'nhcl_company_id': False,
            'from_date': False,
            'to_date': False
        })
        self.credit_note_bills_report_ids.unlink()

    def action_get_excel(self):
        # Create a file-like buffer to receive the data
        if not self.credit_note_bills_report_ids:
            self.action_load_data()

        if not self.credit_note_bills_report_ids:
            return False

        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Store', 'Terminal', 'Order Ref', 'Date', 'Phone', 'Quantity', 'Discount', 'Net', 'Tax', 'Gross']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.credit_note_bills_report_ids, start=1):
            worksheet.write(row_num, 0, line.nhcl_company_id.name)
            worksheet.write(row_num, 1, line.config_id.name)
            worksheet.write(row_num, 2, line.nhcl_order_ref)
            worksheet.write(row_num, 3, line.nhcl_date_order and format_date(self.env, line.nhcl_date_order,
                                                                             date_format='dd-MM-yyyy'))
            # worksheet.write(row_num, 4, line.partner_phone)
            # worksheet.write(row_num, 4, line.nhcl_order_quantity)
            # worksheet.write(row_num, 6, line.nhcl_discount_amount)
            worksheet.write(row_num, 4, line.nhcl_amount_total)
            worksheet.write(row_num, 5, line.nhcl_tax_amount)
            worksheet.write(row_num, 6, line.nhcl_in_amount_total)

        # Close the workbook
        workbook.close()

        # Get the content of the buffer
        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        # Encode the data in base64
        encoded_data = base64.b64encode(excel_data)

        # Create an attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'Credit_Note_bills_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Credit_Note_bills_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_view_credit_note_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Credit Note Bill  Report Lines',
            'res_model': 'nhcl.credit.notes.bills.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('credit_note_bills_report_id', '=', self.id)],
            'context': {
                'default_credit_note_bills_report_id': self.id
            }
        }


class NHCLCreditNoteBillsReportLine(models.Model):
    _name = 'nhcl.credit.notes.bills.report.line'
    _description = "NHCL Credit Note Bills Report line"

    credit_note_bills_report_id = fields.Many2one('nhcl.credit.notes.bills.report')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    config_id = fields.Many2one('pos.config', string="Terminal")
    nhcl_order_ref = fields.Char(string="Reference")
    nhcl_date_order = fields.Datetime(string="Date")
    partner_phone = fields.Char(string="Phone")
    nhcl_order_quantity = fields.Integer(string="Quantity")
    nhcl_amount_total = fields.Float(string="Net")
    nhcl_discount_amount = fields.Float(string="Discount Amount")
    nhcl_in_amount_total = fields.Float(string="Gross")
    nhcl_tax_amount = fields.Float(string="Tax Amount")
