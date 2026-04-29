from odoo import models, fields, api, _
import base64
import io
import datetime
import xlsxwriter


class NHCLCreditNoteSettlementSummaryReport(models.Model):
    _name = 'credit.note.settlement.summary.report'
    _description = "Credit Note Settlement Summary Report"
    _rec_name = 'id'


    def _default_stores(self):
        return self.env['nhcl.ho.store.master'].search([
            ('nhcl_active', '=', True),
            ('nhcl_store_type', '!=', 'ho')
        ]).ids

    from_date = fields.Date(string="From Date")
    to_date = fields.Date(string="To Date")
    nhcl_company_id = fields.Many2one( 'res.company',string="Store Name")
    nhcl_store_id = fields.Many2many( 'nhcl.ho.store.master', string="Company",  default=_default_stores)
    line_ids = fields.One2many('credit.note.settlement.summary.line','report_id', string="Lines")
    company_domain = fields.Char( string="Company Domain", compute="_compute_company_domain")

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

    def action_load_data(self):
        self.line_ids.unlink()
        for rec in self:
            start_dt = datetime.datetime.combine(
                rec.from_date,
                datetime.time.min
            )
            end_dt = datetime.datetime.combine(
                rec.to_date,
                datetime.time.max
            )
            payments = self.env['pos.payment'].search([
                ('payment_method_id.name', '=', 'Credit Note Settlement'),
                ('payment_date', '>=', start_dt),
                ('payment_date', '<=', end_dt),
            ])
            if rec.nhcl_company_id:
                payments = payments.filtered(
                    lambda x:
                    x.pos_order_id.company_id.id == rec.nhcl_company_id.id
                )
            vals_list = []
            processed_orders = []
            for pay in payments:
                order = pay.pos_order_id
                if not order:
                    continue

                if order.id in processed_orders:
                    continue

                processed_orders.append(order.id)

                gross = pay.amount

                order_total = order.amount_total or 1
                ratio = gross / order_total

                tax = order.amount_tax * ratio
                net = gross - tax

                discount = 0.0
                for line in order.lines:
                    line_total = line.qty * line.price_unit
                    discount += line_total * (line.discount / 100.0)

                vals_list.append({
                    'report_id': rec.id,
                    'nhcl_company_id': order.company_id.id,
                    'config_id': order.config_id.id,
                    'date_order': order.date_order,
                    # 'partner_phone': order.partner_phone or '',
                    'base_bill_no': order.pos_reference or '',
                    'net_amount': net,
                    'discount_amount': discount,
                    'gross_amount': gross,
                    'tax_amount': tax,
                    'payment_methods': pay.payment_method_id.name,
                })

            if vals_list:
                self.env[
                    'credit.note.settlement.summary.line'
                ].create(vals_list)

    def action_reset(self):
        self.write({
            'from_date': False,
            'to_date': False,
            'nhcl_company_id': False,
            'nhcl_store_id': [(5, 0, 0)],
        })
        self.line_ids.unlink()

    def action_get_excel(self):
        if not self.line_ids:
            self.action_load_data()
        if not self.line_ids:
            return False
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(
            buffer,
            {'in_memory': True}
        )
        sheet = workbook.add_worksheet('Report')
        bold = workbook.add_format({
            'bold': True
        })
        headers = [
            'Store',
            'Terminal',
            'Date',
            'Base Bill No',
            'Net',
            'Discount',
            'Gross',
            'Tax',
            'Payment Method'
        ]
        for col, header in enumerate(headers):
            sheet.write(0, col, header, bold)
        row = 1
        for line in self.line_ids:
            sheet.write(row, 0, line.nhcl_company_id.name)
            sheet.write(row, 1, line.config_id.name)
            sheet.write(row, 2, str(line.date_order))
            sheet.write(row, 3, line.base_bill_no)
            sheet.write(row, 4, line.net_amount)
            sheet.write(row, 5, line.discount_amount)
            sheet.write(row, 6, line.gross_amount)
            sheet.write(row, 7, line.tax_amount)
            sheet.write(row, 8, line.payment_methods)
            row += 1
        workbook.close()
        buffer.seek(0)
        file_data = buffer.read()
        buffer.close()
        attachment = self.env['ir.attachment'].create({
            'name': 'Credit_Note_Settlement_Report.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(file_data),
            'mimetype':
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'new',
        }

    def action_view_credit_note_settlement_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Credit Note Setttlement Summary Report Lines',
            'res_model': 'credit.note.settlement.summary.line',
            'view_mode': 'tree,pivot',
            'domain': [('report_id', '=', self.id)],
            'context': {
                'default_report_id': self.id
            }
        }


class NHCLCreditNoteSettlementSummaryLine(models.Model):
    _name = 'credit.note.settlement.summary.line'
    _description = "Credit Note Settlement Summary Line"

    report_id = fields.Many2one( 'credit.note.settlement.summary.report' )
    nhcl_company_id = fields.Many2one('res.company',string="Store Name" )
    config_id = fields.Many2one('pos.config', string="Terminal" )
    date_order = fields.Datetime( string="Date" )
    partner_phone = fields.Char( string="Customer Phone No" )
    base_bill_no = fields.Char( string="Base Bill No")
    net_amount = fields.Float( string="Net")
    discount_amount = fields.Float(string="Discount")
    gross_amount = fields.Float(string="Gross")
    tax_amount = fields.Float(  string="Tax Amount")
    payment_methods = fields.Char(string="Payment Method")