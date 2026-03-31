from odoo import models, fields, api, _
import requests
from datetime import datetime
import pytz
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io
import xlsxwriter
from odoo.fields import Datetime


class PoslfbReportWizard(models.TransientModel):
    _name = 'pos.lfb.report.wizard'
    _description = 'POS lfb Report Wizard'

    from_date = fields.Datetime('From Date')
    to_date = fields.Datetime('To Date')

    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company')

    DEFAULT_SERVER_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    def get_last_first_bill_num(self):

        report_list = []

        try:
            # User timezone
            user_tz = pytz.timezone(self.env.user.tz or 'Asia/Kolkata')

            # Convert user datetime → UTC for API
            from_date_utc = Datetime.context_timestamp(
                self, self.from_date
            ).astimezone(pytz.UTC)

            to_date_utc = Datetime.context_timestamp(
                self, self.to_date
            ).astimezone(pytz.UTC)

            # API must receive UTC
            from_date_str = from_date_utc.strftime("%d/%m/%y %H:%M:%S")
            to_date_str = to_date_utc.strftime("%d/%m/%y %H:%M:%S")

            for store in self.nhcl_store_id:
                ho_ip = store.nhcl_terminal_ip
                ho_port = store.nhcl_port_no
                ho_api_key = store.nhcl_api_key

                domain = [
                    ('date_order', '>=', from_date_str),
                    ('date_order', '<=', to_date_str),
                    ('state', 'in', ['paid', 'done'])
                ]

                domain_str = str(domain).replace("'", "\"")

                url = (
                    f"http://{ho_ip}:{ho_port}/api/pos.order/search"
                    f"?domain={domain_str}"
                )

                headers = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }

                first_bill_no = last_bill_no = 'N/A'

                try:
                    response = requests.get(url, headers=headers, timeout=30)
                    response.raise_for_status()

                    data = response.json().get('data', [])

                    bill_numbers = [
                        rec.get('name') for rec in data if rec.get('name')
                    ]

                    if bill_numbers:
                        first_bill_no = min(bill_numbers)
                        last_bill_no = max(bill_numbers)

                except requests.exceptions.RequestException:
                    first_bill_no = last_bill_no = 'API Error'

                report_list.append({
                    'store_name': store.nhcl_store_name.name,
                    'first_bill_no': first_bill_no,
                    'last_bill_no': last_bill_no,
                    # Display dates in user timezone
                    'start_date': Datetime.context_timestamp(
                        self, self.from_date
                    ).strftime("%d/%m/%y %H:%M:%S"),
                    'end_date': Datetime.context_timestamp(
                        self, self.to_date
                    ).strftime("%d/%m/%y %H:%M:%S"),
                })

            return self.env.ref(
                'nhcl_ho_store_cmr_integration.report_pos_lfb_pdfsss'
            ).report_action(self, data={'doc': report_list})

        except Exception:
            return {'doc': []}

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