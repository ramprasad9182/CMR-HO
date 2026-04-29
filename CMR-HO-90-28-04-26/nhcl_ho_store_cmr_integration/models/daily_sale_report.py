from odoo import models,fields,api,_
import requests
from datetime import datetime, time
import pytz

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict


class NhclDailySaleReport(models.Model):
    _name = 'nhcl.daily.sale.report'
    _description = "Nhcl Daily Sale Report"
    _rec_name = 'name'

    def _default_stores(self):
        ho_store_id = self.nhcl_store_id.search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
        self.nhcl_store_id = ho_store_id

    def _default_from_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(3, 30, 0))
        )


    def _default_to_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(18, 30, 0))
        )


    from_date = fields.Datetime(
        string='From Date',
        default=_default_from_date
    )
    to_date = fields.Datetime(
        string='To Date',
        default=_default_to_date
    )
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company', default=lambda self: self._default_stores())
    nhcl_daily_sale_report_ids = fields.One2many('nhcl.daily.sale.report.line', 'nhcl_daily_sale_report_id')
    name = fields.Char(string='Name', default='Daily Sale DSD Report')
    family = fields.Many2one(
        'product.category',
        string='Family',
        domain=[('parent_id', '=', False)]
    )

    category = fields.Many2one(
        'product.category',
        string='Category',
        domain="[('parent_id', '=', family)]"
    )

    nhcl_class = fields.Many2one(
        'product.category',
        string='Class',
        domain="[('parent_id', '=', category)]"
    )

    brick = fields.Many2one(
        'product.category',
        string='Brick',
        domain="[('parent_id', '=', nhcl_class)]"
    )

    total_bill_qty = fields.Float(compute="_compute_nhcl_show_totals", string='Total Bill Qty')
    total_net_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Amount')

    @api.onchange('family')
    def _onchange_family(self):
        self.category = False
        self.nhcl_class = False
        self.brick = False

    @api.onchange('category')
    def _onchange_category(self):
        self.nhcl_class = False
        self.brick = False

    @api.onchange('nhcl_class')
    def _onchange_nhcl_class(self):
        self.brick = False

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.nhcl_daily_sale_report_ids
            rec.total_bill_qty = sum(lines.mapped('bill_qty'))
            rec.total_net_amount = sum(lines.mapped('net_amount'))

    def daily_sale_dsd_report(self):
        self.nhcl_daily_sale_report_ids.unlink()

        for rec in self:
            for store in rec.nhcl_store_id:

                domain = [
                    ('order_id.date_order', '>=', rec.from_date),
                    ('order_id.date_order', '<=', rec.to_date),
                    ('order_id.company_id.name', '=', store.nhcl_store_name.name)
                ]

                # Family filter
                if rec.family:
                    domain.append(
                        ('product_id.categ_id.parent_id.parent_id.parent_id', '=', rec.family.id)
                    )

                # Category filter
                if rec.category:
                    domain.append(
                        ('product_id.categ_id.parent_id.parent_id', '=', rec.category.id)
                    )

                # Class filter
                if rec.nhcl_class:
                    domain.append(
                        ('product_id.categ_id.parent_id', '=', rec.nhcl_class.id)
                    )

                # Brick filter
                if rec.brick:
                    domain.append(
                        ('product_id.categ_id', '=', rec.brick.id)
                    )

                # Fetch POS order lines for selected store
                pos_lines = self.env['pos.order.line'].search(domain)

                for line in pos_lines:
                    categ = line.product_id.categ_id

                    family_name = (
                        categ.parent_id.parent_id.parent_id.complete_name
                        if categ.parent_id and
                           categ.parent_id.parent_id and
                           categ.parent_id.parent_id.parent_id
                        else ''
                    )

                    category_name = (
                        categ.parent_id.parent_id.complete_name
                        if categ.parent_id and categ.parent_id.parent_id
                        else ''
                    )

                    class_name = (
                        categ.parent_id.complete_name
                        if categ.parent_id
                        else ''
                    )

                    brick_name = categ.complete_name

                    existing_line = rec.nhcl_daily_sale_report_ids.filtered(
                        lambda x:
                        x.nhcl_store_id.id == store.id and
                        x.family_name == family_name and
                        x.category_name == category_name and
                        x.class_name == class_name and
                        x.brick_name == brick_name
                    )

                    if existing_line:
                        existing_line.write({
                            'bill_qty': existing_line.bill_qty + line.qty,
                            'net_amount': existing_line.net_amount + line.price_subtotal_incl,
                        })
                    else:
                        self.env['nhcl.daily.sale.report.line'].create({
                            'family_name': family_name,
                            'category_name': category_name,
                            'class_name': class_name,
                            'brick_name': brick_name,
                            'bill_qty': line.qty,
                            'net_amount': line.price_subtotal_incl,
                            'nhcl_store_id': store.id,
                            'nhcl_daily_sale_report_id': rec.id
                        })

    def action_to_reset(self):
        self.write({
            'nhcl_store_id': False,
            'from_date': False,
            'to_date': False
        })
        self.nhcl_daily_sale_report_ids.unlink()

    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Store Name','Family', 'Category','Class','Brick','BillQty','NetAmt']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.nhcl_daily_sale_report_ids, start=1):
            worksheet.write(row_num, 0, line.nhcl_store_id.nhcl_store_name.name)
            worksheet.write(row_num, 1, line.family_name)
            worksheet.write(row_num, 2, line.category_name)
            worksheet.write(row_num, 3, line.class_name)
            worksheet.write(row_num, 3, line.brick_name)
            worksheet.write(row_num, 4, line.bill_qty)
            worksheet.write(row_num, 4, line.net_amount)

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
            'name': f'Sale_order_Daily_Based_Report{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Sale_order_Daily_Based_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def action_daily_sale_detailed_view(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily sale DSD Report',
            'res_model': 'nhcl.daily.sale.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_daily_sale_report_id', '=', self.id)],
            'context': {
                'default_read_group': self.id
            }
        }


class NhclDailySaleReportLine(models.Model):
    _name = 'nhcl.daily.sale.report.line'
    _description = "NHcl Daily Sale Report Line"

    nhcl_daily_sale_report_id = fields.Many2one('nhcl.daily.sale.report', string="Daily Sale Report")
    nhcl_store_id = fields.Many2one('nhcl.ho.store.master', string='Store Name')
    family_name = fields.Char(string="Family")
    category_name = fields.Char(string="Category")
    class_name = fields.Char(string="Class")
    brick_name = fields.Char(string="Brick")
    bill_qty = fields.Float(string="BillQty")
    net_amount = fields.Float(string="Total Amount")

