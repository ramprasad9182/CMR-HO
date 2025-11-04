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
        'nhcl.audit.plan',
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
            self.get_store_audit_plans()
        else:
            domain.append(('id', '=', 0))
            self.company_domain = domain
            self.get_store_audit_plans()


    # @api.onchange('nhcl_store_id')
    def get_store_audit_plans(self):
        """Fetch plan names from API when store(s) selected"""

        AuditPlan = self.env['nhcl.audit.plan']
        existing_records = AuditPlan.search([])

        # Collect existing plan references to avoid duplicates
        existing_refs = set(existing_records.mapped('name'))

        for store in self.nhcl_store_id:
            # Fetch store details
            ho_ip = store.nhcl_terminal_ip
            ho_port = store.nhcl_port_no
            ho_api_key = store.nhcl_api_key
            domain = [('state', '=', 'done')]
            store_audit_type_search_url = f"http://{ho_ip}:{ho_port}/api/stock.inventory/search?domain={domain}"
            headers_source = {
                'api-key': f"{ho_api_key}",
                'Content-Type': 'application/json'
            }

            # Fetch data from API
            response = requests.get(store_audit_type_search_url, headers=headers_source)
            if response.status_code != 200:
                _logger.warning("Failed to fetch data from %s: %s", store_audit_type_search_url, response.text)
                continue

            store_audit_type_data = response.json()
            store_audit_type_data_list = store_audit_type_data.get("data", [])

            audit_plan_values = []
            for data in store_audit_type_data_list:
                plan_ref = data.get('name')
                plan_name = data.get('plan_name')

                # Skip if already exists
                if plan_name in existing_refs:
                    continue

                company = data.get('company_id', [{}])
                store_name = company[0].get('name') if company else False

                audit_plan_values.append({
                    'name': plan_name,
                    'plan_ref': plan_ref,
                    'store_name': store_name,
                })
                existing_refs.add(plan_name)  # Update to avoid duplicates in next loops

            # Create only new plans
            if audit_plan_values:
                AuditPlan.create(audit_plan_values)
        # if not self.nhcl_store_id:
        #     return
        # existing_records = self.env['nhcl.audit.plan'].search([])
        # if existing_records:
        #     existing_records.unlink()

        # for store in self.nhcl_store_id:
        #     # Fetch store details
        #     ho_ip = store.nhcl_terminal_ip
        #     ho_port = store.nhcl_port_no
        #     ho_api_key = store.nhcl_api_key
        #     domain = [('state', '=', 'done')]
        #     store_audit_type_search_url = f"http://{ho_ip}:{ho_port}/api/stock.inventory/search?domain={domain}"
        #     headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
        #
        #     # Fetch the POS order and POS order line data for the store
        #     store_audit_type_data = requests.get(store_audit_type_search_url, headers=headers_source).json()
        #     store_audit_type_data_list = store_audit_type_data.get("data", [])
        #     audit_plan_values = []
        #     for  data in store_audit_type_data_list:
        #         # name = store_audit_type_data_list[0]['name']
        #         # plan_name = store_audit_type_data_list[0]['plan_name']
        #         # company_id = store_audit_type_data_list[0]['company_id']
        #         company = data.get('company_id', [{}])
        #         store_name = company[0].get('name') if company else False
        #         audit_plan_values.append({
        #             'name': data.get('plan_name'),
        #             'plan_ref': data.get('name'),
        #             'store_name': store_name,
        #         })
        #         # print("list data",store_audit_type_data_list)
        #     if audit_plan_values:
        #         self.env['nhcl.audit.plan'].create(audit_plan_values)

                # print("list data",name)
                # print("list data",plan_name)
                # print("list data",company_id)

    def _is_in_date_range(self, inventory):
        """Check if inventory falls within the selected date range"""
        user_tz = self.env.user.tz or pytz.utc
        local = pytz.timezone(user_tz)
        if not self.from_date or not self.to_date:
            return True

        from_date_range = inventory.get('from_date_range')
        to_date_range = inventory.get('to_date_range')

        if not (from_date_range and to_date_range):
            return False

        try:
            from_date_local = datetime.strftime(
                pytz.utc.localize(
                    datetime.strptime(str(self.from_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
                "%Y-%m-%d %H:%M:%S")
            to_date_local = datetime.strftime(
                pytz.utc.localize(
                    datetime.strptime(str(self.to_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
                "%Y-%m-%d %H:%M:%S")

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

            # Inventory is included if ANY part of it overlaps with the selected range
            return (from_date_range_local >= from_date_local and to_date_range_local <= to_date_local)

        except Exception as e:
            _logger.error(f"Date conversion error: {e}")
            return False

    def action_to_reset(self):
        self.write({
            'nhcl_store_id': False,
            'from_date': False,
            'to_date': False
        })
        self.nhcl_pos_audit_ids.unlink()

    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Family', 'Category', 'Class', 'Brick', 'Barcode', 'ItemId', 'ItemName', 'ArticleName', 'MRP', 'RSP',
                   'MBQ Range','Categ1', 'Categ2', 'Categ3', 'Categ4', 'Categ5', 'Categ6','ItemDesc1', 'ItemDesc2', 'ItemDesc3', 'ItemDesc4',
                   'ItemDesc5', 'ItemDesc6','Book Qty', 'Phy Qty', 'Diff Qty', 'Book RSP', 'Phy RSP', 'Diff RSP', 'CP Value', 'Book CP Value',
                   'Phy CP Value', 'Diff CP Value',
                   ]
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.nhcl_pos_audit_ids, start=1):
            worksheet.write(row_num, 0, line.division_name)
            worksheet.write(row_num, 1, line.section)
            worksheet.write(row_num, 2, line.department)
            worksheet.write(row_num, 3, line.brick_name)
            worksheet.write(row_num, 4, line.barcode)
            worksheet.write(row_num, 5, line.item_name)
            worksheet.write(row_num, 6, line.items_name)
            worksheet.write(row_num, 7, line.article_name)
            worksheet.write(row_num, 8, line.mrp_price)
            worksheet.write(row_num, 9, line.rsp_price)
            worksheet.write(row_num, 10, line.item_range)
            worksheet.write(row_num, 11, line.item_categ1)
            worksheet.write(row_num, 12, line.item_categ2)
            worksheet.write(row_num, 13, line.item_categ3)
            worksheet.write(row_num, 14, line.item_categ4)
            worksheet.write(row_num, 15, line.item_categ5)
            worksheet.write(row_num, 16, line.item_categ6)
            worksheet.write(row_num, 17, line.item_descrip1)
            worksheet.write(row_num, 18, line.item_descrip2)
            worksheet.write(row_num, 19, line.item_descrip3)
            worksheet.write(row_num, 20, line.item_descrip4)
            worksheet.write(row_num, 21, line.item_descrip5)
            worksheet.write(row_num, 22, line.item_descrip6)
            worksheet.write(row_num, 23, line.book_qty)
            worksheet.write(row_num, 24, line.phy_qty)
            worksheet.write(row_num, 25, line.difference_qty)
            worksheet.write(row_num, 26, line.book_rsp_price)
            worksheet.write(row_num, 27, line.phy_rsp_price)
            worksheet.write(row_num, 28, line.difference_rsp_price)
            worksheet.write(row_num, 29, line.cp_value)
            worksheet.write(row_num, 30, line.book_cp_value)
            worksheet.write(row_num, 31, line.phy_cp_value)
            worksheet.write(row_num, 32, line.difference_cp_value)



            # worksheet.write(row_num, 33, line.store_name)

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
            'name': f'POS_Audit_Based_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'POS_Audit_Based_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    # dummy button for processing
    def get_pos_audit_report(self):
        if not self.nhcl_store_id:
            raise ValidationError('Please Select the Company/Store.')

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

            audit_plan_names = self.audit_type_id.mapped('name') if self.audit_type_id else []
            domain = [('state', '=', 'done')]
            store_audit_search_url = f"http://{ho_ip}:{ho_port}/api/stock.inventory/search?domain={domain}"

            try:
                response = requests.get(store_audit_search_url, headers=headers_source, timeout=30)
                if response.status_code != 200:
                    _logger.warning("Failed to fetch inventory from store %s: %s", store.nhcl_store_name, response.text)
                    continue

                store_audit_data_list = response.json().get("data", [])
                _logger.info(f"Fetched {len(store_audit_data_list)} inventories from {store.nhcl_store_name}")

                filtered_audit_data_list = []
                for inv in store_audit_data_list:
                    audit_plan_name = inv.get('plan_name')
                    if not audit_plan_names and not self.from_date and not self.to_date:
                        filtered_audit_data_list.append(inv)
                        print("No filter", filtered_audit_data_list)
                        _logger.debug(f"Added by Scenario 1: {audit_plan_name}")

                    # Scenario 2: Only audit plan selected
                    elif audit_plan_names and not self.from_date and not self.to_date:
                        if audit_plan_name in audit_plan_names:
                            filtered_audit_data_list.append(inv)
                            print("plan filter", filtered_audit_data_list)
                            _logger.debug(f"Added by Scenario 2: {audit_plan_name}")

                    # Scenario 3: Only date range selected (no audit plan)
                    elif not audit_plan_names and self.from_date and self.to_date:
                        if self._is_in_date_range(inv):
                            filtered_audit_data_list.append(inv)
                            print("date filter", filtered_audit_data_list)
                            _logger.debug(f"Added by Scenario 3: {audit_plan_name}")

                    # Scenario 4: Both audit plan and date range selected
                    elif audit_plan_names and self.from_date and self.to_date:
                        if audit_plan_name in audit_plan_names and self._is_in_date_range(inv):
                            filtered_audit_data_list.append(inv)
                            print("plan and date filter", filtered_audit_data_list)
                            _logger.debug(f"Added by Scenario 4: {audit_plan_name}")

                    # inventories_to_process = filtered_audit_data_list
                    _logger.info(f"{len(filtered_audit_data_list)} inventories match the filter range.")
                # Process inventories
                for inv in filtered_audit_data_list:
                    company = inv.get('company_id', [{}])
                    company_name = company[0].get('name') if company else False
                    line_ids = [line['id'] for line in inv.get('inventory_line_ids', [])]
                    print('line_ids', line_ids)
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
                            print("lot_number", lot_number)
                            lot_rec = self.env['stock.lot'].sudo().search([
                                ('name', '=', lot_number),
                                ('company_id.name', '=', company_name)
                            ], limit=1)
                            print("serial_lot", lot_rec)
                            if not lot_rec:
                                continue
                            # Calculate price differences
                            book_rsp_price = lot_rec.rs_price or 0.0
                            phy_rsp_price = lot_rec.rs_price or 0.0
                            book_cp_value = lot_rec.cost_price or 0.0
                            phy_cp_value = lot_rec.cost_price or 0.0

                            # Calculate differences
                            diff_rsp = phy_rsp_price - book_rsp_price
                            diff_cp_value = phy_cp_value - book_cp_value
                            store_qty = line_data.get('theoretical_qty')
                            store_qty1 = line_data.get('qty_done')
                            store_qty_differnce = store_qty1-store_qty
                            # v = line_data.get('difference_qty')
                            # print("diff1", store_qty_differnce)
                            # print("diff", type(store_qty))
                            # print("diff", store_qty1)
                            # Prepare data for One2many line
                            data = {
                                'division_name': lot_rec.product_id.categ_id.parent_id.parent_id.parent_id.name or '',
                                'department': lot_rec.product_id.categ_id.parent_id.parent_id.name or '',
                                'section': lot_rec.product_id.categ_id.parent_id.name or '',
                                'brick_name': lot_rec.product_id.categ_id.name or '',
                                'barcode': lot_rec.name,
                                'item_name': lot_rec.name,
                                'items_name': lot_rec.product_id.name,
                                'article_name': lot_rec.product_id.name,
                                'mrp_price': lot_rec.mr_price or 0.0,
                                'rsp_price': lot_rec.rs_price or 0.0,
                                'book_qty': line_data.get('theoretical_qty', 0),
                                'phy_qty': line_data.get('qty_done', 0),
                                # 'difference_qty': line_data.get('difference_qty', 0),
                                'difference_qty': store_qty_differnce,
                                'book_rsp_price': lot_rec.rs_price or 0.0,
                                'phy_rsp_price': lot_rec.rs_price or 0.0,
                                'difference_rsp_price': diff_rsp or 0.0,
                                'cp_value': lot_rec.cost_price or 0.0,
                                'book_cp_value': lot_rec.cost_price or 0.0,
                                'phy_cp_value': lot_rec.cost_price or 0.0,
                                'difference_cp_value': diff_cp_value or 0.0,
                                'item_range':lot_rec.description_2.name,
                                'store_name':lot_rec.company_id.name,
                                'item_categ1' : lot_rec.category_1.name,
                                'item_categ2' : lot_rec.category_2.name,
                                'item_categ3' : lot_rec.category_3.name,
                                'item_categ4' : lot_rec.category_4.name,
                                'item_categ5' : lot_rec.category_5.name,
                                'item_categ6' : lot_rec.category_6.name,
                                'item_descrip1' : lot_rec.description_3.name,
                                'item_descrip2' : lot_rec.description_4.name,
                                'item_descrip3' : lot_rec.description_5.name,
                                'item_descrip4' : lot_rec.description_6.name,
                                'item_descrip5' : lot_rec.description_1.name,
                                'item_descrip6' : lot_rec.description_8.name,

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
    #         raise ValidationError('Please Select the Company/Store.')
    #
    #     # Remove old lines
    #     self.nhcl_pos_audit_ids.unlink()
    #
    #     audit_lines = []
    #     total_created = 0
    #     user_tz = self.env.user.tz or pytz.utc
    #     local = pytz.timezone(user_tz)
    #
    #     for store in self.nhcl_store_id:
    #         ho_ip = store.nhcl_terminal_ip
    #         ho_port = store.nhcl_port_no
    #         ho_api_key = store.nhcl_api_key
    #         headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
    #
    #         audit_plan_names = self.audit_type_id.mapped('name') if self.audit_type_id else []
    #         store_audit_search_url = f"http://{ho_ip}:{ho_port}/api/stock.inventory/search"
    #
    #         try:
    #             response = requests.get(store_audit_search_url, headers=headers_source, timeout=30)
    #             if response.status_code != 200:
    #                 _logger.warning("Failed to fetch inventory from store %s: %s", store.nhcl_store_name, response.text)
    #                 continue
    #
    #             store_audit_data_list = response.json().get("data", [])
    #             _logger.info(f"Fetched {len(store_audit_data_list)} inventories from {store.nhcl_store_name}")
    #
    #             # Filter by date range (if provided)
    #             # if self.from_date and self.to_date:
    #             #     filtered_audit_data_list = []
    #             #     from_date_local = datetime.strftime(
    #             #         pytz.utc.localize(
    #             #             datetime.strptime(str(self.from_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
    #             #         "%Y-%m-%d %H:%M:%S")
    #             #     to_date_local = datetime.strftime(
    #             #         pytz.utc.localize(
    #             #             datetime.strptime(str(self.to_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
    #             #         "%Y-%m-%d %H:%M:%S")
    #             filtered_audit_data_list = []
    #             for inv in store_audit_data_list:
    #                 audit_plan_name = inv.get('plan_name')
    #                 if not audit_plan_names and not self.from_date and not self.to_date:
    #                     filtered_audit_data_list.append(inv)
    #                     print("No filter",filtered_audit_data_list)
    #                     _logger.debug(f"Added by Scenario 1: {audit_plan_name}")
    #
    #                 # Scenario 2: Only audit plan selected
    #                 elif audit_plan_names and not self.from_date and not self.to_date:
    #                     if audit_plan_name in audit_plan_names:
    #                         filtered_audit_data_list.append(inv)
    #                         print("plan filter", filtered_audit_data_list)
    #                         _logger.debug(f"Added by Scenario 2: {audit_plan_name}")
    #
    #                 # Scenario 3: Only date range selected (no audit plan)
    #                 elif not audit_plan_names and self.from_date and self.to_date:
    #                     if self._is_in_date_range(inv):
    #                         filtered_audit_data_list.append(inv)
    #                         print("date filter", filtered_audit_data_list)
    #                         _logger.debug(f"Added by Scenario 3: {audit_plan_name}")
    #
    #                 # Scenario 4: Both audit plan and date range selected
    #                 elif audit_plan_names and self.from_date and self.to_date:
    #                     if audit_plan_name in audit_plan_names and self._is_in_date_range(inv):
    #                         filtered_audit_data_list.append(inv)
    #                         print("plan and date filter", filtered_audit_data_list)
    #                         _logger.debug(f"Added by Scenario 4: {audit_plan_name}")
    #                 # from_date_range = inv.get('from_date_range')
    #                 # to_date_range = inv.get('to_date_range')
    #                 #
    #                 # if not (from_date_range and to_date_range):
    #                 #     continue
    #
    #                 # try:
    #                 #     audit_from_date = datetime.strptime(from_date_range, "%Y-%m-%dT%H:%M:%S").strftime(
    #                 #                                 "%Y-%m-%d %H:%M:%S")
    #                 #     audit_to_date = datetime.strptime(to_date_range, "%Y-%m-%dT%H:%M:%S").strftime(
    #                 #                                 "%Y-%m-%d %H:%M:%S")
    #                 #     from_date_range_local = datetime.strftime(
    #                 #                                     pytz.utc.localize(
    #                 #                                         datetime.strptime(str(audit_from_date),
    #                 #                                                           DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
    #                 #                                     "%Y-%m-%d %H:%M:%S")
    #                 #     to_date_range_local = datetime.strftime(
    #                 #                                     pytz.utc.localize(
    #                 #                                         datetime.strptime(str(audit_to_date),
    #                 #                                                           DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
    #                 #                                     "%Y-%m-%d %H:%M:%S")
    #                 #     print("######",from_date_range_local)
    #                 #     print("@@@@@@@",to_date_range_local)
    #                 #     if (from_date_range_local >= from_date_local and to_date_range_local <= to_date_local):
    #                 #         filtered_audit_data_list.append(inv)
    #                 # except Exception as e:
    #                 #     _logger.error(f"Date conversion error: {e}")
    #                 #     continue
    #
    #                 # inventories_to_process = filtered_audit_data_list
    #                 _logger.info(f"{len(filtered_audit_data_list)} inventories match the filter range.")
    #             # else:
    #             #     inventories_to_process = store_audit_data_list
    #             # print("Audit data",inventories_to_process)
    #
    #             #Process inventories
    #             for inv in filtered_audit_data_list:
    #                 company = inv.get('company_id', [{}])
    #                 company_name = company[0].get('name') if company else False
    #                 line_ids = [line['id'] for line in inv.get('inventory_line_ids', [])]
    #                 print('line_ids',line_ids)
    #                 if not line_ids:
    #                     continue
    #                 for line_id in line_ids:
    #                     domain = [('id', '=', line_id)]
    #                     line_search_url = f"http://{ho_ip}:{ho_port}/api/stock.inventory.line/search?domain={domain}"
    #                     line_response = requests.get(line_search_url, headers=headers_source)
    #                     if line_response.status_code != 200:
    #                         _logger.warning("Failed to fetch inventory lines: %s", line_response.text)
    #                         continue
    #
    #                     line_datas = line_response.json().get("data", [])
    #                     for line_data in line_datas:
    #                         lot = line_data.get('prod_lot_id', [{}])
    #                         lot_number = lot[0].get('name') if lot else False
    #                         if not lot_number:
    #                             continue
    #                         print("lot_number",lot_number)
    #                         lot_rec = self.env['stock.lot'].sudo().search([
    #                             ('name', '=', lot_number),
    #                             ('company_id.name', '=', company_name)
    #                         ], limit=1)
    #                         print("serial_lot",lot_rec)
    #                         if not lot_rec:
    #                             continue
    #                         # Calculate price differences
    #                         book_rsp_price = lot_rec.rs_price or 0.0
    #                         phy_rsp_price = lot_rec.rs_price or 0.0
    #                         book_cp_value = lot_rec.cost_price or 0.0
    #                         phy_cp_value = lot_rec.cost_price or 0.0
    #
    #                         # Calculate differences
    #                         diff_rsp = phy_rsp_price - book_rsp_price
    #                         diff_cp_value = phy_cp_value - book_cp_value
    #
    #                         # Prepare data for One2many line
    #                         data = {
    #                             'division_name': lot_rec.family.name or '',
    #                             'department': lot_rec.class_level_id.name or '',
    #                             'section': lot_rec.category.name or '',
    #                             'barcode': lot_rec.name,
    #                             'item_name': lot_rec.name,
    #                             'items_name': lot_rec.product_id.name,
    #                             'article_name': lot_rec.product_id.name,
    #                             'mrp_price': lot_rec.mr_price or 0.0,
    #                             'rsp_price': lot_rec.rs_price or 0.0,
    #                             'book_qty': line_data.get('theoretical_qty', 0),
    #                             'phy_qty': line_data.get('product_qty', 0),
    #                             'difference_qty': line_data.get('difference_qty', 0),
    #                             'book_rsp_price': lot_rec.rs_price or 0.0,
    #                             'phy_rsp_price': lot_rec.rs_price or 0.0,
    #                             'difference_rsp_price': diff_rsp or 0.0,
    #                             'cp_value': lot_rec.cost_price or 0.0,
    #                             'book_cp_value': lot_rec.cost_price or 0.0,
    #                             'phy_cp_value': lot_rec.cost_price or 0.0,
    #                             'difference_cp_value': diff_cp_value or 0.0,
    #                         }
    #
    #                         # Append one by one
    #                         audit_lines.append((0, 0, data))
    #                         total_created += 1
    #
    #         except requests.exceptions.RequestException as e:
    #             _logger.error(f"Network error for store {store.nhcl_store_name}: {str(e)}")
    #             continue
    #     # print("append_data",audit_lines)
    #     # Assign all lines to One2many field
    #     self.sudo().nhcl_pos_audit_ids = audit_lines
    #     _logger.info(f"Total audit lines created: {total_created}")


class NhclPosAuditReportLine(models.Model):
    _name = 'nhcl.pos.audit.report.line'
    _description = 'POS Audit Report Lines'

    nhcl_pos_audit_id = fields.Many2one('nhcl.pos.audit.report', string='Report Ref')
    division_name = fields.Char(string='Family')
    section = fields.Char(string='Category')
    department = fields.Char(string='Class')
    brick_name = fields.Char(string='Brick')
    barcode = fields.Char(string='Barcode')
    item_name = fields.Char(string="ItemId")
    items_name = fields.Char(string="ItemName")
    article_name = fields.Char(string="ArticleName")
    mrp_price = fields.Float(string="MRP")
    rsp_price = fields.Float(string="RSP")
    book_qty = fields.Float(string="Book Qty")
    phy_qty = fields.Float(string="Physical Qty")
    difference_qty = fields.Float(string="Difference Qty")
    book_rsp_price = fields.Float(string="Book RSP")
    phy_rsp_price = fields.Float(string="Physical RSP")
    difference_rsp_price = fields.Float(string="Diff RSP")
    cp_value= fields.Float(string="CP Value")
    book_cp_value = fields.Float(string="Book CP Value")
    phy_cp_value = fields.Float(string="Phy CP Value")
    difference_cp_value = fields.Float(string="Diff CP Value")
    item_categ1 = fields.Char(string="categ1")
    item_categ2 = fields.Char(string="categ2")
    item_categ3 = fields.Char(string="categ3")
    item_categ4 = fields.Char(string="categ4")
    item_categ5 = fields.Char(string="categ5")
    item_categ6 = fields.Char(string="categ6")
    item_descrip1 = fields.Char(string="ItemDesc1")
    item_descrip2 = fields.Char(string="ItemDesc2")
    item_descrip3 = fields.Char(string="ItemDesc3")
    item_descrip4 = fields.Char(string="ItemDesc4")
    item_descrip5 = fields.Char(string="ItemDesc5")
    item_descrip6 = fields.Char(string="ItemDesc6")
    item_range = fields.Char(string="MBQ Range")
    store_name = fields.Char(string="Store Name")




class NhclAuditPlan(models.Model):
    _name = 'nhcl.audit.plan'
    _description = 'Audit Plan'

    name = fields.Char(string="Plan Name", required=True)
    plan_ref = fields.Char(string="Plan Reference")
    store_name = fields.Char( string='Store')
    store_id = fields.Many2one('res.country', string='Store')


