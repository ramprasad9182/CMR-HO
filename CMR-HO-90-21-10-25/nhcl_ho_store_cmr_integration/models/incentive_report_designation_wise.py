import base64
import datetime
import io

import requests
import xlsxwriter
from odoo.tools import format_date, DEFAULT_SERVER_DATETIME_FORMAT

from odoo import fields, models, tools, api
from datetime import datetime

from odoo.tools.safe_eval import pytz, _logger, json


class IncentiveReportDesignation(models.TransientModel):
    _name = 'designation.wise.incentive.report'
    _description = "Incentive Report Designation Wise"

    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    ref_company_id = fields.Many2one('res.company', string='Company', domain=lambda self: self._get_company_domain())
    designation_wise_ids = fields.One2many('designation.wise.incentive.report.line', 'designation_wise_id')
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


    def designation_wise_incentive_report(self):
        self.designation_wise_ids.unlink()
        from_date = self.from_date
        to_date = self.to_date
        user_tz = self.env.user.tz or pytz.utc
        local = pytz.timezone(user_tz)
        sum = 0
        move_lines = self.env['stock.move.line'].search([
            ('picking_id.location_id.company_id.id', '=', self.nhcl_store_id.nhcl_store_name.company_id.id),
            ('picking_id.stock_picking_type', '=', 'pos_order'),
            ('state', '=', 'done'),
            ('create_date', '>=', self.from_date),
            ('create_date', '<=', self.to_date),
        ])
        for line in move_lines:
            sum += line.lot_id.rs_price

        structures = self.env['setu.sales.incentive.structure'].search([
            ('start_date', '<=', from_date.strftime("%Y,%m,%d")),
            ('end_date', '>=', to_date.strftime("%Y,%m,%d")),
            ('incentive_state', '=', 'confirmed'),
        ])


        site_wise_structures = structures.filtered(
            lambda
                s: s.nhcl_company_type == 'site_wise' and s.nhcl_incentive_type == 'store_target'and self.nhcl_store_id.nhcl_store_name.name in s.warehouse_ids.mapped(
                'name')
        )
        rule_lines = site_wise_structures.incentive_structure_line_ids.filtered(
            lambda x: x.calculate_based_on == 'pos_order' and x.aging_type == 'target'
        )
        for incentive_line in rule_lines:
            employees = self.env['hr.employee'].sudo().search([
                ('company_id', '=', self.nhcl_store_id.nhcl_store_name.company_id.id)])
            for employee in employees:
                # Employee incentive
                if employee.job_id.id == incentive_line.role.id:
                    incentive_amount = (
                        sum * (incentive_line.incentive_value / 100)
                        if incentive_line.calculation_method == 'percentage'
                        else incentive_line.incentive_value
                    )
                    self._create_incentive_line(employee.id, employee.job_id.id, incentive_line, sum,
                                                incentive_amount)

    def _create_incentive_line(self, employee_id, designation_id, incentive_line, sum, incentive_amount):
        summary_model = self.env['designation.wise.incentive.report.line']
        # existing_summary = summary_model.search([
        #     ('sale_person_id', '=', employee_id),
        #     ('sale_person_incentive_id', '=', self.id),
        #     ('incentive_struct_id', '=', incentive_line.incentive_structure_id.id),
        # ], limit=1)
        #
        # base_value = sum
        #
        # if existing_summary:
        #     existing_summary.write({
        #         'base_value': existing_summary.base_value + base_value,
        #         'amount': existing_summary.amount + incentive_amount,
        #     })
        # else:
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
            'employee_designation': designation_id,
            'ref_company_id': self.ref_company_id.id,
            'designation_wise_id': self.id,
            'incentive_struct_id': incentive_line.incentive_structure_id.id,
            'base_value': sum,
            'amount': incentive_amount,
            'incentive_rule_name': rule_name,
        })

    def action_to_reset(self):
        self.from_date = False
        self.to_date = False
        self.ref_company_id = False
        self.nhcl_store_id = False
        self.designation_wise_ids.unlink()


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
        for row_num, line in enumerate(self.designation_wise_ids, start=1):
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
            'name': f'Designation_Wise_Sales_Incentive_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Designation_Wise_Sales_Incentive_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


class IncentiveReportDesignationLine(models.TransientModel):
    _name = 'designation.wise.incentive.report.line'
    _description = "Incentive Report Designation Wise Line"

    designation_wise_id = fields.Many2one('designation.wise.incentive.report', string="Sale Icentive Lines")
    incentive_rule_name = fields.Char(string='Incentive Rule')
    base_value = fields.Float(string='Base Value')
    amount = fields.Float(string='Incentive Amount')
    ref_company_id = fields.Many2one('res.company', store=True)
    incentive_struct_id = fields.Many2one('setu.sales.incentive.structure',string='Incentive Structure')
    sale_person_id = fields.Many2one('hr.employee', string='Sale Person')
    employee_designation = fields.Many2one('hr.job', string="Designation")