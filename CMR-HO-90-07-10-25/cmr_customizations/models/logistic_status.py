import io
import base64
import xlsxwriter
from odoo.tools.misc import format_date
from odoo import fields, api, models
from odoo.exceptions import UserError, ValidationError


class LogisticStatus(models.TransientModel):
    _name = "logistic.status.screen"

    _rec_name = "logistic_numbering"

    transporter_name = fields.Many2one('res.partner', domain="[('group_contact.name', '=', 'Transporter')]",
                                       string="Transporter",)
    date = fields.Selection([('2024','2024'), ('2025','2025'), ('2026','2026'), ('2027','2027'), ('2028','2028')], string="Date")
    logistic_stage = fields.Char('Logistic Stage')
    logistic_status_ids = fields.One2many('logistic.status.data', 'logistic_status_id')
    logistic_numbering = fields.Many2one('logistic.screen.data', string="LR Number",domain="[('state', '=', 'done')]")

    @api.onchange('transporter_name')
    def _onchange_transporter_name(self):
        if self.transporter_name:
            return {
                'domain': {
                    'logistic_numbering': [('transporter.id', '=', self.transporter_name.id),]
                }
            }
        else:
            return {
                'domain': {
                    'logistic_numbering': []
                }
            }

    def action_check_logistics(self):
        self.ensure_one()

        if not self.logistic_numbering:
            raise UserError("The LR Number is required and must be picked before proceeding.")

        if not self.transporter_name:
            raise UserError("A transporter is required and must be picked before proceeding.")

        if self.transporter_name and self.logistic_numbering:
            # Clear existing logistic status lines
            self.logistic_status_ids.unlink()

            # Initialize an empty list to hold the new lines
            logistic_status_lines = []

            # Search for records based on transporter and logistic number
            logistic_records = self.env['logistic.screen.data'].search([
                ('transporter', '=', self.transporter_name.id),
                ('lr_number', '=', self.logistic_numbering.lr_number)
            ])
            transport_records = self.env['transport.check'].search([
                ('transporter', '=', self.transporter_name.id),
                ('logistic_lr_number', '=', self.logistic_numbering.lr_number)
            ])
            additional_records = self.env['delivery.check'].search([
                ('transporter', '=', self.transporter_name.id),
                ('logistic_lr_number', '=', self.logistic_numbering.lr_number)
            ])

            # Process logistic records
            for logistic_record in logistic_records:
                if not self.date:
                    self.date = logistic_record.lr_date
                    self.logistic_stage = logistic_record.state

                lg_arrived_value = logistic_record.state != 'draft'
                logistic_status_lines.append((0, 0, {
                    'logistic_stage': 'logistic',
                    'logistic_bales': logistic_record.no_of_bales,
                    'logistic_date': logistic_record.lr_date,
                    'lg_arrived': lg_arrived_value
                }))

            # Process transport records
            for transport_record in transport_records:
                lg_arrived_value = transport_record.state != 'draft'
                logistic_status_lines.append((0, 0, {
                    'logistic_stage': 'transporter',
                    'logistic_bales': transport_record.no_of_bales,
                    'logistic_date': transport_record.logistic_date,
                    'lg_arrived': lg_arrived_value
                }))

            # Process additional records
            for additional_record in additional_records:
                lg_arrived_value = additional_record.state != 'draft'
                logistic_status_lines.append((0, 0, {
                    'logistic_stage': 'delivery',
                    'logistic_bales': additional_record.partial_bales,
                    'logistic_date': additional_record.logistic_date,
                    'lg_arrived': lg_arrived_value
                }))

            # Update the logistic_status_ids field with all the generated lines
            self.logistic_status_ids = logistic_status_lines

    def action_to_reset(self):
        self.ensure_one()
        self.logistic_status_ids.unlink()
        self.date = False
        self.logistic_stage = False
        self.logistic_numbering = False
        self.transporter_name = False

    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Transporter Name', 'LR Number', 'Logistic Stage', 'No Of Bales', 'Arrived Date', 'Arrived']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.logistic_status_ids, start=1):
            worksheet.write(row_num, 0, self.transporter_name.name)
            worksheet.write(row_num, 1, self.logistic_numbering.lr_number)
            worksheet.write(row_num, 2, line.logistic_stage)
            worksheet.write(row_num, 3, line.logistic_bales)
            worksheet.write(row_num, 4, line.logistic_date and format_date(self.env, line.logistic_date, date_format='dd-MM-yyyy'))
            worksheet.write(row_num, 5, 'Yes' if line.lg_arrived else 'No')

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
            'name': f'Logistic_Status_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Logistic_Status_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


class LogisticStatusdata(models.TransientModel):
    _name = "logistic.status.data"

    logistic_status_id = fields.Many2one('logistic.status.screen', string='Logistic Status')
    logistic_stage = fields.Selection(
        [('logistic', 'Logistic Entry'), ('transporter', 'Transport Check'), ('delivery', 'Delivery Check')]
    )
    logistic_bales = fields.Integer('No Of Bales')
    logistic_date = fields.Date('Arrived Date')
    lg_arrived = fields.Boolean('Arrived')
