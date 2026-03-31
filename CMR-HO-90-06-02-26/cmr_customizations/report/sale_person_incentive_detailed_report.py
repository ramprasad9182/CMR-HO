import base64
import datetime
import io

import xlsxwriter
from odoo.tools import format_date

from odoo import fields, models, tools,api
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)


class SetuSalesPersonIncentive(models.TransientModel):
    _name = 'sales.person.incentive.report'
    _description = "Sales Person Incentive Report"

    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    ref_company_id = fields.Many2one('res.company', string='Company', domain=lambda self: self._get_company_domain())
    sale_person = fields.Many2one('hr.employee', string='Sale Person')
    sale_person_incentive_ids = fields.One2many('sales.person.incentive.report.line', 'sale_person_incentive_id')

    @api.model
    def _get_company_domain(self):
        # Get the companies currently selected in the user's session context (allowed companies)
        allowed_company_ids = self.env.context.get('allowed_company_ids', [])

        # Apply the domain to show only the companies selected in the session
        return [('id', 'in', allowed_company_ids)] if allowed_company_ids else []

    # def action_check_sale_person_incentive_report(self):
    #     self.sale_person_incentive_ids.unlink()
    #     if self.sale_person:
    #         sale_reports = self.env['sale.report'].search(
    #             [('user_id', '=', self.sale_person.id)])
    #     else:
    #         sale_reports = self.env['sale.report'].sudo().search([])
    #
    #     pos_line_date = sale_reports.filtered(lambda x: datetime.strptime(str(x.date),
    #                                                                "%Y-%m-%d %H:%M:%S").date() >= self.from_date and datetime.strptime(
    #         str(x.date), "%Y-%m-%d %H:%M:%S").date() <= self.to_date and x.team_id.name == 'Point of Sale' and x.company_id == self.ref_company_id)
    #     for line in pos_line_date:
    #         line_date = datetime.strptime(str(line.date),"%Y-%m-%d %H:%M:%S").date()
    #         structure_id = self.env['setu.sales.incentive.structure'].search([('start_date','<=',line_date),('end_date','>=',line_date),('incentive_state', '=', "confirmed")])
    #         incentive_structure_line_id = structure_id.incentive_structure_line_ids.filtered(lambda x:x.calculate_based_on == 'pos_order' and x.target_value_min <= line.margin and x.target_value_max >= line.margin)
    #         if line.margin > 0 and incentive_structure_line_id:
    #             vals = {
    #                 'sale_person_id': line.user_id.id,
    #                 'ref_company_id': line.company_id.id,
    #                 'sale_person_incentive_id': self.id,
    #                 'name': line.name,
    #                 'pos_date': line_date,
    #                 'base_value': line.margin,
    #                 'amount': incentive_structure_line_id.incentive_value,
    #                 "incentive_rule_name": "{} - {} - {}[{}] - {} - {} - {}[{} - {}]".format(
    #                     incentive_structure_line_id.incentive_structure_id.name,
    #                     dict(incentive_structure_line_id._fields['role'].selection).get(
    #                         incentive_structure_line_id.role),
    #                     dict(incentive_structure_line_id._fields['calculate_based_on'].selection).get(
    #                         incentive_structure_line_id.calculate_based_on),
    #                     "POS Orders",
    #                     dict(incentive_structure_line_id._fields['target_based_on'].selection).get(
    #                         incentive_structure_line_id.target_based_on),
    #                     dict(incentive_structure_line_id._fields['calculation_method'].selection).get(
    #                         incentive_structure_line_id.calculation_method),
    #                     incentive_structure_line_id.incentive_value,
    #                     incentive_structure_line_id.target_value_min,
    #                     incentive_structure_line_id.target_value_max),
    #
    #             }
    #             self.env['sales.person.incentive.report.line'].create(vals)
    #

    def action_check_sale_person_incentive_report(self):
        self.sale_person_incentive_ids.unlink()  # Clear previous records
        sale_reports = self.env['pos.order'].sudo().search([])

        for sale_report in sale_reports:
            if self.sale_person:
                pos_order_line_report = self.env['pos.order.line'].sudo().search(
                    [('order_id', '=', sale_report.id), ('employ_id', '=', self.sale_person.id),
                     ('badge_id', '=', self.sale_person.barcode)])
            else:
                pos_order_line_report = self.env['pos.order.line'].sudo().search([('order_id', '=', sale_report.id)])
            _logger.info("pos_order_line_report-%s" % pos_order_line_report)
            pos_line_date = pos_order_line_report.filtered(lambda
                                                               x: self.from_date <= x.order_id.date_order.date() <= self.to_date and x.order_id.company_id == self.ref_company_id)
            _logger.info("pos_line_date-%s"%pos_line_date)
            for line in pos_line_date:
                line_date = line.order_id.date_order.date()
                structure_id = self.env['setu.sales.incentive.structure'].search(
                    [('start_date', '<=', line_date), ('end_date', '>=', line_date),
                     ('incentive_state', '=', "confirmed"), ('company_id', '=', self.ref_company_id.id)]
                )
                incentive_structure_line_id = structure_id.incentive_structure_line_ids.filtered(lambda
                                                                                                     x: x.calculate_based_on == 'pos_order' and x.target_value_min <= line.margin and x.target_value_max >= line.margin)

                if line.price_subtotal_incl > 0 and incentive_structure_line_id:
                    for incentive_line in incentive_structure_line_id:
                        incentive_line.ensure_one()  # Ensure one record is processed
                        vals = {
                            'sale_person_id': line.employ_id.id,
                            'ref_company_id': line.order_id.company_id.id,
                            'sale_person_incentive_id': self.id,
                            'name': line.order_id.name,
                            'pos_date': line_date,
                            'base_value': line.price_subtotal_incl,
                            'amount': incentive_line.incentive_value,
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
                            ),
                        }
                        _logger.info("vals-%s" % vals)
                        self.sale_person_incentive_ids.create(vals)

    def action_to_reset(self):
        self.sale_person = False
        self.from_date = False
        self.to_date = False
        self.ref_company_id = False
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
        headers = ['Session Name', 'POS Date','Sales Person', 'Base Value', 'Incentive Amount', 'Company']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.sale_person_incentive_ids, start=1):
            worksheet.write(row_num, 0, line.name)
            worksheet.write(row_num, 1, line.pos_date and format_date(self.env, line.pos_date, date_format='dd-MM-yyyy'))
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
