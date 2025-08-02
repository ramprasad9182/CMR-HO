import base64
import datetime
import io

import requests
import xlsxwriter
from odoo.tools import format_date, DEFAULT_SERVER_DATETIME_FORMAT

from odoo import fields, models, tools, api
from datetime import datetime

from odoo.tools.safe_eval import pytz, _logger


class SetuSalesPersonIncentiveSummary(models.TransientModel):
    _name = 'sales.person.incentive.summary.report'
    _description = "Sales Person Incentive Summary Report"

    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    ref_company_id = fields.Many2one('res.company', string='Company', domain=lambda self: self._get_company_domain())
    sale_person = fields.Many2one('hr.employee', string='Sale Person')
    sale_person_summary_incentive_ids = fields.One2many('sales.person.incentive.summary.report.line', 'sale_person_incentive_id')
    nhcl_store_id = fields.Many2one('nhcl.ho.store.master', string='Company')

    @api.model
    def _get_company_domain(self):
        # Get the companies currently selected in the user's session context (allowed companies)
        allowed_company_ids = self.env.context.get('allowed_company_ids', [])

        # Apply the domain to show only the companies selected in the session
        return [('id', 'in', allowed_company_ids)] if allowed_company_ids else []

    @api.onchange('nhcl_store_id')
    def _onchange_get_ref_company(self):
        if self.nhcl_store_id:
            self.ref_company_id = self.nhcl_store_id.nhcl_store_name.sudo().company_id


    def action_check_sale_person_incentive_report(self):
        self.sale_person_summary_incentive_ids.unlink()  # Clear previous records
        try:
            for store in self.nhcl_store_id:
                ho_ip = store.nhcl_terminal_ip
                ho_port = store.nhcl_port_no
                ho_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                from_date = self.from_date
                to_date = self.to_date
                user_tz = self.env.user.tz or pytz.utc
                local = pytz.timezone(user_tz)
                # Get employee ID
                employee_search_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                employee_domain = [('nhcl_id', '=', self.sale_person.nhcl_id)]
                emp_data = f"{employee_search_url}?domain={employee_domain}"
                employee_get_data = requests.get(emp_data, headers=headers_source).json()
                employee_data = employee_get_data.get("data", [])
                if not employee_data and self.sale_person:
                    _logger.info(f"No Employee found for '{self.name}', skipping.")
                    continue
                employee_id = False
                if self.sale_person:
                    employee_id = employee_data[0]['id']
                # Get POS order lines
                pos_order_line_url = f"http://{ho_ip}:{ho_port}/api/pos.order.line/search"
                if self.sale_person:
                    order_line_domain = [('employ_id', '=', employee_id),
                                         ('badge_id', '=', employee_data[0]['barcode'])]
                else:
                    order_line_domain = []
                order_line_url = f"{pos_order_line_url}?domain={order_line_domain}"
                pos_order_line_data = requests.get(order_line_url, headers=headers_source).json()
                pos_data_line = pos_order_line_data.get("data", [])
                for data in pos_data_line:
                    date_order_str = data.get("create_date")
                    try:
                        date_order = datetime.strptime(date_order_str, "%Y-%m-%dT%H:%M:%S.%f")
                    except ValueError:
                        date_order = datetime.strptime(date_order_str, "%Y-%m-%dT%H:%M:%S")
                    date_order_local = date_order.astimezone(local).date()
                    if from_date <= date_order_local <= to_date:
                        store_master = self.env['nhcl.ho.store.master'].search([('id', '=', store.id)], limit=1)
                        if not store_master:
                            continue
                        # Get POS Order
                        order_domain = [('id', '=', data.get("order_id")[0]['id'])]
                        pos_order_url = f"http://{ho_ip}:{ho_port}/api/pos.order/search?domain={order_domain}"
                        pos_order_data = requests.get(pos_order_url, headers=headers_source).json()
                        pos_data = pos_order_data.get("data", [])
                        if not pos_data:
                            continue
                        order_date = datetime.strptime(pos_data[0].get("date_order"), "%Y-%m-%dT%H:%M:%S")
                        order_date = order_date.astimezone(local).date()
                        structure_id = self.env['setu.sales.incentive.structure'].search([
                            ('start_date', '<=', order_date),
                            ('end_date', '>=', order_date),
                            ('incentive_state', '=', "confirmed"),
                        ])
                        if not structure_id:
                            continue
                        line_margin = data.get('price_subtotal') - data.get('total_cost')
                        incentive_structure_line_ids = structure_id.incentive_structure_line_ids.filtered(
                            lambda x: x.calculate_based_on == 'pos_order' and
                                      x.target_value_min <= line_margin <= x.target_value_max
                        )
                        if data.get('price_subtotal_incl') <= 0:
                            continue
                        # lot_name = data.get('lot_id', {}).get('name')
                        # lot = self.env['stock.lot'].search([('name', '=', lot_name)], limit=1)
                        lot = False
                        for lot_dict in data.get('pack_lot_ids', []):
                            pack_lot_search_url = f"http://{ho_ip}:{ho_port}/api/pos.pack.operation.lot/search"
                            pack_lot_domain = [('id', '=', lot_dict.get("id"))]
                            pack_lot_url = f"{pack_lot_search_url}?domain={pack_lot_domain}"
                            pack_lot_data = requests.get(pack_lot_url, headers=headers_source).json()
                            pack_lot = pack_lot_data.get("data", [])
                            lot = self.env['stock.lot'].sudo().search([('name', '=', pack_lot[0]['lot_name'])],
                                                                      limit=1)
                        if not lot:
                            continue
                        for rule in incentive_structure_line_ids:
                            matched = False

                            # Check aging_id logic
                            if rule.aging_id:
                                if lot and rule.aging_id.name == lot.description_1.name:
                                    matched = True
                                else:
                                    continue  # aging_id doesn't match
                            # Check day_ageing_incentive logic
                            elif rule.day_ageing_incentive:
                                days_old = (date_order_local - lot.create_date.date()).days
                                range_map = {
                                    '1': (0, 30), '2': (30, 60), '3': (60, 90), '4': (90, 120),
                                    '5': (120, 150), '6': (150, 180), '7': (180, 210),
                                    '8': (210, 240), '9': (240, 270), '10': (270, 300),
                                    '11': (300, 330), '12': (330, 360)
                                }
                                range_min, range_max = range_map.get(rule.day_ageing_incentive, (None, None))
                                if range_min is not None and range_min <= days_old < range_max:
                                    matched = True
                                else:
                                    continue  # age doesn't match
                            # else:
                            #     continue  # No aging rule set
                            # If rule matched
                            if rule.incentive_value > 0:
                                if rule.calculation_method == 'percentage':
                                    value = data.get("price_subtotal_incl") * (rule.incentive_value / 100)
                                else:
                                    value = rule.incentive_value
                                hr_employee_id = False
                                if data.get('employ_id'):
                                    hr_employee_id = self.env['hr.employee'].sudo().search(
                                    [('name', '=', data.get('employ_id')[0]['name'])])
                                if self.sale_person:
                                    existing_line = self.sale_person_summary_incentive_ids.filtered(
                                    lambda x: x.sale_person_id == self.sale_person and
                                              x.incentive_struct_id == rule.incentive_structure_id
                                       )
                                else:
                                    existing_line = self.sale_person_summary_incentive_ids.filtered(
                                        lambda x: x.sale_person_id == hr_employee_id and x.incentive_struct_id == rule.incentive_structure_id
                                    )
                                if self.sale_person:
                                    sale_person = self.sale_person.id
                                elif hr_employee_id:
                                    sale_person = hr_employee_id.id
                                else:
                                    sale_person = False
                                if existing_line:
                                    existing_line[0].write({
                                        'base_value': existing_line.base_value + data.get('price_subtotal_incl'),
                                        'amount': existing_line.amount + value,
                                    })
                                else:
                                    vals = {
                                        'sale_person_id': sale_person,
                                        'ref_company_id': self.ref_company_id.id,
                                        'sale_person_incentive_id': self.id,
                                        'incentive_struct_id' : rule.incentive_structure_id.id,
                                        'base_value': data.get('price_subtotal_incl'),
                                        'amount': value,
                                        'incentive_rule_name': "{} - {} - {}[{}] - {} - {} - {}[{} - {}]".format(
                                            rule.incentive_structure_id.name,
                                            dict(rule._fields['role'].selection).get(rule.role),
                                            dict(rule._fields['calculate_based_on'].selection).get(
                                                rule.calculate_based_on),
                                            "POS Orders",
                                            dict(rule._fields['target_based_on'].selection).get(rule.target_based_on),
                                            dict(rule._fields['calculation_method'].selection).get(
                                                rule.calculation_method),
                                            rule.incentive_value,
                                            rule.target_value_min,
                                            rule.target_value_max,
                                        )
                                    }
                                    self.sale_person_summary_incentive_ids.create(vals)
        except requests.exceptions.RequestException as e:
            _logger.error(f"Failed to retrieve POS orders for store {store.nhcl_store_name.name}: {e}")

    def action_to_reset(self):
        self.sale_person = False
        self.from_date = False
        self.to_date = False
        self.ref_company_id = False
        self.nhcl_store_id = False
        self.sale_person_summary_incentive_ids.unlink()


    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Sales Person', 'Base Value', 'Incentive Amount', 'Company']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.sale_person_summary_incentive_ids, start=1):
            worksheet.write(row_num, 0, line.sale_person_id.name)
            worksheet.write(row_num, 1, line.base_value)
            worksheet.write(row_num, 2, line.amount)
            worksheet.write(row_num, 3, line.ref_company_id.name)

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
            'name': f'Sales_Incentive_Summary_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Sales_Incentive_Summary_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


class SetuSalesPersonIncentiveSummaryLine(models.TransientModel):
    _name = 'sales.person.incentive.summary.report.line'
    _description = "Sales Person Incentive Summary Report Lines"

    sale_person_incentive_id = fields.Many2one('sales.person.incentive.summary.report', string="Sale Icentive Lines")
    sale_person_id = fields.Many2one('hr.employee', string='Sale Person')
    incentive_rule_name = fields.Char(string='Incentive Rule')
    base_value = fields.Float(string='Base Value')
    amount = fields.Float(string='Incentive Amount')
    ref_company_id = fields.Many2one('res.company', store=True)
    incentive_struct_id = fields.Many2one('setu.sales.incentive.structure',string='Incentive Structure')
