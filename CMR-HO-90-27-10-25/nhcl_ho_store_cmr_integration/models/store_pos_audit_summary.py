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

class NhclStorePosAuditSummary(models.Model):
    _name = 'nhcl.store.pos.audit.summary'
    _description = 'Store POS Audit Summary'

    def _default_stores(self):
        """Default stores except HO"""
        ho_store_id = self.env['nhcl.ho.store.master'].search(
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

    nhcl_store_pos_audit_summary_ids = fields.One2many(
        'nhcl.store.pos.audit.summary.line',
        'nhcl_store_pos_audit_summary_id',
        string='Audit Summary Lines'
    )
    negative_stock_line_ids = fields.One2many(
        'nhcl.negative.stock.line',
        'audit_summary_id',
        string='Negative Stock Lines'
    )

    company_domain = fields.Char(string="Company domain", compute="compute_company_domain", store=True)

    @api.depends('nhcl_store_id')
    def compute_company_domain(self):
        domain = []
        company_list = []
        if self.nhcl_store_id:
            for company in self.nhcl_store_id:
                company_list.append(company.nhcl_store_name.company_id.name)
            domain.append(('store_name', 'in', company_list))
            self.company_domain = domain
        else:
            domain.append(('id', '=', 0))
            self.company_domain = domain

    def action_to_reset(self):
        self.write({
            'nhcl_store_id': False,
            'audit_type_id': False,
            'from_date': False,
            'to_date': False
        })
        self.nhcl_store_pos_audit_summary_ids.unlink()
        self.negative_stock_line_ids.unlink()

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
            domain = [('state', '=', 'done')]
            store_audit_type_search_url = f"http://{ho_ip}:{ho_port}/api/stock.inventory/search?domain={domain}"
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}

            # Fetch the POS order and POS order line data for the store
            store_audit_type_data = requests.get(store_audit_type_search_url, headers=headers_source).json()
            store_audit_type_data_list = store_audit_type_data.get("data", [])
            audit_plan_values = []
            for data in store_audit_type_data_list:
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


    def get_negative_stock_excel(self):
        """Generate Excel for negative stock records"""
        if not self.negative_stock_line_ids:
            raise UserError('No negative stock records found.')

        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})
        negative_format = workbook.add_format({'font_color': 'red'})

        # Write data headers for negative stock
        headers = ['Family', 'Store Name', 'Book Qty', 'Phy Qty', 'Diff Qty', 'Book RSP', 'Phy RSP', 'Diff RSP',
                   'Book CP Value', 'Phy CP Value', 'Diff CP Value']

        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows for negative stock
        for row_num, line in enumerate(self.negative_stock_line_ids, start=1):
            worksheet.write(row_num, 0, line.division_name)
            worksheet.write(row_num, 1, line.store_name)
            worksheet.write(row_num, 2, line.book_qty)
            worksheet.write(row_num, 3, line.phy_qty)
            worksheet.write(row_num, 4, line.difference_qty, negative_format)  # Highlight negative
            worksheet.write(row_num, 5, line.book_rsp_price)
            worksheet.write(row_num, 6, line.phy_rsp_price)
            worksheet.write(row_num, 7, line.difference_rsp_price)
            worksheet.write(row_num, 8, line.book_cp_price)
            worksheet.write(row_num, 9, line.phy_cp_price)
            worksheet.write(row_num, 10, line.difference_cp_price)
            # worksheet.write(row_num, 11, line.import_date.strftime('%Y-%m-%d %H:%M:%S') if line.import_date else '')

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
            'name': f'Negative_Stock_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Negative_Stock_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Family', 'Book Qty', 'Phy Qty', 'Diff Qty', 'Book RSP', 'Phy RSP', 'Diff RSP',
                 'Book CP Value','Phy CP Value', 'Diff CP Value',"Sales"
                   ]
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.nhcl_store_pos_audit_summary_ids, start=1):
            worksheet.write(row_num, 0, line.division_name)
            worksheet.write(row_num, 1, line.book_qty)
            worksheet.write(row_num, 2, line.phy_qty)
            worksheet.write(row_num, 3, line.difference_qty)
            worksheet.write(row_num, 4, line.book_rsp_price)
            worksheet.write(row_num, 5, line.phy_rsp_price)
            worksheet.write(row_num, 6, line.difference_rsp_price)
            worksheet.write(row_num, 7, line.difference_book_cp_price)
            worksheet.write(row_num, 8, line.difference_phy_cp_price)
            worksheet.write(row_num, 9, line.difference_cp_price)
            worksheet.write(row_num, 10, line.sale_total)

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
            'name': f'Store_POS_Audit_Based_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Store_POS_Audit_Based_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    def get_store_pos_audit_summary(self):
        """Method to generate store POS audit summary grouped by family and store"""
        if not self.nhcl_store_id:
            raise ValidationError('Please Select the Company/Store.')

        # Remove old lines
        self.nhcl_store_pos_audit_summary_ids.unlink()

        summary_lines = []
        total_created = 0

        # Dictionary to store family-wise aggregates with store
        family_aggregates = {}

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
                    elif audit_plan_names and not self.from_date and not self.to_date:
                        if audit_plan_name in audit_plan_names:
                            filtered_audit_data_list.append(inv)
                    elif not audit_plan_names and self.from_date and self.to_date:
                        if self._is_in_date_range(inv):
                            filtered_audit_data_list.append(inv)
                    elif audit_plan_names and self.from_date and self.to_date:
                        if audit_plan_name in audit_plan_names and self._is_in_date_range(inv):
                            filtered_audit_data_list.append(inv)

                _logger.info(f"{len(filtered_audit_data_list)} inventories match the filter range.")

                # Process inventories
                for inv in filtered_audit_data_list:
                    company = inv.get('company_id', [{}])
                    company_name = company[0].get('name') if company else False
                    line_ids = [line['id'] for line in inv.get('inventory_line_ids', [])]

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

                            lot_rec = self.env['stock.lot'].sudo().search([
                                ('name', '=', lot_number),
                                ('company_id.name', '=', company_name)
                            ], limit=1)
                            print("lot_records",lot_rec)
                            if not lot_rec:
                                _logger.warning("Not found this lot/serial Number: %s", lot_number)
                                continue

                            # Get family name and store as key for grouping
                            family_name = lot_rec.product_id.categ_id.parent_id.parent_id.parent_id.name or ''
                            store_name = lot_rec.company_id.name or ''

                            # Create unique key for family + store combination
                            group_key = f"{family_name}_{store_name}"

                            # Get quantities
                            theoretical_qty = line_data.get('theoretical_qty', 0)
                            product_qty = line_data.get('qty_done', 0)
                            sale_price = line_data.get('sale_price', 0)
                            difference_qty = line_data.get('difference_qty', 0)
                            rs_price = lot_rec.rs_price or 0.0
                            cp_value = lot_rec.cost_price or 0.0

                            # Initialize family-store combination in aggregates if not exists
                            if group_key not in family_aggregates:
                                family_aggregates[group_key] = {
                                    'division_name': lot_rec.product_id.categ_id.parent_id.parent_id.parent_id.name or '',
                                    'store_name': store_name,
                                    'book_qty': 0.0,
                                    'phy_qty': 0.0,
                                    'difference_qty': 0.0,
                                    'book_rsp_price': lot_rec.rs_price or 0.0,
                                    'phy_rsp_price': lot_rec.rs_price or 0.0,
                                    'difference_rsp_price': 0.0,
                                    'difference_book_cp_price':0.0,
                                    'difference_phy_cp_price':0.0,
                                    'difference_cp_price' : 0.0,
                                    'sale_total':0.0,
                                }
                            print("Group",family_aggregates)
                            # Sum up quantities for the family-store combination
                            family_aggregates[group_key]['book_qty'] += theoretical_qty
                            family_aggregates[group_key]['phy_qty'] += product_qty
                            family_aggregates[group_key]['sale_total'] += sale_price

                            family_aggregates[group_key]['book_rsp_price'] += rs_price
                            family_aggregates[group_key]['phy_rsp_price'] += rs_price
                            family_aggregates[group_key]['difference_book_cp_price'] += cp_value
                            family_aggregates[group_key]['difference_phy_cp_price'] += cp_value
                            # family_aggregates[group_key]['difference_qty'] += difference_qty
                            print("Sum Data", family_aggregates)

            except requests.exceptions.RequestException as e:
                _logger.error(f"Network error for store {store.nhcl_store_name}: {str(e)}")
                continue

        # Convert family aggregates to summary lines and calculate differences
        for group_key, aggregate_data in family_aggregates.items():
            aggregate_data['difference_qty'] = aggregate_data['phy_qty'] - aggregate_data['book_qty']
            # Calculate RSP price difference
            aggregate_data['difference_rsp_price'] = aggregate_data['phy_rsp_price'] - aggregate_data['book_rsp_price']
            aggregate_data['difference_cp_price'] = aggregate_data['difference_phy_cp_price'] - aggregate_data['difference_book_cp_price']

            summary_lines.append((0, 0, aggregate_data))
            total_created += 1

        # Assign all lines to One2many field
        self.sudo().nhcl_store_pos_audit_summary_ids = summary_lines
        _logger.info(f"Total audit summary lines created: {total_created} (grouped by family and store)")

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

    def action_import_negative_stock(self):
        """Import negative stock records from audit summary lines"""
        if not self.nhcl_store_pos_audit_summary_ids:
            raise UserError('No audit summary lines found. Please generate the audit summary first.')

        # Remove existing negative stock lines
        self.negative_stock_line_ids.unlink()

        negative_lines = []
        imported_count = 0

        # Find lines with negative difference quantity
        for summary_line in self.nhcl_store_pos_audit_summary_ids:
            if summary_line.difference_qty < 0:  # Negative stock condition
                negative_line_data = {
                    'audit_summary_id': self.id,
                    'division_name': summary_line.division_name or '',
                    'store_name': summary_line.store_name or '',
                    'book_qty': summary_line.book_qty,
                    'phy_qty': summary_line.phy_qty,
                    'difference_qty': summary_line.difference_qty,
                    'book_rsp_price': summary_line.book_rsp_price,
                    'phy_rsp_price': summary_line.phy_rsp_price,
                    'difference_rsp_price': summary_line.difference_rsp_price,
                    'book_cp_price': summary_line.difference_book_cp_price,
                    'phy_cp_price': summary_line.difference_phy_cp_price,
                    'difference_cp_price': summary_line.difference_cp_price,
                    'import_date': fields.Datetime.now(),
                }
                negative_lines.append((0, 0, negative_line_data))
                imported_count += 1

        if not negative_lines:
            raise UserError('No negative stock records found in the audit summary.')

        # Create negative stock records
        self.sudo().negative_stock_line_ids = negative_lines


