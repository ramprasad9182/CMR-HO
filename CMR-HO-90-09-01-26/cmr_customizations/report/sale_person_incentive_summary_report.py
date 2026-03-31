import base64
import datetime
import io

import xlsxwriter
from odoo.tools import format_date

from odoo import fields, models, tools, api
from datetime import datetime


class SetuSalesPersonIncentiveSummary(models.TransientModel):
    _name = 'sales.person.incentive.summary.report'
    _description = "Sales Person Incentive Summary Report"

    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    ref_company_id = fields.Many2one('res.company', string='Company', domain=lambda self: self._get_company_domain())
    sale_person = fields.Many2one('hr.employee', string='Sale Person')
    sale_person_summary_incentive_ids = fields.One2many('sales.person.incentive.summary.report.line', 'sale_person_incentive_id')

    @api.model
    def _get_company_domain(self):
        # Get the companies currently selected in the user's session context (allowed companies)
        allowed_company_ids = self.env.context.get('allowed_company_ids', [])

        # Apply the domain to show only the companies selected in the session
        return [('id', 'in', allowed_company_ids)] if allowed_company_ids else []

    def action_check_sale_person_incentive_report(self):
        self.sale_person_summary_incentive_ids.unlink()  # Clear previous records

        sale_reports = self.env['pos.order'].sudo().search([])

        for sale_report in sale_reports:
            if self.sale_person:
                pos_order_line_report = self.env['pos.order.line'].sudo().search(
                    [('order_id', '=', sale_report.id),
                     ('employ_id', '=', self.sale_person.id),
                     ('badge_id', '=', self.sale_person.barcode)])
            else:
                pos_order_line_report = self.env['pos.order.line'].sudo().search([('order_id', '=', sale_report.id)])

            pos_line_date = pos_order_line_report.filtered(
                lambda
                    x: self.from_date <= x.order_id.date_order.date() <= self.to_date and x.order_id.company_id == self.ref_company_id
            )

            for line in pos_line_date:
                line_date = line.order_id.date_order.date()
                structure_id = self.env['setu.sales.incentive.structure'].search(
                    [('start_date', '<=', line_date), ('end_date', '>=', line_date),
                     ('incentive_state', '=', "confirmed"), ('company_id', '=', self.ref_company_id.id)]
                )

                incentive_structure_line_id = structure_id.incentive_structure_line_ids.filtered(
                    lambda
                        x: x.calculate_based_on == 'pos_order' and x.target_value_min <= line.margin and x.target_value_max >= line.margin
                )

                if line.price_subtotal_incl > 0 and incentive_structure_line_id:
                    # Check if there is an existing sale person line
                    existing_sale_person_line = self.sale_person_summary_incentive_ids.filtered(
                        lambda x: x.sale_person_id == line.employ_id)

                    if existing_sale_person_line:
                        # Update existing line
                        existing_sale_person_line.write({
                            'base_value': existing_sale_person_line.base_value + line.price_subtotal_incl,
                            'amount': existing_sale_person_line.amount + incentive_structure_line_id.incentive_value,
                        })
                    else:
                        vals = {
                            'sale_person_id': line.employ_id.id,
                            'ref_company_id': line.order_id.company_id.id,
                            'sale_person_incentive_id': self.id,
                            'base_value': line.price_subtotal_incl,
                            'amount': incentive_structure_line_id.incentive_value,
                            'incentive_rule_name': "{} - {} - {}[{}] - {} - {} - {}[{} - {}]".format(
                                incentive_structure_line_id.incentive_structure_id.name,
                                dict(incentive_structure_line_id._fields['role'].selection).get(
                                    incentive_structure_line_id.role),
                                dict(incentive_structure_line_id._fields['calculate_based_on'].selection).get(
                                    incentive_structure_line_id.calculate_based_on),
                                "POS Orders",
                                dict(incentive_structure_line_id._fields['target_based_on'].selection).get(
                                    incentive_structure_line_id.target_based_on),
                                dict(incentive_structure_line_id._fields['calculation_method'].selection).get(
                                    incentive_structure_line_id.calculation_method),
                                incentive_structure_line_id.incentive_value,
                                incentive_structure_line_id.target_value_min,
                                incentive_structure_line_id.target_value_max,
                            )
                        }
                        self.sale_person_summary_incentive_ids.create(vals)

    def action_to_reset(self):
        self.sale_person = False
        self.from_date = False
        self.to_date = False
        self.ref_company_id = False
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
