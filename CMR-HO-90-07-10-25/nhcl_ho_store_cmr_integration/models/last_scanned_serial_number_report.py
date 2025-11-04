import base64
from datetime import datetime
import pytz

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date

import requests
from odoo import models,fields,api,_
import logging

_logger = logging.getLogger(__name__)

class LastScannedSerialNumberReport(models.TransientModel):
    _name = 'last.scanned.serial.number.report'

    def _default_stores(self):
        ho_store_id = self.nhcl_store_id.search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
        self.nhcl_store_id = ho_store_id


    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company',default=lambda self: self._default_stores())
    last_scanned_report_line_ids = fields.One2many('last.scanned.serial.number.report.line', 'last_scanned_report_id')

    def get_last_scanned_unmatched_product_report(self):
        self.last_scanned_report_line_ids.unlink()
        vals_list = []

        for store in self.nhcl_store_id:
            store_ip = store.nhcl_terminal_ip
            store_port = store.nhcl_port_no
            store_api_key = store.nhcl_api_key

            base_url = f"http://{store_ip}:{store_port}/api"
            headers = {'api-key': store_api_key, 'Content-Type': 'application/json'}

            try:
                # --- Fetch last scanned serial numbers ---
                url = f"{base_url}/last.scanned.serial.number/search"
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                scanned_data = response.json().get("data", [])
                _logger.info("Fetched %s records from %s", len(scanned_data), store.nhcl_store_name.name)

                for rec in scanned_data:
                    rec_date = datetime.strptime(rec['date'], "%Y-%m-%d").date()
                    if not (self.from_date <= rec_date <= self.to_date):
                        continue  # skip outside date range

                    # --- Fetch product info only if needed ---
                    product_name = False
                    stock_product = rec.get("stock_product_id")
                    if stock_product:
                        product_id = stock_product[0].get("id")
                        if product_id:
                            product_url = f"{base_url}/product.product/{product_id}"
                            try:
                                product_resp = requests.get(product_url, headers=headers, timeout=20)
                                product_resp.raise_for_status()
                                product_info_list = product_resp.json().get("data", [])
                                if product_info_list:
                                    product_info = product_info_list[0]
                                    product = self.env['product.product'].search(
                                        [('default_code', '=', product_info.get("default_code"))],
                                        limit=1
                                    )
                                    product_name = product.display_name if product else product_info.get("name")
                            except requests.exceptions.RequestException as pe:
                                _logger.warning("Product fetch failed for %s: %s", product_id, pe)

                    # --- Prepare vals ---
                    vals_list.append({
                        'last_scanned_report_id': self.id,
                        'scanned_product_name': product_name,
                        'scanned_serial': rec.get('stock_serial'),
                        'scanned_product_barcode': rec.get('stock_product_barcode'),
                        'stock_qty': rec.get('stock_qty'),
                        'store_name': rec.get('store_name'),
                        'store_receipt_number': rec.get('Receipt_number'),
                        'source_document': rec.get('document_number')
                    })

            except requests.exceptions.RequestException as e:
                _logger.error("Failed to fetch data from store %s: %s", store.nhcl_store_name.name, e)

        # --- Bulk create all lines at once ---
        if vals_list:
            self.env['last.scanned.serial.number.report.line'].create(vals_list)

    def action_to_reset(self):
        self.last_scanned_report_line_ids.unlink()
        self.write({
            'nhcl_store_id': False,
            'from_date': False,
            'to_date': False,

        })

    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['StoreName','Product','Serial Number','Quantity','Store Receipt Number']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.last_scanned_report_line_ids, start=1):
            worksheet.write(row_num, 0, line.store_name)
            worksheet.write(row_num, 1, line.scanned_product_name)
            worksheet.write(row_num, 2, line.scanned_serial)
            worksheet.write(row_num, 3, line.stock_qty)
            worksheet.write(row_num, 4, line.store_receipt_number)

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
            'name': f'Last_Scanned_Serial_numbers_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Last_Scanned_Serial_numbers_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

class LastScannedSerialNumberReportLine(models.TransientModel):
    _name = 'last.scanned.serial.number.report.line'

    last_scanned_report_id = fields.Many2one('last.scanned.serial.number.report', string="Last Scanned Report",ondelete='cascade')
    scanned_product_id = fields.Many2one('product.product', string='Product',ondelete='cascade')
    scanned_product_name = fields.Char(string='Product', copy=False)
    scanned_serial = fields.Char(string="Serial's", copy=False)
    scanned_product_barcode = fields.Char(string="Barcode", copy=False)
    stock_qty = fields.Float(string='Qty', copy=False)
    store_name = fields.Char(String="Store Name")
    store_receipt_number = fields.Char(string="Store Receipt Number")
    source_document = fields.Char(string="HO Delivery Doc")

