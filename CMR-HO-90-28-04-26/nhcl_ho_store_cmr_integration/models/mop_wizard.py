from odoo import models,fields,api,_
import requests
from datetime import datetime, time
import pytz
from odoo.exceptions import ValidationError
import xmlrpc.client


from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict


class PosTaxReportWizard(models.TransientModel):
    _name = 'pos.mop.report.wizard'
    _description = 'POS MOP Report Wizard'
    _rec_name = 'name'

    def _default_from_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(3, 30, 0))
        )

    def _default_to_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(18, 30, 0))
        )

    from_date = fields.Datetime(
        string='From Date',
        default=_default_from_date
    )
    to_date = fields.Datetime(
        string='To Date',
        default=_default_to_date
    )
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company')
    pos_mop_report_ids = fields.One2many('pos.mop.report.line', 'pos_mop_report_id')
    total_cash = fields.Float(compute="_compute_nhcl_show_totals", string='Total Cash')
    total_axis = fields.Float(compute="_compute_nhcl_show_totals", string='Total Axis')
    total_hdfc = fields.Float(compute="_compute_nhcl_show_totals", string='Total HDFC')
    total_kotak = fields.Float(compute="_compute_nhcl_show_totals", string='Total Kotak')
    total_paytm = fields.Float(compute="_compute_nhcl_show_totals", string='Total Paytm')
    total_sbi = fields.Float(compute="_compute_nhcl_show_totals", string='Total SBI')
    total_bajaj = fields.Float(compute="_compute_nhcl_show_totals", string='Total Bajaj')
    total_mobikwik = fields.Float(compute="_compute_nhcl_show_totals", string='Total Mobikwik')
    total_cheque = fields.Float(compute="_compute_nhcl_show_totals", string='Total Cheque')
    total_gift_voucher = fields.Float(compute="_compute_nhcl_show_totals", string='Total Gift Voucher')
    total_credit_note_settlement = fields.Float(compute="_compute_nhcl_show_totals",
                                                string='Total Credit Note Settlement')
    grand_total = fields.Float(compute="_compute_nhcl_show_totals", string='Grand Total')

    name = fields.Char(string='Name', default='POS Mode Of Payment Report')

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.pos_mop_report_ids
            rec.total_cash = sum(lines.mapped('cash'))
            rec.total_axis = sum(lines.mapped('axis'))
            rec.total_hdfc = sum(lines.mapped('hdfc'))
            rec.total_kotak = sum(lines.mapped('kotak'))
            rec.total_paytm = sum(lines.mapped('paytm'))
            rec.total_sbi = sum(lines.mapped('sbi'))
            rec.total_bajaj = sum(lines.mapped('bajaj'))
            rec.total_mobikwik = sum(lines.mapped('mobikwik'))
            rec.total_cheque = sum(lines.mapped('cheque'))
            rec.total_gift_voucher = sum(lines.mapped('gift_voucher'))
            rec.total_credit_note_settlement = sum(lines.mapped('credit_note_settlement'))
            rec.grand_total = sum(lines.mapped('grand_total'))

    # def get_grouped_payments(self):
    #     report_list = []
    #     try:
    #         for store in self.nhcl_store_id:
    #             # Fetch store details
    #             ho_ip = store.nhcl_terminal_ip
    #             ho_port = store.nhcl_port_no
    #             ho_api_key = store.nhcl_api_key
    #             user_tz = self.env.user.tz or pytz.utc
    #             local = pytz.timezone(user_tz)
    #
    #             # Ensure from_date and to_date include time (00:00:00 to 23:59:59)
    #             from_date_local = datetime.strptime(str(self.from_date), DEFAULT_SERVER_DATETIME_FORMAT)
    #             from_date_local = local.localize(from_date_local.replace(hour=0, minute=0, second=0))
    #
    #             to_date_local = datetime.strptime(str(self.to_date), DEFAULT_SERVER_DATETIME_FORMAT)
    #             to_date_local = local.localize(to_date_local.replace(hour=23, minute=59, second=59))
    #
    #             # Format the localized dates in the appropriate string format
    #             from_date_str = from_date_local.strftime("%Y-%m-%dT%H:%M:%S")
    #             to_date_str = to_date_local.strftime("%Y-%m-%dT%H:%M:%S")
    #
    #             # Apply the date filter and construct domain string
    #             store_date_entry_domain = [
    #                 ('payment_date', '>=', from_date_str),
    #                 ('payment_date', '<=', to_date_str),
    #             ]
    #
    #             # Convert domain to a string for query parameters, ensuring the domain is a properly formatted string
    #             domain_str = str(store_date_entry_domain).replace("'", "\"")
    #
    #             # Construct the API endpoint URL for pos.payment with the domain filter
    #             pos_payment_url = f"http://{ho_ip}:{ho_port}/api/pos.payment/search?domain={domain_str}"
    #
    #             headers_source = {
    #                 'api-key': ho_api_key,
    #                 'Content-Type': 'application/json'
    #             }
    #
    #             try:
    #                 # Make the API call to get pos.payment data with the domain filter
    #                 response = requests.get(pos_payment_url, headers=headers_source)
    #                 response.raise_for_status()  # Raise exception for HTTP error responses
    #                 response_data = response.json()
    #
    #                 # Check if the 'data' key exists in the response
    #                 if 'data' not in response_data:
    #                     continue
    #
    #                 payments = response_data['data']
    #                 start_date = self.from_date
    #                 end_date = self.to_date
    #
    #                 # Group payments by payment method
    #                 from collections import defaultdict
    #                 grouped_payments = defaultdict(float)
    #
    #                 for payment in payments:
    #                     # Safely access 'payment_method_id' field
    #                     method_field = payment.get('payment_method_id', [])
    #                     if isinstance(method_field, list) and method_field:
    #                         payment_method_name = method_field[0].get('name', 'Unknown')
    #                     elif isinstance(method_field, dict):
    #                         payment_method_name = method_field.get('name', 'Unknown')
    #                     else:
    #                         payment_method_name = "Unknown"
    #
    #                     grouped_payments[payment_method_name] += payment.get('amount', 0)
    #
    #                 # Determine company name from the first payment record (if available)
    #                 company_name = "Unknown"
    #                 if payments:
    #                     company_field = payments[0].get('company_id', [])
    #                     if isinstance(company_field, list) and company_field:
    #                         company_name = company_field[0].get('name', 'Unknown')
    #
    #                 additional_data = {
    #                     'report_data': dict(grouped_payments),
    #                     'start_date': start_date,
    #                     'end_date': end_date,
    #                     'company_name': company_name,
    #                 }
    #
    #                 report_list.append(additional_data)
    #
    #             except requests.exceptions.RequestException as e:
    #                 print(f"Failed to retrieve POS payments for store {store.nhcl_store_name.name}: {e}")
    #
    #     except Exception as outer_e:
    #         print("General error in payment report retrieval:", outer_e)
    #
    #     # Define the final data dictionary outside the try blocks
    #     final_data = {'doc': report_list}  # Change 'report_listss' to 'doc'
    #
    #
    #     return self.env.ref('nhcl_ho_store_cmr_integration.report_pos_mop_pdfsss').report_action(self, data=final_data)

    # def get_grouped_payments(self):
    #     report_list = []
    #     try:
    #         for store in self.nhcl_store_id:
    #             # Fetch store details
    #             ho_ip = store.nhcl_terminal_ip
    #             ho_port = store.nhcl_port_no
    #             ho_api_key = store.nhcl_api_key
    #             user_tz = self.env.user.tz or pytz.utc
    #             local = pytz.timezone(user_tz)
    #
    #             # Ensure from_date and to_date include time (00:00:00 to 23:59:59)
    #             from_date_local = datetime.strptime(str(self.from_date), DEFAULT_SERVER_DATETIME_FORMAT)
    #             from_date_local = local.localize(from_date_local.replace(hour=0, minute=0, second=0))
    #
    #             to_date_local = datetime.strptime(str(self.to_date), DEFAULT_SERVER_DATETIME_FORMAT)
    #             to_date_local = local.localize(to_date_local.replace(hour=23, minute=59, second=59))
    #
    #             # Format the localized dates in the appropriate string format
    #             from_date_str = datetime.strftime(
    #                 pytz.utc.localize(
    #                     datetime.strptime(str(self.from_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(local),
    #                 "%Y-%m-%d %H:%M:%S")
    #             to_date_str = datetime.strftime(
    #                 pytz.utc.localize(datetime.strptime(str(self.to_date), DEFAULT_SERVER_DATETIME_FORMAT)).astimezone(
    #                     local),
    #                 "%Y-%m-%d %H:%M:%S")
    #
    #             # Apply the date filter and construct domain string
    #             store_date_entry_domain = [
    #                 ('payment_date', '>=', from_date_str),
    #                 ('payment_date', '<=', to_date_str),
    #             ]
    #
    #             store_date_entry_domain_invoice = [
    #                 ('create_date', '>=', from_date_str),
    #                 ('create_date', '<=', to_date_str),
    #                 ('move_type', 'in', ['out_refund', 'in_refund'])
    #
    #             ]
    #
    #             # Convert domain to a string for query parameters, ensuring the domain is a properly formatted string
    #             domain_str = str(store_date_entry_domain).replace("'", "\"")
    #             invoice_domain_str = str(store_date_entry_domain_invoice).replace("'", "\"")
    #
    #             # Construct the API endpoint URL for pos.payment with the domain filter
    #             pos_payment_url = f"http://{ho_ip}:{ho_port}/api/pos.payment/search?domain={domain_str}"
    #             invoice_url = f"http://{ho_ip}:{ho_port}/api/account.move/search?domain={invoice_domain_str}"
    #
    #             headers_source = {
    #                 'api-key': ho_api_key,
    #                 'Content-Type': 'application/json'
    #             }
    #
    #             try:
    #                 from collections import defaultdict
    #
    #                 # 1. Fetch POS payment data
    #                 response = requests.get(pos_payment_url, headers=headers_source)
    #                 response.raise_for_status()
    #                 response_data = response.json()
    #
    #                 # 2. Fetch account.move (invoices / credit notes)
    #                 response2 = requests.get(invoice_url, headers=headers_source)
    #                 response2.raise_for_status()
    #                 response_data2 = response2.json()
    #
    #                 # Skip if no data in payments
    #                 if 'data' not in response_data:
    #                     report_list.append({})
    #                     return
    #
    #                 payments = response_data['data']
    #                 start_date = from_date_str
    #                 end_date = to_date_str
    #
    #                 # 3. Group payments by payment method
    #                 grouped_payments = defaultdict(float)
    #
    #                 for payment in payments:
    #                     method_field = payment.get('payment_method_id', [])
    #                     if isinstance(method_field, list) and method_field:
    #                         payment_method_name = method_field[0].get('name', 'Unknown')
    #                     elif isinstance(method_field, dict):
    #                         payment_method_name = method_field.get('name', 'Unknown')
    #                     else:
    #                         payment_method_name = "Unknown"
    #
    #                     grouped_payments[payment_method_name] += payment.get('amount', 0)
    #
    #                 # 4. Compute credit note totals per company
    #                 credit_notes_by_company = defaultdict(float)
    #                 for rec in response_data2.get('data', []):
    #                     move_type = rec.get('move_type')
    #                     if move_type in ['out_refund', 'in_refund']:  # only credit notes
    #                         company_field = rec.get('company_id', [])
    #                         if isinstance(company_field, list) and company_field:
    #                             company_name_cn = company_field[0].get('name', 'Unknown')
    #                         elif isinstance(company_field, dict):
    #                             company_name_cn = company_field.get('name', 'Unknown')
    #                         else:
    #                             company_name_cn = "Unknown"
    #
    #                         credit_notes_by_company[company_name_cn] += rec.get('amount_total_signed', 0.0)
    #
    #                 # 5. Determine company for this batch
    #                 company_name = "Unknown"
    #                 if payments:
    #                     company_field = payments[0].get('company_id', [])
    #                     if isinstance(company_field, list) and company_field:
    #                         company_name = company_field[0].get('name', 'Unknown')
    #                     elif isinstance(company_field, dict):
    #                         company_name = company_field.get('name', 'Unknown')
    #
    #                 # 6. Add Credit Notes into grouped payments (update existing or create)
    #                 company_credit_total = credit_notes_by_company.get(company_name, 0.0)
    #                 grouped_payments["Credit Notes"] = grouped_payments.get("Credit Notes", 0.0) + company_credit_total
    #
    #                 # 7. Build final report dictionary
    #                 additional_data = {
    #                     'report_data': dict(grouped_payments),
    #                     'start_date': start_date,
    #                     'end_date': end_date,
    #                     'company_name': company_name,
    #                 }
    #
    #                 report_list.append(additional_data)
    #
    #
    #             except requests.exceptions.RequestException as e:
    #                 print(f"Failed to retrieve POS payments for store {store.nhcl_store_name.name}: {e}")
    #
    #     except Exception as outer_e:
    #         print("General error in payment report retrieval:", outer_e)
    #
    #     # Define the final data dictionary outside the try blocks
    #     final_data = {'doc': report_list}
    #     # print(final_data)# Change 'report_listss' to 'doc'
    #
    #     return self.env.ref('nhcl_ho_store_cmr_integration.report_pos_mop_pdfsss').report_action(self, data=final_data)

    @api.constrains('from_date', 'to_date')
    def _check_dates(self):
        for record in self:
            if record.from_date and record.to_date and record.to_date < record.from_date:
                raise ValidationError(
                    "The 'To Date' cannot be earlier than the 'From Date'."
                )

    def get_grouped_payments_in_excel(self):
        report_list = []
        distinct_payment_methods = set()  # Set to store unique payment methods

        try:
            for store in self.nhcl_store_id:
                # Fetch store details
                ho_ip = store.nhcl_terminal_ip
                ho_port = store.nhcl_port_no
                ho_api_key = store.nhcl_api_key
                user_tz = self.env.user.tz or pytz.utc
                local = pytz.timezone(user_tz)

                # Format dates as YYYY-MM-DD
                # Ensure from_date and to_date include time (00:00:00 to 23:59:59)
                from_date_local = datetime.strptime(str(self.from_date), DEFAULT_SERVER_DATETIME_FORMAT)
                from_date_local = local.localize(from_date_local.replace(hour=0, minute=0, second=0))

                to_date_local = datetime.strptime(str(self.to_date), DEFAULT_SERVER_DATETIME_FORMAT)
                to_date_local = local.localize(to_date_local.replace(hour=23, minute=59, second=59))

                # Format the localized dates in the appropriate string format
                from_date_str = from_date_local.strftime("%Y-%m-%dT%H:%M:%S")
                to_date_str = to_date_local.strftime("%Y-%m-%dT%H:%M:%S")

                # Apply the date filter and construct domain string
                store_date_entry_domain = [
                    ('payment_date', '>=', from_date_str),
                    ('payment_date', '<=', to_date_str),
                ]

                # Convert domain to a string for query parameters, ensuring the domain is a properly formatted string
                domain_str = str(store_date_entry_domain).replace("'", "\"")

                # Construct the API endpoint URL for pos.payment with the domain filter
                pos_payment_url = f"http://{ho_ip}:{ho_port}/api/pos.payment/search?domain={domain_str}"

                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }

                try:
                    # Make the API call to get pos.payment data with the domain filter
                    response = requests.get(pos_payment_url, headers=headers_source)
                    response.raise_for_status()  # Raise exception for HTTP error responses
                    response_data = response.json()

                    # If the response is a dict, extract values; otherwise, assume it's a list.
                    if isinstance(response_data, dict):
                        payments = response_data.get('data', [])
                        start_date = self.from_date
                        end_date = self.to_date
                    else:
                        payments = response_data
                        start_date = ""
                        end_date = ""

                    # Group payments by payment method.
                    grouped_payments = defaultdict(float)
                    for payment in payments:
                        # 'payment_method_id' is expected to be a list with one dictionary inside.
                        method_field = payment['payment_method_id']
                        if isinstance(method_field, list) and len(method_field) > 0:
                            payment_method_name = method_field[0]['name']
                        elif isinstance(method_field, dict):
                            payment_method_name = method_field['name']
                        else:
                            payment_method_name = "Unknown"

                        # Add the payment method to the set of distinct methods
                        distinct_payment_methods.add(payment_method_name)
                        grouped_payments[payment_method_name] += payment['amount']

                    # Add the store name and other required fields to the report data
                    additional_data = {
                        'store_name': store.nhcl_store_name.name,  # Add store name here
                        'bill_type': "POS BILL",  # You can customize this if needed
                        'grouped_payments': dict(grouped_payments),
                        'start_date': start_date,
                        'end_date': end_date,
                    }

                    report_list.append(additional_data)

                except requests.exceptions.RequestException as e:
                    print(f"Failed to retrieve POS payments for store {store.nhcl_store_name.name}: {e}")

        except Exception as outer_e:
            print("General error in payment report retrieval:", outer_e)

        # Create an Excel file in memory
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet('POS Payment Grouped Report')

        bold = workbook.add_format({'bold': True})

        # Convert the distinct payment methods to a sorted list
        payment_methods = sorted(distinct_payment_methods)

        # Write headers dynamically
        headers = ['Site', 'Bill Type'] + payment_methods + ['Grand Total']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        row = 1
        for line in report_list:
            # Start by writing the site and bill type
            worksheet.write(row, 0, line['store_name'])
            worksheet.write(row, 1, line['bill_type'])

            total_amount = 0
            # Write payment methods dynamically based on the unique payment methods
            for col_num, payment_method in enumerate(payment_methods, start=2):
                amount = line['grouped_payments'].get(payment_method, 0.0)
                worksheet.write(row, col_num, amount)
                total_amount += amount

            # Write the Grand Total for the row
            worksheet.write(row, len(payment_methods) + 2, total_amount)

            row += 1

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
            'name': f'POS_Grouped_Payments_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'POS_Grouped_Payments_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


    def action_summery_mop_detailed_report(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': ' Mode Of Payment Report',
            'res_model': 'pos.mop.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('pos_mop_report_id', '=', self.id)],
            'context': {
                'default_pos_mop_report_id': self.id
            }
        }

    def get_mop_payments(self):
        try:
            self.ensure_one()  # wizard safety

            from_date = fields.Datetime.to_datetime(self.from_date)
            to_date = fields.Datetime.to_datetime(self.to_date)

            # Clear old lines
            self.pos_mop_report_ids = [(5, 0, 0)]
            line_vals = []

            # Loop each selected store (Many2many)
            for store in self.nhcl_store_id:

                company_id = store.nhcl_store_name.company_id.id

                # POS Payments
                payments = self.env['pos.payment'].search([
                    ('payment_date', '>=', from_date),
                    ('payment_date', '<=', to_date),
                    ('pos_order_id.company_id', '=', company_id)
                ])

                # Credit Notes
                credit_moves = self.env['account.move'].search([
                    ('create_date', '>=', from_date),
                    ('create_date', '<=', to_date),
                    ('move_type', 'in', ['out_refund', 'in_refund']),
                    ('company_id', '=', company_id)
                ])

                # Initialize totals
                cash = axis = hdfc = kotak = paytm = 0.0
                sbi = bajaj = mobikwik = cheque = 0.0
                gift_voucher = credit_note_settlement = 0.0

                # Group by payment method
                for payment in payments:
                    method_name = (payment.payment_method_id.name or '').lower()

                    if method_name == 'cash':
                        cash += payment.amount
                    elif method_name == 'axis':
                        axis += payment.amount
                    elif method_name == 'hdfc':
                        hdfc += payment.amount
                    elif method_name == 'kotak':
                        kotak += payment.amount
                    elif method_name == 'paytm':
                        paytm += payment.amount
                    elif method_name == 'sbi':
                        sbi += payment.amount
                    elif method_name == 'bajaj':
                        bajaj += payment.amount
                    elif method_name == 'mobikwik':
                        mobikwik += payment.amount
                    elif method_name == 'cheque':
                        cheque += payment.amount
                    elif method_name == 'gift voucher':
                        gift_voucher += payment.amount

                # Credit Note Settlement
                credit_note_settlement = sum(
                    credit_moves.mapped('amount_total_signed')
                )

                grand_total = (
                        cash + axis + hdfc + kotak + paytm +
                        sbi + bajaj + mobikwik + cheque +
                        gift_voucher + credit_note_settlement
                )

                # Append line
                line_vals.append((0, 0, {
                    'nhcl_company_id': store.nhcl_store_name.company_id.id,
                    'cash': cash,
                    'axis': axis,
                    'hdfc': hdfc,
                    'kotak': kotak,
                    'paytm': paytm,
                    'sbi': sbi,
                    'bajaj': bajaj,
                    'mobikwik': mobikwik,
                    'cheque': cheque,
                    'gift_voucher': gift_voucher,
                    'credit_note_settlement': credit_note_settlement,
                    'grand_total': grand_total,
                    'pos_mop_report_id': self.id
                }))

            # Write one2many lines
            self.write({'pos_mop_report_ids': line_vals})

            return True

        except Exception as e:
            print("Error in MOP report")
            return {'type': 'ir.actions.act_window_close'}




class PosMOPReportline(models.TransientModel):
    _name = 'pos.mop.report.line'
    _description = 'POS MOP Report Line'

    pos_mop_report_id = fields.Many2one('pos.mop.report.wizard', 'MOP Report Line')
    nhcl_company_id = fields.Many2one('res.company', string='Store Name')
    cash = fields.Float(string='Cash')
    axis = fields.Float(string='Axis')
    hdfc = fields.Float(string='HDFC')
    kotak = fields.Float(string='Kotak')
    paytm = fields.Float(string='Paytm')
    sbi = fields.Float(string='SBI')
    bajaj = fields.Float(string='Bajaj')
    mobikwik = fields.Float(string='Mobikwik')
    cheque = fields.Float(string='Cheque')
    gift_voucher = fields.Float(string='Gift Voucher')
    credit_note_settlement = fields.Float(string='Credit Note Settlement')
    grand_total = fields.Float(string='Grand Total')
