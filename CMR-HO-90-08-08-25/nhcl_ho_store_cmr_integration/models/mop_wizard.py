from odoo import models,fields,api,_
import requests
from datetime import datetime
import pytz

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

    from_date = fields.Datetime('From Date')
    to_date = fields.Datetime('To Date')
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company')

    def get_grouped_payments(self):
        report_list = []
        try:
            for store in self.nhcl_store_id:
                # Fetch store details
                ho_ip = store.nhcl_terminal_ip
                ho_port = store.nhcl_port_no
                ho_api_key = store.nhcl_api_key
                user_tz = self.env.user.tz or pytz.utc
                local = pytz.timezone(user_tz)

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

                    # Check if the 'data' key exists in the response
                    if 'data' not in response_data:
                        continue

                    payments = response_data['data']
                    start_date = self.from_date
                    end_date = self.to_date

                    # Group payments by payment method
                    from collections import defaultdict
                    grouped_payments = defaultdict(float)

                    for payment in payments:
                        # Safely access 'payment_method_id' field
                        method_field = payment.get('payment_method_id', [])
                        if isinstance(method_field, list) and method_field:
                            payment_method_name = method_field[0].get('name', 'Unknown')
                        elif isinstance(method_field, dict):
                            payment_method_name = method_field.get('name', 'Unknown')
                        else:
                            payment_method_name = "Unknown"

                        grouped_payments[payment_method_name] += payment.get('amount', 0)

                    # Determine company name from the first payment record (if available)
                    company_name = "Unknown"
                    if payments:
                        company_field = payments[0].get('company_id', [])
                        if isinstance(company_field, list) and company_field:
                            company_name = company_field[0].get('name', 'Unknown')

                    additional_data = {
                        'report_data': dict(grouped_payments),
                        'start_date': start_date,
                        'end_date': end_date,
                        'company_name': company_name,
                    }

                    report_list.append(additional_data)

                except requests.exceptions.RequestException as e:
                    print(f"Failed to retrieve POS payments for store {store.nhcl_store_name.name}: {e}")

        except Exception as outer_e:
            print("General error in payment report retrieval:", outer_e)

        # Define the final data dictionary outside the try blocks
        final_data = {'doc': report_list}  # Change 'report_listss' to 'doc'


        return self.env.ref('nhcl_ho_store_cmr_integration.report_pos_mop_pdfsss').report_action(self, data=final_data)



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
