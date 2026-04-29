from odoo import models,fields,api,_
import requests
from datetime import datetime
import pytz
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict


class NhclStoreAssetReport(models.Model):
    _name = 'nhcl.store.asset.report'
    _description = "Nhcl Store Asset Report"
    _rec_name = 'name'

    def _default_stores(self):
        ho_store_id = self.nhcl_store_id.search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
        self.nhcl_store_id = ho_store_id

    from_date = fields.Datetime('From Date')
    to_date = fields.Datetime('To Date')
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company', default=lambda self: self._default_stores())
    nhcl_store_asset_report_ids = fields.One2many('nhcl.store.asset.report.line', 'nhcl_asset_line_report_id')
    name = fields.Char(string='Name', default='Store Wise Asset Report')

    def nhcl_store_asset_report(self):
        for record in self:
            record.nhcl_store_asset_report_ids.unlink()

            if not record.from_date or not record.to_date:
                raise ValidationError("Please select From Date and To Date.")

            from_date = record.from_date.date()
            to_date = record.to_date.date()

            for store in record.nhcl_store_id:

                ho_ip = store.nhcl_terminal_ip
                ho_port = store.nhcl_port_no
                ho_api_key = store.nhcl_api_key

                if not ho_ip or not ho_port or not ho_api_key:
                    _logger.warning("Store configuration missing for %s", store.name)
                    continue
                headers = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }

                try:
                    inventory_search_url = f"http://{ho_ip}:{ho_port}/api/cf.inventory.count/search"

                    response = requests.get(
                        inventory_search_url,
                        headers=headers,
                        timeout=15
                    )

                    if response.status_code != 200:
                        _logger.warning("Inventory fetch failed for %s", store.name)
                        continue

                    inventory_records = response.json().get("data", [])
                    if not inventory_records:
                        continue

                    grouped_data = {}

                    for inventory in inventory_records:
                        store_date_str = inventory.get("date")
                        if not store_date_str:
                            continue

                        try:
                            store_date = datetime.strptime(
                                store_date_str, "%Y-%m-%d"
                            ).date()
                        except Exception:
                            continue

                        if not (from_date <= store_date <= to_date):
                            continue

                        line_ids = [line.get('id') for line in inventory.get('line_ids', []) if line.get('id')]

                        if not line_ids:
                            continue

                        for line_id in line_ids:

                            line_url = f"http://{ho_ip}:{ho_port}/api/cf.inventory.count.line/{line_id}"

                            line_response = requests.get(
                                line_url,
                                headers=headers,
                                timeout=15
                            )

                            if line_response.status_code != 200:
                                continue

                            line_datas = line_response.json().get("data", [])

                            if not line_datas:
                                continue   # skip safely

                            for line_data in line_datas:
                                asset_data = line_data.get('asset_id')

                                if not asset_data or not isinstance(asset_data, list):
                                    continue

                                asset_dict = asset_data[0]
                                asset_name = asset_dict.get('name')

                                if not asset_name:
                                    continue

                                global_count = line_data.get("global_count", 0)

                                key = (store.id, asset_name)
                                grouped_data[key] = grouped_data.get(key, 0) + global_count

                    # STEP 3: Create grouped report lines
                    for (store_id, asset_name), total_amount in grouped_data.items():
                        self.env['nhcl.store.asset.report.line'].sudo().create({
                            'nhcl_asset_line_report_id': record.id,
                            'nhcl_store_id': store_id,
                            'asset_name': asset_name,
                            'global_amount': total_amount,
                        })

                except requests.exceptions.RequestException as e:
                    _logger.error("API Error for store %s: %s", store.name, str(e))
                    continue







    def action_to_reset(self):
        self.write({
            'nhcl_store_id': False,
            'from_date': False,
            'to_date': False
        })
        self.nhcl_store_asset_report_ids.unlink()


    def get_excel_sheet(self):

        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        bold = workbook.add_format({'bold': True})

        lines = self.nhcl_store_asset_report_ids

        # Get all asset names (columns)
        asset_names = sorted(list(set(lines.mapped('asset_name'))))

        # Header
        worksheet.write(0, 0, 'Store', bold)

        for col, asset in enumerate(asset_names, start=1):
            worksheet.write(0, col, asset, bold)

        # Prepare dictionary
        store_data = defaultdict(dict)

        for line in lines:
            store = line.nhcl_store_id.nhcl_store_name.name
            asset = line.asset_name
            store_data[store][asset] = line.global_amount

        # Write rows
        row = 1
        for store, assets in store_data.items():

            worksheet.write(row, 0, store)

            for col, asset in enumerate(asset_names, start=1):
                worksheet.write(row, col, assets.get(asset, 0))

            row += 1

        workbook.close()

        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        encoded_data = base64.b64encode(excel_data)

        attachment = self.env['ir.attachment'].create({
            'name': f'Store_Asset_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Store_Asset_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def get_asset_report_data(self):
        lines = self.sudo().nhcl_store_asset_report_ids

        asset_names = sorted(list(set(lines.mapped('asset_name'))))

        store_data = {}

        for line in lines.sudo():
            store = line.nhcl_store_id.nhcl_store_name.name
            asset = line.asset_name

            if store not in store_data:
                store_data[store] = {}

            store_data[store][asset] = line.global_amount

        return {
            'asset_names': asset_names,
            'store_data': store_data,
        }

    def action_view_store_asset_lines(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Store Asset Report Lines',
            'res_model': 'nhcl.store.asset.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_asset_line_report_id', '=', self.id)],
            'context': {
                'default_nhcl_asset_line_report_id': self.id
            }
        }


class NhclStoreAssetReportLine(models.Model):
    _name = 'nhcl.store.asset.report.line'
    _description = "NHCL Store Asset Report Line"

    nhcl_asset_line_report_id = fields.Many2one('nhcl.store.asset.report', string="Store Asset Report")
    nhcl_store_id = fields.Many2one('nhcl.ho.store.master', string='Store Name')
    asset_name = fields.Char(string='Asset Name')
    family_name = fields.Char(string="Family")
    category_name = fields.Char(string="Category")
    class_name = fields.Char(string="Class")
    brick_name = fields.Char(string="Brick")
    # bill_qty = fields.Float(string="BillQty")
    # net_amount = fields.Float(string="NetAmt")
    global_amount = fields.Float(string="GlobalAmount")

