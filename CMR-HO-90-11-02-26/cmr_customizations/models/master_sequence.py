from odoo import models, fields, api
from odoo.exceptions import UserError
import io
import base64
import xlsxwriter
from odoo.tools.misc import format_date


class MasterSequence(models.Model):
    """Created nhcl.master.sequence class to add fields and functions"""
    _name = 'nhcl.master.sequence'
    _description = "Sequence Master"

    nhcl_data = fields.Date(string='Date', default=fields.Date.today, copy=False)
    nhcl_prefix = fields.Char(string='Prefix', copy=False)
    nhcl_code = fields.Char(string='Code', copy=False)
    nhcl_type = fields.Char(string='Type', copy=False)
    nhcl_padding = fields.Integer(string='Padding', copy=False)
    nhcl_next_number = fields.Integer(string='Next Number', copy=False)
    nhcl_active = fields.Boolean(string='Active', default=True, copy=False)
    nhcl_state = fields.Selection([('draft', 'Draft'), ('activate', 'Activated'), ('in_activate', 'De Activated')],
                                  string='Status', default='draft', copy=False)

    def activate_sequence(self):
        if self.nhcl_next_number and self.nhcl_prefix and self.nhcl_code and self.nhcl_state in ['draft',
                                                                                                 'in_activate']:
            a = self.env['ir.sequence'].search([('code', '=', self.nhcl_code)])
            a.prefix = self.nhcl_prefix
            a.padding = self.nhcl_padding
            a.code = self.nhcl_code
            a.number_next_actual = self.nhcl_next_number
            self.nhcl_state = 'activate'

    def deactivate_sequence(self):
        if self.nhcl_state == 'activate':
            self.nhcl_state = 'in_activate'
            self.nhcl_active = False
        return {
            'type': 'ir.actions.client', 'tag': 'reload'
        }


class vehicleTransport(models.Model):
    _name = 'vehicle.transport'

    name = fields.Char(string='Name',copy=False)
    company_id = fields.Many2one('res.company', string="Company", copy=False, domain=lambda self: self._get_company_domain())
    cmr_transpot_ids = fields.One2many('vehicle.transport.line','cmr_transpot_id', string='Vehicle', copy=False)
    vehicle_id = fields.Many2one('fleet.vehicle',string='Vehicle', copy=False, domain="[('company_id','=',company_id)]")
    from_date = fields.Date(string='From Date', copy=False)
    end_date = fields.Date(string='End Date', copy=False)

    @api.model
    def _get_company_domain(self):
        allowed_company_ids = self.env.context.get('allowed_company_ids', [])
        return [('id', 'in', allowed_company_ids)] if allowed_company_ids else []

    def get_vehicle_status(self):
        self.ensure_one()
        if not self.vehicle_id:
            raise UserError("Please pick a vehicle before retrieving journal lines!.")
        if not self.from_date or not self.end_date:
            raise UserError("Before obtaining journal lines, please choose both the From and End Dates!.")
        if self.from_date > self.end_date:
            raise UserError("The End Date must be after the From Date!.")
        journal_lines = self.env['account.move.line'].sudo().search(
            [('vehicle_id', '=', self.vehicle_id.id), ('move_id.invoice_date', '>=', self.from_date),
             ('move_id.invoice_date', '<=', self.end_date)])
        filtered_jes = journal_lines.filtered(lambda x: x.company_id == self.company_id)
        self.cmr_transpot_ids.unlink()
        line_values = []
        for i in filtered_jes:
            line_values.append((0, 0, {
                'account_id': i.account_id.id,
                'label': i.name,
                'je_no': i.move_id.name,
                'credit': i.credit,
                'debit': i.debit
            }))
        self.write({'cmr_transpot_ids': line_values})

    def unlink_vehicle_lines(self):
        # Unlink all the records in the One2many field
        self.vehicle_id = False
        self.company_id = False
        self.from_date = False
        self.end_date = False
        self.ensure_one()
        self.cmr_transpot_ids.unlink()

    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Vehicle', 'From date', 'End date', 'JE Number', 'Analytical Account', 'Label', 'Debit', 'Credit']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.cmr_transpot_ids, start=1):
            worksheet.write(row_num, 0, self.vehicle_id.name)
            worksheet.write(row_num, 1, self.from_date and format_date(self.env, self.from_date, date_format='dd-MM-yyyy'))
            worksheet.write(row_num, 2, self.end_date and format_date(self.env, self.end_date, date_format='dd-MM-yyyy'))
            worksheet.write(row_num, 3, line.je_no)
            worksheet.write(row_num, 4, line.account_id.name)
            worksheet.write(row_num, 5, line.label)
            worksheet.write(row_num, 6, line.debit)
            worksheet.write(row_num, 7, line.credit)

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
            'name': f'Fleet_Status_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'Fleet_Status_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }



class CmrTransport(models.Model):
    _name = 'vehicle.transport.line'

    cmr_transpot_id = fields.Many2one('vehicle.transport')
    account_id = fields.Many2one('account.account',string='Analytical Account', copy=False)
    label = fields.Char(string='Label', copy=False)
    je_no = fields.Char(string='JE Number', copy=False)
    debit = fields.Float(string='Debit', copy=False)
    credit = fields.Float(string='Credit', copy=False)