class NhclStorePosAuditSummaryLine(models.Model):
    _name = 'nhcl.store.pos.audit.summary.line'
    _description = 'Store POS Audit Summary Lines'

    nhcl_store_pos_audit_summary_id = fields.Many2one('nhcl.store.pos.audit.summary', string='Summary Ref')
    division_name = fields.Char(string='Family')
    store_name = fields.Char(string='Store Name')
    book_qty = fields.Float(string="Book Qty")
    phy_qty = fields.Float(string="Physical Qty")
    difference_qty = fields.Float(string="Difference Qty")
    book_rsp_price = fields.Float(string="Book RSP")
    phy_rsp_price = fields.Float(string="Physical RSP")
    difference_rsp_price = fields.Float(string="Diff RSP")
    difference_book_cp_price = fields.Float(string="Book CP value")
    difference_phy_cp_price = fields.Float(string="Phy CP value")
    difference_cp_price = fields.Float(string="Diff CP value")
    sale_total = fields.Float(string="Sales")

class NhclNegativeStockLine(models.Model):
    _name = 'nhcl.negative.stock.line'
    _description = 'Negative Stock Lines'
    _order = 'difference_qty asc'

    audit_summary_id = fields.Many2one('nhcl.store.pos.audit.summary', string='Audit Summary Reference')
    division_name = fields.Char(string='Family')
    store_name = fields.Char(string='Store Name')
    book_qty = fields.Float(string="Book Qty")
    phy_qty = fields.Float(string="Physical Qty")
    difference_qty = fields.Float(string="Difference Qty")
    book_rsp_price = fields.Float(string="Book RSP")
    phy_rsp_price = fields.Float(string="Physical RSP")
    difference_rsp_price = fields.Float(string="Diff RSP")
    book_cp_price = fields.Float(string="Book CP value")
    phy_cp_price = fields.Float(string="Phy CP value")
    difference_cp_price = fields.Float(string="Diff CP value")
    import_date = fields.Datetime(string='Import Date')
    # sale_total = fields.Float(string="Sales")