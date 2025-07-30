import base64
import datetime
import io

import requests
import xlsxwriter
from odoo.tools import format_date, DEFAULT_SERVER_DATETIME_FORMAT

from odoo import fields, models, tools, api
from datetime import datetime
import logging

from odoo.tools.safe_eval import pytz

_logger = logging.getLogger(__name__)


class SetuSalesPersonIncentive(models.TransientModel):
    _name = 'sales.person.incentive.report'
    _description = "Sales Person Incentive Report"

    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    ref_company_id = fields.Many2one('res.company', string='Company', domain=lambda self: self._get_company_domain())
    sale_person = fields.Many2one('hr.employee', string='Sale Person')
    sale_person_incentive_ids = fields.One2many('sales.person.incentive.report.line', 'sale_person_incentive_id')
    nhcl_store = fields.Many2one('nhcl.ho.store.master', string='Company', store=True)

    @api.onchange('nhcl_store')
    def _onchange_get_ref_company(self):
        if self.nhcl_store:
            self.ref_company_id = self.nhcl_store.nhcl_store_name.sudo().company_id

    @api.model
    def _get_company_domain(self):
        # Get the companies currently selected in the user's session context (allowed companies)
        allowed_company_ids = self.env.context.get('allowed_company_ids', [])

        # Apply the domain to show only the companies selected in the session
        return [('id', 'in', allowed_company_ids)] if allowed_company_ids else []

    def action_check_sale_person_incentive_report(self):
        self.sale_person_incentive_ids.unlink()
        try:
            for store in self.nhcl_store:
                ho_ip = store.nhcl_terminal_ip
                ho_port = store.nhcl_port_no
                ho_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                from_date = self.from_date
                to_date = self.to_date
                user_tz = self.env.user.tz or pytz.utc
                local = pytz.timezone(user_tz)
                employee_search_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                employee_nhcl_id = self.sale_person.nhcl_id
                employee_domain = [('nhcl_id', '=', employee_nhcl_id)]
                emp_data = f"{employee_search_url}?domain={employee_domain}"
                employee_get_data = requests.get(emp_data, headers=headers_source).json()
                employee_data = employee_get_data.get("data", [])
                employee_id = False
                if employee_data:
                    employee_id = employee_data[0]['id']
                elif self.sale_person:
                    _logger.info(f"No Employee found for '{self.name}' with email. Skipping this record.")
                    continue
                pos_order_line_search_url = f"http://{ho_ip}:{ho_port}/api/pos.order.line/search"
                if self.sale_person:
                    order_line_domain = [('employ_id', '=', employee_id), ('badge_id', '=', employee_data[0]['barcode'])]
                else:
                    order_line_domain = []
                order_line_url = f"{pos_order_line_search_url}?domain={order_line_domain}"
                pos_order_line_data = requests.get(order_line_url, headers=headers_source).json()
                pos_data_line = pos_order_line_data.get("data", [])
                for data in pos_data_line:
                    date_order_str = data.get("create_date")
                    try:
                        date_order = datetime.strptime(date_order_str, "%Y-%m-%dT%H:%M:%S.%f").strftime(
                            "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        date_order = datetime.strptime(date_order_str, "%Y-%m-%dT%H:%M:%S").strftime(
                            "%Y-%m-%d %H:%M:%S")

                    date_order_local = datetime.strftime(
                         pytz.utc.localize(
                            datetime.strptime(str(date_order), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
                        "%Y-%m-%d"
                    )
                    if str(from_date) <= date_order_local <= str(to_date):
                        store_master = self.env['nhcl.ho.store.master'].search([('id', '=', store.id)], limit=1)
                        if store_master:
                            pos_order_search_url = f"http://{ho_ip}:{ho_port}/api/pos.order/search"
                            order_domain = [('id', '=', data.get("order_id")[0]['id'])]
                            order_url = f"{pos_order_search_url}?domain={order_domain}"
                            pos_order_data = requests.get(order_url, headers=headers_source).json()
                            pos_data = pos_order_data.get("data", [])
                            order_date = pos_data[0].get("date_order")
                            pos_order_date = datetime.strptime(order_date, "%Y-%m-%dT%H:%M:%S").strftime(
                                "%Y-%m-%d %H:%M:%S")
                            pos_date = datetime.strftime(
                                pytz.utc.localize(
                                    datetime.strptime(str(pos_order_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(
                                    local),
                                "%Y-%m-%d"
                            )
                            order_date = datetime.strptime(pos_date, "%Y-%m-%d").date()
                            structure_id = self.env['setu.sales.incentive.structure'].search([
                                ('start_date', '<=', order_date),
                                ('end_date', '>=', order_date),
                                ('incentive_state', '=', "confirmed"),
                            ])
                            line_margin = data.get('price_subtotal') - data.get('total_cost')
                            incentive_structure_lines = structure_id.incentive_structure_line_ids.filtered(
                                lambda x: x.calculate_based_on == 'pos_order' and
                                          x.target_value_min <= line_margin <= x.target_value_max
                            )
                            if data.get("price_subtotal_incl") > 0 and incentive_structure_lines:
                                for incentive_line in incentive_structure_lines:
                                    # Match aging_id
                                    if incentive_line.aging_id:
                                        matched = False
                                        for lot_dict in data.get('pack_lot_ids', []):
                                            pack_lot_search_url = f"http://{ho_ip}:{ho_port}/api/pos.pack.operation.lot/search"
                                            pack_lot_domain = [('id', '=', lot_dict.get("id"))]
                                            pack_lot_url = f"{pack_lot_search_url}?domain={pack_lot_domain}"
                                            pack_lot_data = requests.get(pack_lot_url, headers=headers_source).json()
                                            pack_lot = pack_lot_data.get("data", [])
                                            lot = self.env['stock.lot'].sudo().search([('name', '=', pack_lot[0]['lot_name'])],
                                                                                      limit=1)
                                            if lot and lot.description_1.name == incentive_line.aging_id.name:
                                                matched = True
                                                # break
                                        if not matched:
                                            continue

                                    # Match day_ageing_incentive
                                    if incentive_line.day_ageing_incentive and data.get('pack_lot_ids'):
                                        days_matched = False
                                        for lot_dict in data.get('pack_lot_ids', []):
                                            days_pack_lot_search_url = f"http://{ho_ip}:{ho_port}/api/pos.pack.operation.lot/search"
                                            days_pack_lot_domain = [('id', '=', lot_dict.get("id"))]
                                            days_pack_lot_url = f"{days_pack_lot_search_url}?domain={days_pack_lot_domain}"
                                            days_pack_lot_data = requests.get(days_pack_lot_url, headers=headers_source).json()
                                            days_pack_lot = days_pack_lot_data.get("data", [])
                                            days_lot = self.env['stock.lot'].sudo().search([('name', '=', days_pack_lot[0]['lot_name'])],
                                                                                      limit=1)
                                            if not days_lot or not days_lot.create_date:
                                                continue
                                            lot_create_date = days_lot.create_date.date()

                                            day_diff = (order_date - lot_create_date).days
                                            selected_range = incentive_line.day_ageing_incentive


                                            if ((selected_range == '1' and 0 <= day_diff <= 30) or \
                                                    (selected_range == '2' and 30 <= day_diff <= 60) or \
                                                    (selected_range == '3' and 60 <= day_diff <= 90) or \
                                                    (selected_range == '4' and 90 <= day_diff <= 120) or
                                                    (selected_range == '5' and 120 <= day_diff <= 150) or
                                                    (selected_range == '6' and 150 <= day_diff <= 180) or
                                                    (selected_range == '7' and 180 <= day_diff <= 210) or
                                                    (selected_range == '8' and 210 <= day_diff <= 240) or
                                                    (selected_range == '9' and 240 <= day_diff <= 270) or
                                                    (selected_range == '10' and 270 <= day_diff <= 300) or
                                                    (selected_range == '10' and 300 <= day_diff <= 330) or
                                                    (selected_range == '10' and 330 <= day_diff <= 360)):
                                                days_matched = True
                                                break
                                        if not days_matched:
                                            continue

                                    # Calculate incentive
                                    if incentive_line.calculation_method == 'percentage':
                                        value = data.get("price_subtotal_incl") * (incentive_line.incentive_value / 100)
                                    else:
                                        value = incentive_line.incentive_value
                                    hr_employee_id = False
                                    if data.get('employ_id'):
                                        hr_employee_id = self.env['hr.employee'].sudo().search([('name','=',
                                                                                             data.get('employ_id')[0]['name'])])
                                    if self.sale_person:
                                        sale_person = self.sale_person.id
                                    elif hr_employee_id:
                                        sale_person = hr_employee_id.id
                                    else:
                                        sale_person =False
                                    vals = {
                                        'sale_person_id': sale_person,
                                        'ref_company_id': self.ref_company_id.id,
                                        'sale_person_incentive_id': self.id,
                                        'name': data.get("order_id")[0]['name'],
                                        'pos_date': order_date,
                                        'base_value': data.get("price_subtotal_incl"),
                                        'amount': value,
                                        'incentive_rule_name': "{} - {} - {}[{}] - {} - {} - {}[{} - {}]".format(
                                            incentive_line.incentive_structure_id.name,
                                            dict(incentive_line._fields['role'].selection).get(incentive_line.role),
                                            dict(incentive_line._fields['calculate_based_on'].selection).get(
                                                incentive_line.calculate_based_on),
                                            "POS Orders",
                                            dict(incentive_line._fields['target_based_on'].selection).get(
                                                incentive_line.target_based_on),
                                            dict(incentive_line._fields['calculation_method'].selection).get(
                                                incentive_line.calculation_method),
                                            incentive_line.incentive_value,
                                            incentive_line.target_value_min,
                                            incentive_line.target_value_max
                                        )
                                    }
                                    _logger.info("Incentive vals -> %s", vals)
                                    self.sale_person_incentive_ids.create(vals)
                        else:
                            print(f"Store master not found for {store.nhcl_store_name.name}, skipping.")
                    else:
                        print(f"POS line for {store.nhcl_store_name.name} is outside date range.")
        except requests.exceptions.RequestException as e:
            print(f"Failed to retrieve POS orders for store {store.nhcl_store_name.name}: {e}")



    def action_to_reset(self):
        self.sale_person = False
        self.from_date = False
        self.to_date = False
        self.ref_company_id = False
        self.nhcl_store = False
        self.sale_person_incentive_ids.unlink()

    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Session Name', 'POS Date', 'Sales Person', 'Base Value', 'Incentive Amount', 'Company']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.sale_person_incentive_ids, start=1):
            worksheet.write(row_num, 0, line.name)
            worksheet.write(row_num, 1,
                            line.pos_date and format_date(self.env, line.pos_date, date_format='dd-MM-yyyy'))
            worksheet.write(row_num, 2, line.sale_person_id.name)
            worksheet.write(row_num, 3, line.base_value)
            worksheet.write(row_num, 4, line.amount)
            worksheet.write(row_num, 5, line.ref_company_id.name)

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
            'name': f'Sales_Incentive_Detailed_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Sales_Incentive_Detailed_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


class SetuSalesPersonIncentiveLine(models.TransientModel):
    _name = 'sales.person.incentive.report.line'
    _description = "Sales Person Incentive Report Lines"

    sale_person_incentive_id = fields.Many2one('sales.person.incentive.report', string="Sale Icentive Lines")
    sale_person_id = fields.Many2one('hr.employee', string='Sale Person')
    incentive_rule_name = fields.Char(string='Incentive Rule')
    base_value = fields.Float(string='Base Value')
    amount = fields.Float(string='Incentive Amount')
    ref_company_id = fields.Many2one('res.company', store=True)
    name = fields.Char(string="Order Reference")
    pos_date = fields.Date(string="POS Order Date")

