from odoo import models,fields,api,_
import requests
from datetime import datetime
import pytz

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict


class NhclDailySaleReport(models.Model):
    _name = 'nhcl.daily.sale.report'

    def _default_stores(self):
        ho_store_id = self.nhcl_store_id.search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
        self.nhcl_store_id = ho_store_id

    from_date = fields.Datetime('From Date')
    to_date = fields.Datetime('To Date')
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company', default=lambda self: self._default_stores())
    nhcl_daily_sale_report_ids = fields.One2many('nhcl.daily.sale.report.line', 'nhcl_daily_sale_report_id')

    def daily_sale_dsd_report(self):
        self.nhcl_daily_sale_report_ids.unlink()
        try:
            for store in self.nhcl_store_id:
                # Fetch store details
                ho_ip = store.nhcl_terminal_ip
                ho_port = store.nhcl_port_no
                ho_api_key = store.nhcl_api_key
                user_tz = self.env.user.tz or pytz.utc
                local = pytz.timezone(user_tz)

                # Convert from_date and to_date to the local timezone
                from_date = datetime.strftime(
                    pytz.utc.localize(
                        datetime.strptime(str(self.from_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
                    "%Y-%m-%d %H:%M:%S")
                to_date = datetime.strftime(
                    pytz.utc.localize(datetime.strptime(str(self.to_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(
                        local),
                    "%Y-%m-%d %H:%M:%S")

                # Construct URLs for POS orders and POS order lines
                pos_order_search_url = f"http://{ho_ip}:{ho_port}/api/pos.order/search"
                pos_order_line_search_url = f"http://{ho_ip}:{ho_port}/api/pos.order.line/search"
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}

                # Fetch the POS order and POS order line data for the store
                pos_order_data = requests.get(pos_order_search_url, headers=headers_source).json()
                pos_order_line_data = requests.get(pos_order_line_search_url, headers=headers_source).json()

                # Extract the POS order line data
                pos_data_line = pos_order_line_data.get("data", [])

                # Process the POS data for the store
                for data in pos_data_line:
                    print("data",data)
                    date_order_str = data.get("create_date")

                    # Update the format to handle fractional seconds
                    try:
                        # Handle the case where fractional seconds are included in the timestamp
                        date_order = datetime.strptime(date_order_str, "%Y-%m-%dT%H:%M:%S.%f").strftime(
                            "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        # If there are no fractional seconds, use the original format
                        date_order = datetime.strptime(date_order_str, "%Y-%m-%dT%H:%M:%S").strftime(
                            "%Y-%m-%d %H:%M:%S")

                    date_order_local = datetime.strftime(
                        pytz.utc.localize(
                            datetime.strptime(str(date_order), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
                        "%Y-%m-%d %H:%M:%S")

                    # Only include records within the date range
                    if from_date <= date_order_local <= to_date:

                        # Find or create the nhcl.ho.store.master record (this assumes a lookup by name or similar logic)
                        store_master = self.env['nhcl.ho.store.master'].search([('id', '=', store.id)], limit=1)
                        if data.get("product_id"):
                            product = data.get("product_id")[0]["id"]
                            store_product_search_url = f"http://{ho_ip}:{ho_port}/api/product.product/{product}"
                            product_data = requests.get(store_product_search_url, headers=headers_source).json()
                            store_product_data_list = product_data.get("data", [])
                            if isinstance(store_product_data_list, list) and store_product_data_list:
                                store_product_data = store_product_data_list[0]
                            else:
                                store_product_data = {}
                            barcode = store_product_data.get("barcode")
                            if not barcode:
                                # _logger.warning(f"No barcode found for product ID {product}, skipping line.")
                                continue  # Or handle this case gracefully

                            categ_name = self.env['product.product'].sudo().search([('barcode', '=', barcode)], limit=1)

                            if store_master and data.get("tax_ids"):
                                exit_line = self.nhcl_daily_sale_report_ids.filtered(
                                    lambda x: x.nhcl_store_id == store_master and x.family_name == categ_name.categ_id.parent_id.parent_id.parent_id.complete_name and x.category_name == categ_name.categ_id.parent_id.parent_id.complete_name
                                and x.class_name == categ_name.categ_id.parent_id.complete_name and x.brick_name == categ_name.categ_id.complete_name)

                                if exit_line:
                                    # Update existing line
                                    exit_line.write({
                                        'bill_qty': exit_line.bill_qty + data.get("qty"),
                                        'net_amount': exit_line.net_amount + data.get("price_subtotal_incl"),
                                        'nhcl_store_id': store_master.id,
                                    })
                                else:
                                    self.env['nhcl.daily.sale.report.line'].create({
                                        'family_name': categ_name.categ_id.parent_id.parent_id.parent_id.complete_name,
                                        'category_name': categ_name.categ_id.parent_id.parent_id.complete_name,
                                        'class_name': categ_name.categ_id.parent_id.complete_name,
                                        'brick_name': categ_name.categ_id.complete_name,
                                        'bill_qty': data.get("qty"),
                                        'net_amount': data.get("price_subtotal_incl"),
                                        'nhcl_store_id': store_master.id,
                                        'nhcl_daily_sale_report_id': self.id
                                    })
                        else:
                            print(
                                f"Store master not found for {store.nhcl_store_name.name}, skipping processing for this store.")
                    else:
                        print(
                            f"POS order line for store {store.nhcl_store_name.name} is outside the specified date range.")

        except requests.exceptions.RequestException as e:
            print(f"Failed to retrieve POS orders for store {store.nhcl_store_name.name}: {e}")

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


class NhclDailySaleReportLine(models.Model):
    _name = 'nhcl.daily.sale.report.line'

    nhcl_daily_sale_report_id = fields.Many2one('nhcl.daily.sale.report', string="Daily Sale Report")
    nhcl_store_id = fields.Many2one('nhcl.ho.store.master', string='Store Name')
    family_name = fields.Char(string="Family")
    category_name = fields.Char(string="Category")
    class_name = fields.Char(string="Class")
    brick_name = fields.Char(string="Brick")
    bill_qty = fields.Float(string="BillQty")
    net_amount = fields.Float(string="NetAmt")

