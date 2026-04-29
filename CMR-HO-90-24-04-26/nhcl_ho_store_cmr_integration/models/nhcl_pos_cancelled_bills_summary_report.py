from odoo import models, fields, api, _

import base64
import io

import datetime
import xlsxwriter
from odoo.tools import format_date


class NHCLPosCancelledBillsReport(models.Model):
    _name = 'nhcl.pos.cancelled.bills.report'
    _description = "NHCL POS Cancelled Bills Report"
    _rec_name = 'nhcl_company_id'

    def _default_stores(self):
        return self.env['nhcl.ho.store.master'].search([
            ('nhcl_active', '=', True),
            ('nhcl_store_type', '!=', 'ho')
        ]).ids

    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    cancel_bills_report_ids = fields.One2many('nhcl.pos.cancelled.bills.report.line', 'cancel_bills_report_id')
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string="Company", default=_default_stores)
    total_order_quantity = fields.Float(compute="_compute_nhcl_show_totals", string='Total Quantities')
    total_discount_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Discount')
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
            lines = rec.cancel_bills_report_ids
            rec.total_order_quantity = sum(lines.mapped('nhcl_order_quantity'))
            rec.total_discount_amount = sum(lines.mapped('nhcl_discount_amount'))
            rec.total_amount_total = sum(lines.mapped('nhcl_amount_total'))
            rec.total_tax_amount = sum(lines.mapped('nhcl_tax_amount'))
            rec.total_in_amount_total = sum(lines.mapped('nhcl_in_amount_total'))

    def action_load_data(self):
        # Remove existing lines
        self.cancel_bills_report_ids.unlink()

        for store in self:
            # 🔹 Fetch POS order lines from local DB
            start_dt = datetime.datetime.combine(store.from_date, datetime.time.min)
            end_dt = datetime.datetime.combine(store.to_date, datetime.time.max)

            company_ids = store.nhcl_store_id.mapped(
                'nhcl_store_name.company_id.id'
            )

            if not company_ids:
                continue

            pos_lines = self.env['pos.order.line'].search([
                ('order_id.name', 'ilike', 'Refund'),
                ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
                ('order_id.date_order', '>=', start_dt),
                ('order_id.date_order', '<=', end_dt),
                ('company_id', 'in', company_ids)
            ])

            grouped_data = {}
            for line in pos_lines:

                order = line.order_id

                order_ref = order.name
                # receipt_ref = order.pos_reference
                if not order_ref:
                    continue

                line_total = line.qty * line.price_unit

                # Convert date to user timezone
                date_order = fields.Datetime.context_timestamp(self, order.date_order)

                qty = line.qty
                subtotal = line.price_subtotal
                tax_inc_total = line.price_subtotal_incl
                is_fix_discount_line = getattr(line, 'is_fix_discount_line', False)
                reward_id = getattr(line, 'reward_id', False)
                is_reward_line = getattr(line, 'is_reward_line', False)
                gdiscount = getattr(line, 'gdiscount', False)
                # discount_reward = getattr(line, 'discount_reward', False)

                # # ❌ Ignore refunds
                # if qty < 0:
                #     continue

                # Initialize group
                if order_ref not in grouped_data:
                    grouped_data[order_ref] = {
                        'qty': 0,
                        'config_id': order.config_id.id,
                        'company_id': order.company_id.id,
                        # 'partner_phone': order.partner_phone,
                        'amount_excl': 0.0,
                        'amount_incl': 0.0,
                        'tax_amount': 0.0,
                        'nhcl_discount_amount': 0.0,
                        'date': date_order.strftime("%Y-%m-%d %H:%M:%S"),
                    }

                # if subtotal > 0:
                grouped_data[order_ref]['qty'] += qty
                grouped_data[order_ref]['amount_excl'] += subtotal
                grouped_data[order_ref]['amount_incl'] += tax_inc_total
                grouped_data[order_ref]['tax_amount'] += tax_inc_total - subtotal

                if is_fix_discount_line:
                    grouped_data[order_ref]['nhcl_discount_amount'] += tax_inc_total

                # ✅ DISCOUNT / PROMOTION lines
                if reward_id or is_reward_line:
                    grouped_data[order_ref]['nhcl_discount_amount'] += line_total * (line.discount / 100.0)
                if gdiscount:
                    grouped_data[order_ref]['nhcl_discount_amount'] += line_total * (line.gdiscount / 100.0)
                # if discount_reward:
                #     grouped_data[order_ref]['nhcl_discount_amount'] += tax_inc_total

            # 🔹 Bulk create
            vals_list = []
            for order_ref, values in grouped_data.items():
                vals_list.append({
                    'nhcl_order_ref': order_ref,
                    'config_id': values['config_id'],
                    # 'partner_phone': values['partner_phone'],
                    'nhcl_order_quantity': values['qty'],
                    'nhcl_amount_total': values['amount_excl'],
                    'nhcl_in_amount_total': values['amount_incl'],
                    'nhcl_discount_amount': values['nhcl_discount_amount'],
                    'nhcl_tax_amount': values['tax_amount'],
                    'nhcl_date_order': values['date'],
                    'nhcl_company_id': values['company_id'],
                    'cancel_bills_report_id': store.id,
                })

            if vals_list:
                self.env['nhcl.pos.cancelled.bills.report.line'].create(vals_list)

    def action_to_reset(self):
        self.write({
            'nhcl_company_id': False,
            'from_date': False,
            'to_date': False
        })
        self.cancel_bills_report_ids.unlink()

    def action_get_excel(self):
        # Create a file-like buffer to receive the data
        if not self.cancel_bills_report_ids:
            self.action_load_data()

        if not self.cancel_bills_report_ids:
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
        for row_num, line in enumerate(self.cancel_bills_report_ids, start=1):
            worksheet.write(row_num, 0, line.nhcl_company_id.name)
            worksheet.write(row_num, 1, line.config_id.name)
            worksheet.write(row_num, 2, line.nhcl_order_ref)
            worksheet.write(row_num, 3, line.nhcl_date_order and format_date(self.env, line.nhcl_date_order,
                                                                             date_format='dd-MM-yyyy'))
            # worksheet.write(row_num, 4, line.partner_phone)
            worksheet.write(row_num, 4, line.nhcl_order_quantity)
            worksheet.write(row_num, 5, line.nhcl_discount_amount)
            worksheet.write(row_num, 6, line.nhcl_amount_total)
            worksheet.write(row_num, 7, line.nhcl_tax_amount)
            worksheet.write(row_num, 8, line.nhcl_in_amount_total)

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
            'name': f'POS_cancelled_bills_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'POS_cancelled_bills_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_view_pos_cancelled_bills(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Cancelled Bills Report Lines',
            'res_model': 'nhcl.pos.cancelled.bills.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('cancel_bills_report_id', '=', self.id)],
            'context': {
                'default_cancel_bills_report_id': self.id
            }
        }



class NHCLPosCancelledBillsReportLine(models.Model):
    _name = 'nhcl.pos.cancelled.bills.report.line'
    _description = "NHCL POS Cancelled Bills Report line"

    cancel_bills_report_id = fields.Many2one('nhcl.pos.cancelled.bills.report')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    config_id = fields.Many2one('pos.config', string="Terminal")
    nhcl_order_ref = fields.Char(string="Order Ref")
    nhcl_date_order = fields.Datetime(string="Date")
    partner_phone = fields.Char(string="Phone")
    nhcl_order_quantity = fields.Integer(string="Quantity")
    nhcl_amount_total = fields.Float(string="Net")
    nhcl_discount_amount = fields.Float(string="Discount Amount")
    nhcl_in_amount_total = fields.Float(string="Gross")
    nhcl_tax_amount = fields.Float(string="Tax Amount")
