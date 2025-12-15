from odoo import models, fields, api, _
import requests
from datetime import datetime
import pytz
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io
import xlsxwriter


class PoslfbReportWizard(models.TransientModel):
    _name = 'pos.lfb.report.wizard'
    _description = 'POS lfb Report Wizard'

    from_date = fields.Datetime('From Date')
    to_date = fields.Datetime('To Date')

    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company')

    DEFAULT_SERVER_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    def get_last_first_bill_num(self):
        """
        Fetches the first and last bill numbers for POS orders from an external API
        for each store, based on the provided date range, state, and domain.
        """
        report_list = []

        try:
            # Loop through each store (assuming self.nhcl_store_id holds the stores)
            for store in self.nhcl_store_id:
                # Store details
                ho_ip = store.nhcl_terminal_ip
                ho_port = store.nhcl_port_no
                ho_api_key = store.nhcl_api_key
                user_tz = self.env.user.tz or pytz.utc
                local = pytz.timezone(user_tz)

                # Format dates as YYYY-MM-DD
                from_date_local = datetime.strptime(str(self.from_date), DEFAULT_SERVER_DATETIME_FORMAT)
                from_date_local = local.localize(from_date_local.replace(hour=0, minute=0, second=0))

                to_date_local = datetime.strptime(str(self.to_date), DEFAULT_SERVER_DATETIME_FORMAT)
                to_date_local = local.localize(to_date_local.replace(hour=23, minute=59, second=59))

                # Format the localized dates in the appropriate string format
                from_date_str = from_date_local.strftime("%Y-%m-%dT%H:%M:%S")
                to_date_str = to_date_local.strftime("%Y-%m-%dT%H:%M:%S")

                # Construct the domain for filtering POS orders
                store_date_entry_domain = [
                    ('date_order', '>=', from_date_str),
                    ('date_order', '<=', to_date_str),
                    ('state', 'in', ['paid', 'done'])  # Only include 'paid' or 'done' states
                ]

                # Convert domain to string for query parameters
                domain_str = str(store_date_entry_domain).replace("'", "\"")  # Replace single quotes with double quotes

                # Construct the API endpoint URL for pos.order
                pos_orders_url = f"http://{ho_ip}:{ho_port}/api/pos.order/search?domain={domain_str}"

                headers = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }

                try:
                    # Make the API call to get pos.order data with the domain filter
                    response = requests.get(pos_orders_url, headers=headers)
                    response.raise_for_status()  # Raise exception for HTTP errors
                    response_data = response.json()  # Parse the JSON response

                    # Fetch the tracking numbers from the orders and filter out None values
                    print("LFB",response_data.get('data', []))
                    tracking_numbers = [order.get('name') for order in response_data.get('data', [])]
                    tracking_numbers = [num for num in tracking_numbers if num is not None]  # Remove None values

                    # Determine the first and last bill number
                    if tracking_numbers:
                        first_bill_no = min(tracking_numbers)
                        last_bill_no = max(tracking_numbers)
                    else:
                        first_bill_no = last_bill_no = 'N/A'  # No tracking numbers found
                except requests.exceptions.RequestException as e:
                    first_bill_no = last_bill_no = 'API Error'

                # Prepare the report data for this store
                report_data = {
                    'store_name': store.nhcl_store_name.name,
                    'first_bill_no': first_bill_no,
                    'last_bill_no': last_bill_no,
                    'start_date': from_date_str,
                    'end_date': to_date_str,
                }

                # Add the report data for the store to the report list
                report_list.append(report_data)

            # Return the final result

            final_data = {'doc': report_list}
            return self.env.ref('nhcl_ho_store_cmr_integration.report_pos_lfb_pdfsss').report_action(self, data=final_data)

        except Exception as outer_e:
            return {'doc': []}  # Return empty result in case of error

    def get_last_first_bill_num_in_excel(self):
        """
        Fetches the first and last bill numbers for POS orders from an external API
        for each store, based on the provided date range, state, and domain.
        """
        report_list = []

        try:
            # Loop through each store (assuming self.nhcl_store_id holds the stores)
            for store in self.nhcl_store_id:
                # Store details
                ho_ip = store.nhcl_terminal_ip
                ho_port = store.nhcl_port_no
                ho_api_key = store.nhcl_api_key
                user_tz = self.env.user.tz or pytz.utc
                local = pytz.timezone(user_tz)

                # Format dates as YYYY-MM-DD
                from_date_str = datetime.strftime(
                    pytz.utc.localize(
                        datetime.strptime(str(self.from_date), self.DEFAULT_SERVER_DATETIME_FORMAT)
                    ).astimezone(local),
                    "%Y-%m-%d"
                )
                to_date_str = datetime.strftime(
                    pytz.utc.localize(
                        datetime.strptime(str(self.to_date), self.DEFAULT_SERVER_DATETIME_FORMAT)
                    ).astimezone(local),
                    "%Y-%m-%d"
                )

                # Construct the domain for filtering POS orders
                store_date_entry_domain = [
                    ('date_order', '>=', from_date_str),
                    ('date_order', '<=', to_date_str),
                    ('state', 'in', ['paid', 'done'])  # Only include 'paid' or 'done' states
                ]

                domain_str = str(store_date_entry_domain).replace("'", "\"")

                pos_orders_url = f"http://{ho_ip}:{ho_port}/api/pos.order/search?domain={domain_str}"

                headers = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }

                try:
                    response = requests.get(pos_orders_url, headers=headers)
                    response.raise_for_status()
                    response_data = response.json()

                    tracking_numbers = [order.get('tracking_number') for order in response_data.get('data', [])]
                    tracking_numbers = [num for num in tracking_numbers if num is not None]

                    if tracking_numbers:
                        first_bill_no = min(tracking_numbers)
                        last_bill_no = max(tracking_numbers)
                    else:
                        first_bill_no = last_bill_no = 'N/A'
                except requests.exceptions.RequestException as e:
                    first_bill_no = last_bill_no = 'API Error'

                # Prepare the report data for this store
                report_data = {
                    'store_name': store.nhcl_store_name.name,
                    'first_bill_no': first_bill_no,
                    'last_bill_no': last_bill_no,
                    'start_date': from_date_str,
                    'end_date': to_date_str,
                }

                report_list.append(report_data)

            # Create an Excel file in memory
            buffer = io.BytesIO()
            workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
            worksheet = workbook.add_worksheet('POS Bill Numbers')

            # Add headers
            worksheet.write(0, 0, 'Store', workbook.add_format({'bold': True}))
            worksheet.write(0, 1, 'First Bill Number', workbook.add_format({'bold': True}))
            worksheet.write(0, 2, 'Last Bill Number', workbook.add_format({'bold': True}))
            worksheet.write(0, 3, 'From Date', workbook.add_format({'bold': True}))
            worksheet.write(0, 4, 'To Date', workbook.add_format({'bold': True}))

            # Add data rows
            row = 1
            for line in report_list:
                worksheet.write(row, 0, line['store_name'])
                worksheet.write(row, 1, line['first_bill_no'])
                worksheet.write(row, 2, line['last_bill_no'])
                worksheet.write(row, 3, line['start_date'])
                worksheet.write(row, 4, line['end_date'])
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
                'name': f'POS_Bill_Numbers_Report_{fields.Date.today()}.xlsx',
                'type': 'binary',
                'datas': encoded_data,
                'store_fname': f'POS_Bill_Numbers_Report_{fields.Date.today()}.xlsx',
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            })

            # Return the action to download the file
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'new',
            }
        except Exception as e:
            # Handle any errors and return empty data
            return {'doc': []}  # Return empty result in case of error