from odoo import models, fields, api, _
import requests
from datetime import datetime, time
import pytz

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict


class NhclHSNTaxReport(models.Model):
    _name = 'nhcl.hsn.tax.report'
    _description = "Nhcl HSN Tax Report"
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
    nhcl_pos_hsn_tax_ids = fields.One2many('nhcl.hsn.tax.report.line', 'nhcl_pos_hsn_tax_id')
    name = fields.Char(string='Name', default='HSN Tax Report')
    l10n_in_hsn_code = fields.Char(string="HSN/SAC Code", help="Harmonized System Nomenclature/Services Accounting Code")
    tax_id = fields.Many2one('account.tax', string='Tax')

    def get_hsn_with_tax_wise_report(self):
        self.nhcl_pos_hsn_tax_ids.unlink()

        try:
            for store in self.nhcl_store_id:

                ho_ip = store.nhcl_terminal_ip
                ho_port = store.nhcl_port_no
                ho_api_key = store.nhcl_api_key

                user_tz = self.env.user.tz or 'UTC'
                local = pytz.timezone(user_tz)

                from_date = datetime.strftime(
                    pytz.utc.localize(
                        datetime.strptime(
                            str(self.from_date),
                            DEFAULT_SERVER_DATETIME_FORMAT
                        )
                    ).astimezone(local),
                    "%Y-%m-%d %H:%M:%S"
                )

                to_date = datetime.strftime(
                    pytz.utc.localize(
                        datetime.strptime(
                            str(self.to_date),
                            DEFAULT_SERVER_DATETIME_FORMAT
                        )
                    ).astimezone(local),
                    "%Y-%m-%d %H:%M:%S"
                )

                pos_order_line_search_url = (
                    f"http://{ho_ip}:{ho_port}/api/pos.order.line/search"
                )

                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }

                pos_order_line_data = requests.get(
                    pos_order_line_search_url,
                    headers=headers_source
                ).json()

                pos_data_line = pos_order_line_data.get("data", [])

                for data in pos_data_line:
                    date_order_str = data.get("create_date")

                    try:
                        date_order = datetime.strptime(
                            date_order_str,
                            "%Y-%m-%dT%H:%M:%S.%f"
                        ).strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        date_order = datetime.strptime(
                            date_order_str,
                            "%Y-%m-%dT%H:%M:%S"
                        ).strftime("%Y-%m-%d %H:%M:%S")

                    date_order_local = datetime.strftime(
                        pytz.utc.localize(
                            datetime.strptime(
                                date_order,
                                DEFAULT_SERVER_DATETIME_FORMAT
                            )
                        ).astimezone(local),
                        "%Y-%m-%d %H:%M:%S"
                    )

                    if not (from_date <= date_order_local <= to_date):
                        continue

                    store_master = self.env[
                        'nhcl.ho.store.master'
                    ].search([
                        ('id', '=', store.id)
                    ], limit=1)

                    if not data.get("product_id"):
                        continue

                    product_id = data.get("product_id")[0]["id"]

                    product_url = (
                        f"http://{ho_ip}:{ho_port}/api/product.product/{product_id}"
                    )

                    product_data = requests.get(
                        product_url,
                        headers=headers_source
                    ).json()

                    store_product_data_list = product_data.get("data", [])

                    if isinstance(store_product_data_list, list) and store_product_data_list:
                        store_product_data = store_product_data_list[0]
                    else:
                        store_product_data = {}

                    barcode = store_product_data.get("barcode")

                    if not barcode:
                        continue

                    hsn_product = self.env[
                        'product.product'
                    ].sudo().search([
                        ('barcode', '=', barcode)
                    ], limit=1)

                    product_hsn = hsn_product.l10n_in_hsn_code
                    tax_name = data.get("tax_ids")[0]["name"] if data.get("tax_ids") else False

                    # -------------------
                    # HSN FILTER
                    # -------------------
                    if self.l10n_in_hsn_code:
                        if product_hsn != self.l10n_in_hsn_code:
                            continue

                    # -------------------
                    # TAX FILTER
                    # -------------------
                    if self.tax_id:
                        if tax_name != self.tax_id.name:
                            continue

                    if store_master and tax_name:

                        existing_line = self.nhcl_pos_hsn_tax_ids.filtered(
                            lambda x:
                            x.nhcl_store_id == store_master and
                            x.nhcl_hsn == product_hsn and
                            x.nhcl_tax == tax_name
                        )

                        tax_amount = (
                                data.get("price_subtotal_incl") -
                                data.get("price_subtotal")
                        )

                        if existing_line:
                            existing_line.write({
                                'nhcl_order_quantity':
                                    existing_line.nhcl_order_quantity + data.get("qty"),

                                'nhcl_amount_total':
                                    existing_line.nhcl_amount_total +
                                    data.get("price_subtotal_incl"),

                                'nhcl_taxable_amount':
                                    existing_line.nhcl_taxable_amount +
                                    data.get("price_subtotal"),

                                'nhcl_tax_amount':
                                    existing_line.nhcl_tax_amount +
                                    tax_amount,

                                'nhcl_cgst_amount':
                                    existing_line.nhcl_cgst_amount +
                                    (tax_amount / 2),

                                'nhcl_sgst_amount':
                                    existing_line.nhcl_sgst_amount +
                                    (tax_amount / 2),
                            })

                        else:
                            self.env[
                                'nhcl.hsn.tax.report.line'
                            ].create({
                                'nhcl_hsn': product_hsn,
                                'nhcl_tax': tax_name,
                                'nhcl_order_quantity': data.get("qty"),
                                'nhcl_amount_total':
                                    data.get("price_subtotal_incl"),
                                'nhcl_taxable_amount':
                                    data.get("price_subtotal"),
                                'nhcl_tax_amount': tax_amount,
                                'nhcl_cgst_amount': tax_amount / 2,
                                'nhcl_sgst_amount': tax_amount / 2,
                                'nhcl_store_id': store_master.id,
                                'nhcl_pos_hsn_tax_id': self.id
                            })

        except requests.exceptions.RequestException as e:
            raise ValueError(
                f"Failed to retrieve POS data: {str(e)}"
            )

    def action_to_reset(self):
        self.write({
            'nhcl_store_id': False,
            'from_date': False,
            'to_date': False,
            'l10n_in_hsn_code': False,
            'tax_id': False
        })

        self.nhcl_pos_hsn_tax_ids.unlink()


    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['HSN', 'TAX%', 'BILLQTY', 'NETAMT', 'TAXABLEAMT', 'CGSTAMT', 'SGSTAMT']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.nhcl_pos_hsn_tax_ids, start=1):
            worksheet.write(row_num, 0, line.nhcl_hsn)
            worksheet.write(row_num, 1, line.nhcl_tax)
            worksheet.write(row_num, 2, line.nhcl_order_quantity)
            worksheet.write(row_num, 3, line.nhcl_amount_total)
            worksheet.write(row_num, 4, line.nhcl_taxable_amount)
            worksheet.write(row_num, 5, line.nhcl_cgst_amount)
            worksheet.write(row_num, 6, line.nhcl_sgst_amount)

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
            'name': f'POS_HSN_Wise_Tax_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'POS_HSN_Wise_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


    def action_hsn_tax_report_line(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'HSN Tax Report',
            'res_model': 'nhcl.hsn.tax.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_pos_hsn_tax_id', '=', self.id)],
            'context': {
                'default_nhcl_pos_hsn_tax_id': self.id
            }
        }


class NhclHSNTaxReportLine(models.Model):
    _name = 'nhcl.hsn.tax.report.line'
    _description = "Nhcl HSN Tax Report Line"

    nhcl_pos_hsn_tax_id = fields.Many2one('nhcl.hsn.tax.report', string="HSN Tax Report")
    nhcl_hsn = fields.Char(string="HSN")
    nhcl_tax = fields.Char(string="Tax%")
    nhcl_order_quantity = fields.Integer(string="BillQty")
    nhcl_amount_total = fields.Float(string="Gross AMT")
    nhcl_taxable_amount = fields.Float(string="NET AMT")
    nhcl_tax_amount = fields.Float(string="TAX AMT")
    nhcl_cgst_amount = fields.Float(string="CGST AMT")
    nhcl_sgst_amount = fields.Float(string="SGST AMT")
    nhcl_store_id = fields.Many2one('nhcl.ho.store.master', string='Company')
