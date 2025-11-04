import json

from odoo import api, fields, models
import requests
from datetime import datetime, time
import pytz

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io
import logging
import os
from odoo.exceptions import ValidationError, UserError
import xlsxwriter

_logger = logging.getLogger(__name__)




class NhclPosAuditReport(models.Model):
    _name = 'nhcl.pos.audit.report'
    _description = 'POS Audit Report'

    def _default_stores(self):
        """Default stores except HO"""
        ho_store_id = self.nhcl_store_id.search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
        self.nhcl_store_id = ho_store_id

    from_date = fields.Datetime('From Date')
    to_date = fields.Datetime('To Date')

    nhcl_store_id = fields.Many2many(
        'nhcl.ho.store.master',
        string='Company',
        default=lambda self: self._default_stores()
    )

    # audit type field – depends on stores selected
    audit_type_id = fields.Many2one(
        'nhcl.audit.plan',  # create this model or use existing one
        string='Audit Type')

    nhcl_pos_audit_ids = fields.One2many(
        'nhcl.pos.audit.report.line',
        'nhcl_pos_audit_id',
        string='Audit Lines'
    )
    company_domain = fields.Char(string="Company domain",compute="compute_company_domain", store=True)

    @api.depends('nhcl_store_id')
    def compute_company_domain(self):
        domain = []
        company_list=[]
        if self.nhcl_store_id:
            for company in self.nhcl_store_id:
                company_list.append(company.nhcl_store_name.company_id.name)
            domain.append(('store_name','in',company_list))
            self.company_domain = domain
        else:
            self.company_domain = domain


    @api.onchange('nhcl_store_id')
    def _onchange_store_id(self):
        """Fetch plan names from API when store(s) selected"""
        if not self.nhcl_store_id:
            return
        existing_records = self.env['nhcl.audit.plan'].search([])
        if existing_records:
            existing_records.unlink()
        for store in self.nhcl_store_id:
            # Fetch store details
            ho_ip = store.nhcl_terminal_ip
            ho_port = store.nhcl_port_no
            ho_api_key = store.nhcl_api_key
            store_audit_type_search_url = f"http://{ho_ip}:{ho_port}/api/stock.inventory/search"
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}

            # Fetch the POS order and POS order line data for the store
            store_audit_type_data = requests.get(store_audit_type_search_url, headers=headers_source).json()
            store_audit_type_data_list = store_audit_type_data.get("data", [])
            audit_plan_values = []
            for  data in store_audit_type_data_list:
                # name = store_audit_type_data_list[0]['name']
                # plan_name = store_audit_type_data_list[0]['plan_name']
                # company_id = store_audit_type_data_list[0]['company_id']
                company = data.get('company_id', [{}])
                store_name = company[0].get('name') if company else False
                audit_plan_values.append({
                    'name': data.get('plan_name'),
                    'plan_ref': data.get('name'),
                    'store_name': store_name,
                })
                # print("list data",store_audit_type_data_list)
            if audit_plan_values:
                self.env['nhcl.audit.plan'].create(audit_plan_values)

                # print("list data",name)
                # print("list data",plan_name)
                # print("list data",company_id)


    # dummy button for processing
    def get_pos_audit_report(self):
        if not self.nhcl_store_id:
            return

        # Remove old lines
        self.nhcl_pos_audit_ids.unlink()

        audit_lines = []
        total_created = 0
        user_tz = self.env.user.tz or pytz.utc
        local = pytz.timezone(user_tz)

        for store in self.nhcl_store_id:
            ho_ip = store.nhcl_terminal_ip
            ho_port = store.nhcl_port_no
            ho_api_key = store.nhcl_api_key
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}


            store_audit_search_url = f"http://{ho_ip}:{ho_port}/api/stock.inventory/search"

            try:
                response = requests.get(store_audit_search_url, headers=headers_source, timeout=30)
                if response.status_code != 200:
                    _logger.warning("Failed to fetch inventory from store %s: %s", store.nhcl_store_name, response.text)
                    continue

                store_audit_data_list = response.json().get("data", [])
                _logger.info(f"Fetched {len(store_audit_data_list)} inventories from {store.nhcl_store_name}")

                # Filter by date range (if provided)
                if self.from_date and self.to_date:
                    filtered_audit_data_list = []
                    from_date_local = datetime.strftime(
                        pytz.utc.localize(
                            datetime.strptime(str(self.from_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
                        "%Y-%m-%d %H:%M:%S")
                    to_date_local = datetime.strftime(
                        pytz.utc.localize(
                            datetime.strptime(str(self.to_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
                        "%Y-%m-%d %H:%M:%S")

                    for inv in store_audit_data_list:
                        from_date_range = inv.get('from_date_range')
                        to_date_range = inv.get('to_date_range')

                        if not (from_date_range and to_date_range):
                            continue

                        try:
                            audit_from_date = datetime.strptime(from_date_range, "%Y-%m-%dT%H:%M:%S").strftime(
                                                        "%Y-%m-%d %H:%M:%S")
                            audit_to_date = datetime.strptime(to_date_range, "%Y-%m-%dT%H:%M:%S").strftime(
                                                        "%Y-%m-%d %H:%M:%S")
                            from_date_range_local = datetime.strftime(
                                                            pytz.utc.localize(
                                                                datetime.strptime(str(audit_from_date),
                                                                                  DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
                                                            "%Y-%m-%d %H:%M:%S")
                            to_date_range_local = datetime.strftime(
                                                            pytz.utc.localize(
                                                                datetime.strptime(str(audit_to_date),
                                                                                  DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
                                                            "%Y-%m-%d %H:%M:%S")
                            print("######",from_date_range_local)
                            print("@@@@@@@",to_date_range_local)
                            if (from_date_range_local >= from_date_local and to_date_range_local <= to_date_local):
                                filtered_audit_data_list.append(inv)
                        except Exception as e:
                            _logger.error(f"Date conversion error: {e}")
                            continue

                    inventories_to_process = filtered_audit_data_list
                    _logger.info(f"{len(inventories_to_process)} inventories match the filter range.")
                else:
                    inventories_to_process = store_audit_data_list
                # print("Audit data",inventories_to_process)

                #Process inventories
                for inv in inventories_to_process:
                    company = inv.get('company_id', [{}])
                    company_name = company[0].get('name') if company else False
                    line_ids = [line['id'] for line in inv.get('inventory_line_ids', [])]
                    print('line_ids',line_ids)
                    if not line_ids:
                        continue
                    for line_id in line_ids:
                        domain = [('id', '=', line_id)]
                        line_search_url = f"http://{ho_ip}:{ho_port}/api/stock.inventory.line/search?domain={domain}"
                        line_response = requests.get(line_search_url, headers=headers_source)
                        if line_response.status_code != 200:
                            _logger.warning("Failed to fetch inventory lines: %s", line_response.text)
                            continue

                        line_datas = line_response.json().get("data", [])
                        for line_data in line_datas:
                            lot = line_data.get('prod_lot_id', [{}])
                            lot_number = lot[0].get('name') if lot else False
                            if not lot_number:
                                continue
                            print("lot_number",lot_number)
                            lot_rec = self.env['stock.lot'].sudo().search([
                                ('name', '=', lot_number),
                                ('company_id.name', '=', company_name)
                            ], limit=1)
                            print("serial_lot",lot_rec)
                            if not lot_rec:
                                continue

                            # Prepare data for One2many line
                            data = {
                                'division_name': lot_rec.family.name or '',
                                'department': lot_rec.class_level_id.name or '',
                                'section': lot_rec.category.name or '',
                                'barcode': lot_rec.name,
                                'item_name': lot_rec.name,
                                'items_name': lot_rec.product_id.name,
                                'article_name': lot_rec.product_id.name,
                                'mrp_price': lot_rec.mr_price or 0.0,
                                'rsp_price': lot_rec.rs_price or 0.0,
                                'book_qty': line_data.get('theoretical_qty', 0),
                                'phy_qty': line_data.get('product_qty', 0),
                                'difference_qty': line_data.get('difference_qty', 0),
                                'book_rsp_price': lot_rec.rs_price or 0.0,
                                'phy_rsp_price': lot_rec.rs_price or 0.0,
                                'difference_rsp_price': 0.0,
                                'cp_value': lot_rec.cost_price or 0.0,
                                'book_cp_value': lot_rec.cost_price or 0.0,
                                'phy_cp_value': lot_rec.cost_price or 0.0,
                                'difference_cp_value': 0.0,
                            }

                            # Append one by one
                            audit_lines.append((0, 0, data))
                            total_created += 1

            except requests.exceptions.RequestException as e:
                _logger.error(f"Network error for store {store.nhcl_store_name}: {str(e)}")
                continue
        # print("append_data",audit_lines)
        # Assign all lines to One2many field
        self.sudo().nhcl_pos_audit_ids = audit_lines
        _logger.info(f"Total audit lines created: {total_created}")

    # def get_pos_audit_report(self):
    #     if not self.nhcl_store_id:
    #         return
    #
    #     # Remove old lines
    #     self.nhcl_pos_audit_ids.unlink()
    #
    #     total_created = 0
    #
    #     for store in self.nhcl_store_id:
    #         ho_ip = store.nhcl_terminal_ip
    #         ho_port = store.nhcl_port_no
    #         ho_api_key = store.nhcl_api_key
    #         headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
    #         user_tz = self.env.user.tz or pytz.utc
    #         local = pytz.timezone(user_tz)
    #
    #         # Fetch ALL inventory data from store (without filtering)
    #         store_audit_search_url = f"http://{ho_ip}:{ho_port}/api/stock.inventory/search"
    #         try:
    #             # Fetch all records first - ALWAYS fetch all records from store
    #             response = requests.get(store_audit_search_url, headers=headers_source, timeout=30)
    #             if response.status_code != 200:
    #                 _logger.warning("Failed to fetch inventory from store %s: %s", response.text)
    #                 continue
    #
    #             store_audit_data_list = response.json().get("data", [])
    #             print(store_audit_data_list)
    #             _logger.info(f"Found {len(store_audit_data_list)} inventories in store {store.nhcl_store_name}")
    #
    #             # Check if user provided from_date and to_date
    #             if self.from_date and self.to_date:
    #                 # USER PROVIDED DATES: Filter inventories locally based on date range
    #                 filtered_audit_data_list = []
    #
    #                 # Convert filter dates to local timezone
    #                 from_date_local = datetime.strftime(
    #                     pytz.utc.localize(
    #                         datetime.strptime(str(self.from_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
    #                     "%Y-%m-%d %H:%M:%S")
    #                 to_date_local = datetime.strftime(
    #                     pytz.utc.localize(
    #                         datetime.strptime(str(self.to_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(
    #                         local),
    #                     "%Y-%m-%d %H:%M:%S")
    #
    #                 _logger.info(f"Date filter applied: from {from_date_local} to {to_date_local}")
    #
    #                 for inv in store_audit_data_list:
    #                     print("****",inv)
    #                     # Get date range from inventory record
    #                     from_date_range = inv.get('from_date_range')
    #                     to_date_range = inv.get('to_date_range')
    #
    #                     print(from_date_local)
    #                     print(to_date_local)
    #                     audit_from_date =datetime.strptime(from_date_range, "%Y-%m-%dT%H:%M:%S").strftime(
    #                         "%Y-%m-%d %H:%M:%S")
    #                     audit_to_date = datetime.strptime(to_date_range, "%Y-%m-%dT%H:%M:%S").strftime(
    #                         "%Y-%m-%d %H:%M:%S")
    #                     # print(audit_from_date)
    #                     # Check if dates exist and fall within the filter range
    #                     if from_date_range and to_date_range:
    #                         # Convert inventory dates to local timezone for comparison
    #                         try:
    #                             from_date_range_local = datetime.strftime(
    #                                 pytz.utc.localize(
    #                                     datetime.strptime(str(audit_from_date),
    #                                                       DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
    #                                 "%Y-%m-%d %H:%M:%S")
    #                             to_date_range_local = datetime.strftime(
    #                                 pytz.utc.localize(
    #                                     datetime.strptime(str(audit_to_date),
    #                                                       DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
    #                                 "%Y-%m-%d %H:%M:%S")
    #                             print("#####",from_date_range_local)
    #                             print("#####", from_date_local)
    #                             print("$$$$$",to_date_range_local)
    #                             print("$$$$$", to_date_local)
    #                             # Check if inventory date range falls within filter range
    #                             if (from_date_range_local >= from_date_local and to_date_range_local <= to_date_local):
    #                                 filtered_audit_data_list.append(inv)
    #                                 print("data",filtered_audit_data_list)
    #                                 _logger.info(
    #                                     f"Inventory {inv.get('name')} matches date range: {from_date_range} to {to_date_range}")
    #
    #                         except Exception as e:
    #                             _logger.error(f"Error converting inventory dates: {str(e)}")
    #                             continue
    #
    #                 _logger.info(
    #                     f"After date filtering: {len(filtered_audit_data_list)} inventories match the date range")
    #                 inventories_to_process = filtered_audit_data_list
    #                 print("@@@@", inventories_to_process)
    #             else:
    #                 # USER DID NOT PROVIDE DATES: Use all records (normal flow)
    #                 _logger.info("No date filter provided, processing ALL inventories")
    #                 inventories_to_process = store_audit_data_list
    #
    #             # Process the inventories (either filtered or all)
    #             for inv in inventories_to_process:
    #                 company = inv.get('company_id', [{}])
    #                 company_name = company[0].get('name') if company else False
    #
    #                 line_ids = [line['id'] for line in inv.get('inventory_line_ids', [])]
    #                 _logger.info(f"Processing inventory with {len(line_ids)} lines")
    #
    #                 if not line_ids:
    #                     continue
    #
    #                 # Bulk fetch inventory lines from store
    #                 line_search_url = f"http://{ho_ip}:{ho_port}/api/stock.inventory.line/search"
    #                 payload = {
    #                     "domain": [["id", "in", line_ids]],
    #                     "fields": ["id", "prod_lot_id", "product_id", 'theoretical_qty', 'product_qty',
    #                                'difference_qty']
    #                 }
    #
    #                 line_response = requests.get(line_search_url, json=payload, headers=headers_source)
    #                 if line_response.status_code != 200:
    #                     _logger.warning("Failed to fetch inventory lines: %s", line_response.text)
    #                     continue
    #
    #                 line_datas = line_response.json().get("data", [])
    #                 _logger.info(f"Retrieved {len(line_datas)} line details")
    #
    #                 # Process each line data and search in stock.lot
    #                 for line_data in line_datas:
    #                     # Extract lot information
    #                     lot = line_data.get('prod_lot_id', [{}])
    #                     lot_number = lot[0].get('name') if lot else False
    #
    #                     if not lot_number:
    #                         _logger.warning(f"No lot number found for line ID: {line_data.get('id')}")
    #                         continue
    #
    #                     # Search for this lot in HO database (stock.lot)
    #                     lot_rec = self.env['stock.lot'].sudo().search([
    #                         ('name', '=', lot_number),
    #                         ('company_id.name', '=', company_name)
    #                     ],limit=1)
    #
    #                     if not lot_rec:
    #                         _logger.warning(f"Lot {lot_number} not found in HO database for company {company_name}")
    #                         continue
    #
    #                     # Calculate price differences
    #                     book_rsp_price = lot_rec.rs_price or 0.0
    #                     phy_rsp_price = lot_rec.rs_price or 0.0
    #                     book_cp_value = lot_rec.cost_price or 0.0
    #                     phy_cp_value = lot_rec.cost_price or 0.0
    #
    #                     # Calculate differences
    #                     diff_rsp = phy_rsp_price - book_rsp_price
    #                     diff_cp_value = phy_cp_value - book_cp_value
    #
    #                     # Create audit line with quantity data
    #                     vals = {
    #                         'nhcl_pos_audit_id': self.id,
    #                         'division_name': lot_rec.family.name or '',
    #                         'department': lot_rec.class_level_id.name or '',
    #                         'section': lot_rec.category.name or '',
    #                         'barcode': lot_rec.name,
    #                         'item_name': lot_rec.name,
    #                         'items_name': lot_rec.product_id.name,
    #                         'article_name': lot_rec.product_id.name,
    #                         'mrp_price': lot_rec.mr_price or 0.0,
    #                         'rsp_price': lot_rec.rs_price or 0.0,
    #                         'book_qty': line_data.get('theoretical_qty', 0),
    #                         'phy_qty': line_data.get('product_qty', 0),
    #                         'difference_qty': line_data.get('difference_qty', 0),
    #                         'book_rsp_price': book_rsp_price,
    #                         'phy_rsp_price': phy_rsp_price,
    #                         'difference_rsp_price': diff_rsp,
    #                         'cp_value': lot_rec.cost_price or 0.0,
    #                         'book_cp_value': book_cp_value,
    #                         'phy_cp_value': phy_cp_value,
    #                         'difference_cp_value': diff_cp_value,
    #                     }
    #
    #                     try:
    #                         created_line = self.env['nhcl.pos.audit.report.line'].sudo().create(vals)
    #                         total_created += 1
    #                         _logger.info(f"Created audit line for lot {lot_number}: "
    #                                      f"Theoretical={line_data.get('theoretical_qty')}, "
    #                                      f"Counted={line_data.get('product_qty')}, "
    #                                      f"Difference={line_data.get('difference_qty')}")
    #
    #                     except Exception as e:
    #                         _logger.error(f"Error creating audit line for lot {lot_number}: {str(e)}")
    #                         _logger.error(f"Problematic vals: {vals}")
    #
    #         except requests.exceptions.RequestException as e:
    #             _logger.error(f"Network error for store {store.nhcl_store_name}: {str(e)}")
    #             continue
    #
    #     _logger.info(f"Total audit lines created: {total_created}")






class NhclPosAuditReportLine(models.Model):
    _name = 'nhcl.pos.audit.report.line'
    _description = 'POS Audit Report Lines'

    nhcl_pos_audit_id = fields.Many2one('nhcl.pos.audit.report', string='Report Ref')
    division_name = fields.Char(string='Division Name')
    section = fields.Char(string='Section')
    department = fields.Char(string='Department')
    barcode = fields.Char(string='Barcode')
    item_name = fields.Char(string="ItemId")
    items_name = fields.Char(string="ItemName")
    article_name = fields.Char(string="ArticleName")
    mrp_price = fields.Float(string="MRP")
    rsp_price =fields.Float(string="RSP")
    book_qty =fields.Float(string="Book Qty")
    phy_qty =fields.Float(string="Physical Qty")
    difference_qty =fields.Float(string="Difference Qty")
    book_rsp_price = fields.Float(string="Book RSP")
    phy_rsp_price = fields.Float(string="Physical RSP")
    difference_rsp_price = fields.Float(string="Diff RSP")
    cp_value= fields.Float(string="CP Value")
    book_cp_value = fields.Float(string="Book CP Value")
    phy_cp_value = fields.Float(string="Phy CP Value")
    difference_cp_value = fields.Float(string="Diff CP Value")




class NhclAuditPlan(models.Model):
    _name = 'nhcl.audit.plan'
    _description = 'Audit Plan'

    name = fields.Char(string="Plan Name", required=True)
    plan_ref = fields.Char(string="Plan Reference")
    store_name = fields.Char( string='Store')
    store_id = fields.Many2one('res.country', string='Store')


