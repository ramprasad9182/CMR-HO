import base64
import datetime
import io

import requests
import xlsxwriter
from odoo.tools import format_date, DEFAULT_SERVER_DATETIME_FORMAT

from odoo import fields, models, tools, api
from datetime import datetime

from odoo.tools.safe_eval import pytz, _logger, json


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
        self.sale_person_summary_incentive_ids.unlink()
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

                # --- Step 1: Get employees ---
                employee_search_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                if self.sale_person:
                    employee_domain = [('nhcl_id', '=', self.sale_person.nhcl_id)]
                else:
                    employee_domain = []

                emp_data_url = f"{employee_search_url}?domain={employee_domain}"
                employee_get_data = requests.get(emp_data_url, headers=headers_source).json()
                employee_data_list = employee_get_data.get("data", [])
                if not employee_data_list:
                    continue

                for employee_data in employee_data_list:
                    employee_id = employee_data.get('id')
                    barcode = employee_data.get('barcode')

                    # --- Step 2: Get POS order lines for this employee ---
                    pos_order_line_search_url = f"http://{ho_ip}:{ho_port}/api/pos.order.line/search"
                    order_line_domain = [('employ_id', '=', employee_id)]
                    if barcode:
                        order_line_domain.append(('badge_id', '=', barcode))
                    order_line_url = f"{pos_order_line_search_url}?domain={order_line_domain}"
                    pos_order_line_data = requests.get(order_line_url, headers=headers_source).json()
                    pos_data_lines = pos_order_line_data.get("data", [])

                    for line in pos_data_lines:
                        try:
                            date_str = line.get("create_date")
                            try:
                                date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f")
                            except ValueError:
                                date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                            local_date = pytz.utc.localize(date_obj).astimezone(local).date()
                        except Exception:
                            continue

                        if not (from_date <= local_date <= to_date):
                            continue

                        # Fetch order details
                        order_id = line.get("order_id")[0]['id']
                        order_url = f"http://{ho_ip}:{ho_port}/api/pos.order/search?domain=[('id', '=', {order_id})]"
                        order_response = requests.get(order_url, headers=headers_source).json()
                        order_data = order_response.get("data", [])
                        if not order_data:
                            continue

                        order_date_str = order_data[0].get("date_order")
                        try:
                            order_date = datetime.strptime(order_date_str, "%Y-%m-%dT%H:%M:%S").date()
                        except Exception:
                            continue

                        # Get all matching structures
                        structures = self.env['setu.sales.incentive.structure'].search([
                            ('start_date', '<=', order_date),
                            ('end_date', '>=', order_date),
                            ('incentive_state', '=', 'confirmed'),
                        ])

                        _logger.info(f"Matched {len(structures)} structures for POS date {order_date}")

                        # --- Separate site_wise and gross ---
                        site_wise_structures = structures.filtered(
                            lambda
                                s: s.nhcl_company_type == 'site_wise' and store.nhcl_store_name.name in s.warehouse_ids.mapped(
                                'name')
                        )
                        gross_structures = structures.filtered(lambda s: s.nhcl_company_type == 'gross')

                        for structure in (site_wise_structures + gross_structures):
                            if structure.nhcl_incentive_type == 'target':
                                rule_lines = structure.incentive_structure_line_ids.filtered(
                                    lambda x: x.calculate_based_on == 'pos_order' and
                                              x.target_value_min <= line.get('price_subtotal') <= x.target_value_max
                                )
                            else:
                                rule_lines = structure.incentive_structure_line_ids.filtered(
                                    lambda x: x.calculate_based_on == 'pos_order'
                                )

                            if not rule_lines:
                                _logger.info(f"No matching rule lines for structure: {structure.name}")
                                continue

                            for incentive_line in rule_lines:
                                employee = self.env['hr.employee'].sudo().search([
                                    ('name', '=', line.get('employ_id')[0]['name']), ('barcode' , '=', line.get('badge_id'))
                                ], limit=1)

                                if not employee:
                                    continue

                                # Aging check
                                for aging in incentive_line.aging_id:
                                    if aging and employee.job_id.id == incentive_line.role.id:
                                        matched = False
                                        for lot_dict in line.get('pack_lot_ids', []):
                                            lot_id = lot_dict.get("id")
                                            lot_url = f"http://{ho_ip}:{ho_port}/api/pos.pack.operation.lot/search?domain=[('id', '=', {lot_id})]"
                                            lot_response = requests.get(lot_url, headers=headers_source).json()
                                            lot_data = lot_response.get("data", [])
                                            if not lot_data:
                                                continue
                                            lot = self.env['stock.lot'].sudo().search([
                                                ('name', '=', lot_data[0]['lot_name'])
                                            ], limit=1)
                                            if lot and lot.description_1.name == aging.name:
                                                matched = True
                                                break
                                        if not matched:
                                            continue

                                # Day-aging check
                                if incentive_line.day_ageing_incentive and line.get('pack_lot_ids'):
                                    matched = False
                                    for lot_dict in line.get('pack_lot_ids', []):
                                        lot_id = lot_dict.get("id")
                                        lot_url = f"http://{ho_ip}:{ho_port}/api/pos.pack.operation.lot/search?domain=[('id', '=', {lot_id})]"
                                        lot_response = requests.get(lot_url, headers=headers_source).json()
                                        lot_data = lot_response.get("data", [])
                                        if not lot_data:
                                            continue
                                        lot = self.env['stock.lot'].sudo().search([
                                            ('name', '=', lot_data[0]['lot_name'])
                                        ], limit=1)
                                        if not lot or not lot.create_date:
                                            continue
                                        day_diff = (order_date - lot.create_date.date()).days
                                        day_range = incentive_line.day_ageing_incentive
                                        if ((day_range == '1' and 0 <= day_diff <= 30) or
                                                (day_range == '2' and 30 <= day_diff <= 60) or
                                                (day_range == '3' and 60 <= day_diff <= 90) or
                                                (day_range == '4' and 90 <= day_diff <= 120) or
                                                (day_range == '5' and 120 <= day_diff <= 150) or
                                                (day_range == '6' and 150 <= day_diff <= 180) or
                                                (day_range == '7' and 180 <= day_diff <= 210) or
                                                (day_range == '8' and 210 <= day_diff <= 240) or
                                                (day_range == '9' and 240 <= day_diff <= 270) or
                                                (day_range == '10' and 270 <= day_diff <= 360)):
                                            matched = True
                                            break
                                    if not matched:
                                        continue

                                # Employee incentive
                                if employee.job_id.id == incentive_line.role.id:
                                    incentive_amount = (
                                        line.get("price_subtotal_incl") * (incentive_line.incentive_value / 100)
                                        if incentive_line.calculation_method == 'percentage'
                                        else incentive_line.incentive_value
                                    )
                                    self._create_incentive_line(employee.id, incentive_line, line, order_date,
                                                                incentive_amount)

                                # # Manager incentive
                                # if employee.parent_id and employee.parent_id.job_id.id == incentive_line.role.id:
                                #     incentive_amount = (
                                #         line.get("price_subtotal_incl") * (incentive_line.incentive_value / 100)
                                #         if incentive_line.calculation_method == 'percentage'
                                #         else incentive_line.incentive_value
                                #     )
                                #     self._create_incentive_line(employee.parent_id.id, incentive_line, line, order_date,
                                #                                 incentive_amount)
                                #
                                # if employee.parent_id.parent_id and employee.parent_id.parent_id.job_id.id == incentive_line.role.id:
                                #     incentive_amount = (
                                #         line.get("price_subtotal_incl") * (incentive_line.incentive_value / 100)
                                #         if incentive_line.calculation_method == 'percentage'
                                #         else incentive_line.incentive_value
                                #     )
                                #     self._create_incentive_line(employee.parent_id.parent_id.id, incentive_line, line, order_date,
                                #                                 incentive_amount)

        except requests.exceptions.RequestException as e:
            _logger.error(f"Failed to retrieve POS orders for store {store.nhcl_store_name.name}: {e}")

    def _create_incentive_line(self, employee_id, incentive_line, pos_line_data, order_date, incentive_amount):
        summary_model = self.env['sales.person.incentive.summary.report.line']
        existing_summary = summary_model.search([
            ('sale_person_id', '=', employee_id),
            ('sale_person_incentive_id', '=', self.id),
            ('incentive_struct_id', '=', incentive_line.incentive_structure_id.id),
        ], limit=1)

        base_value = pos_line_data.get("price_subtotal_incl")

        if existing_summary:
            existing_summary.write({
                'base_value': existing_summary.base_value + base_value,
                'amount': existing_summary.amount + incentive_amount,
            })
        else:
            rule_name = "{} - {} - {}[{}] - {} - {} - {}[{} - {}]".format(
                incentive_line.incentive_structure_id.name,
                incentive_line.role.name if incentive_line.role else '',
                dict(incentive_line._fields['calculate_based_on'].selection).get(incentive_line.calculate_based_on),
                "POS Orders",
                dict(incentive_line._fields['target_based_on'].selection).get(incentive_line.target_based_on),
                dict(incentive_line._fields['calculation_method'].selection).get(incentive_line.calculation_method),
                incentive_line.incentive_value,
                incentive_line.target_value_min,
                incentive_line.target_value_max,
            )

            summary_model.create({
                'sale_person_id': employee_id,
                'ref_company_id': self.ref_company_id.id,
                'sale_person_incentive_id': self.id,
                'incentive_struct_id': incentive_line.incentive_structure_id.id,
                'base_value': base_value,
                'amount': incentive_amount,
                'incentive_rule_name': rule_name,
            })

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
