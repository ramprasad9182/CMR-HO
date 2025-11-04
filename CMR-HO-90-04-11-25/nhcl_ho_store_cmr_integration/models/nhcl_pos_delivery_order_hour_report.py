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
import logging

_logger = logging.getLogger(__name__)

class NhclPOSDeliveryHourReport(models.Model):
    _name = 'nhcl.pos.delivery.hour.report'

    from_date = fields.Datetime('From Date')
    to_date = fields.Datetime('To Date')
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company')
    nhcl_pos_delivery_order_hour_report_ids = fields.One2many('nhcl.pos.delivery.order.hour.report.line', 'nhcl_pos_delivery_order_hour_report_id')

    @api.model
    def default_get(self, fields_list):
        res = super(NhclPOSDeliveryHourReport, self).default_get(fields_list)
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            vals = {
                'nhcl_store_id': i.nhcl_store_name.id,
            }
            replication_data.append((0, 0, vals))
        res.update({'nhcl_store_id': replication_data})
        return res

    def get_pos_delivery_order_hour_report(self):
        self.nhcl_pos_delivery_order_hour_report_ids.unlink()

        user_tz = self.env.user.tz or 'UTC'
        local_tz = pytz.timezone(user_tz)

        # Parse and localize input date range
        from_dt = pytz.utc.localize(datetime.strptime(str(self.from_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(
            local_tz)
        to_dt = pytz.utc.localize(datetime.strptime(str(self.to_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(
            local_tz)

        for store in self.nhcl_store_id:
            store_ip = store.nhcl_terminal_ip
            store_port = store.nhcl_port_no
            store_api_key = store.nhcl_api_key

            pos_order_line_search_url = f"http://{store_ip}:{store_port}/api/stock.move/search"
            headers = {'api-key': store_api_key, 'Content-Type': 'application/json'}

            try:
                response = requests.get(pos_order_line_search_url, headers=headers)
                response.raise_for_status()
                pos_delivery_order_data = response.json()
                pos_data_line = pos_delivery_order_data.get("data", [])

                for data in pos_data_line:
                    picking_type = data.get("picking_type_id")
                    if not (picking_type and isinstance(picking_type, list) and len(picking_type) > 0):
                        _logger.warning(f"Skipping record with invalid picking_type_id: {data}")
                        continue

                    if picking_type[0].get("name") != "PoS Orders":
                        continue

                    product_id = data.get("product_id")[0]["id"]
                    product_url = f"http://{store_ip}:{store_port}/api/product.product/{product_id}"
                    product_data_response = requests.get(product_url, headers=headers)
                    product_data_response.raise_for_status()

                    product_info_list = product_data_response.json().get("data", [])
                    if not product_info_list:
                        _logger.warning(f"No product info returned for product ID {product_id}")
                        continue

                    product_info = product_info_list[0]
                    product = self.env['product.product'].search([
                        ('barcode', '=', product_info.get("barcode")),
                        ('default_code', '=', product_info.get("default_code"))
                    ], limit=1)

                    if not product:
                        _logger.warning(f"No matching product found in Odoo for barcode {product_info.get('barcode')}")
                        continue

                    # Parse and localize date_order
                    date_order_str = data.get("create_date")
                    try:
                        date_order = datetime.strptime(date_order_str, "%Y-%m-%dT%H:%M:%S.%f")
                    except ValueError:
                        date_order = datetime.strptime(date_order_str, "%Y-%m-%dT%H:%M:%S")
                    date_order = pytz.utc.localize(date_order).astimezone(local_tz)

                    if from_dt <= date_order <= to_dt:
                        store_master = self.env['nhcl.ho.store.master'].browse(store.id)
                        self.env['nhcl.pos.delivery.order.hour.report.line'].create({
                            'nhcl_product_id': product.display_name,
                            'nhcl_name': data.get("picking_id")[0]["name"],
                            'nhcl_order_quantity': data.get("product_qty"),
                            'nhcl_date_order': date_order.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                            'nhcl_store_id': store_master.id,
                            'nhcl_pos_delivery_order_hour_report_id': self.id
                        })

            except requests.exceptions.RequestException as e:
                _logger.error(f"Failed to retrieve POS orders from store {store.nhcl_store_name.name}: {e}")

    def action_to_reset(self):
        self.write({
            'nhcl_store_id' : False,
            'from_date' : False,
            'to_date' : False
        })
        self.nhcl_pos_delivery_order_hour_report_ids.unlink()

    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Company','Product', 'Date','Quantity']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.nhcl_pos_delivery_order_hour_report_ids, start=1):
            worksheet.write(row_num, 0, line.nhcl_store_id.nhcl_store_name.name)
            worksheet.write(row_num, 1, line.nhcl_product_id)
            worksheet.write(row_num, 2, line.nhcl_date_order and format_date(self.env, line.nhcl_date_order, date_format='dd-MM-yyyy'))
            worksheet.write(row_num, 3, line.nhcl_order_quantity)

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
            'name': f'POS_Delivery_orders_Hourly_Based_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'POS_Delivery_orders_Hourly_Based_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


class NhclPOSHourReportLine(models.Model):
    _name = 'nhcl.pos.delivery.order.hour.report.line'

    nhcl_pos_delivery_order_hour_report_id = fields.Many2one('nhcl.pos.delivery.hour.report', string="Pos Hour Report")
    nhcl_name = fields.Char(string="Name")
    nhcl_product_id = fields.Char(string="Product")
    nhcl_date_order = fields.Datetime(string="Order Date")
    nhcl_order_quantity = fields.Integer(string="Quantity")
    nhcl_store_id = fields.Many2one('nhcl.ho.store.master', string='Company')


