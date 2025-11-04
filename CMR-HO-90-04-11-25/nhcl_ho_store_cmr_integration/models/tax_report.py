from odoo import models,fields,api,_
import requests
from datetime import datetime
import pytz
import re


import xmlrpc.client


from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from odoo.http import  request

from collections import defaultdict


class PosTaxReportWizard(models.TransientModel):
    _name = 'pos.tax.report.wizard'
    _description = 'POS tax Report Wizard'

    from_date = fields.Datetime('From Date')
    to_date = fields.Datetime('To Date')

    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company')




    DEFAULT_SERVER_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

    def get_taxed_data(self):
        """
        Fetches taxed data from the external API for pos.order.line,
        filters based on domain (create_date, state, and from_date_str, to_date_str),
        and computes tax-related information.
        """
        report_list = []
        try:
            for store in self.nhcl_store_id:
                # Fetch store details
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

                # Construct the domain for filtering
                store_date_entry_domain = [
                    ('create_date', '>=', from_date_str),
                    # Filter by create_date (greater than or equal to from_date_str)
                    ('create_date', '<=', to_date_str),  # Filter by create_date (less than or equal to to_date_str)
                    ('order_id.state', 'in', ['paid', 'done'])  # Filter by order state (only 'paid' or 'done')
                ]

                # Convert domain to a string for query parameters
                domain_str = str(store_date_entry_domain).replace("'", "\"")  # Replace single quotes with double quotes

                # Construct the API endpoint URL for pos.order.line with the domain filter
                pos_order_lines_url = f"http://{ho_ip}:{ho_port}/api/pos.order.line/search?domain={domain_str}"

                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }

                try:
                    # Make the API call to get pos.order.line data with the domain filter
                    response = requests.get(pos_order_lines_url, headers=headers_source)
                    response.raise_for_status()  # Raise exception for HTTP error responses
                    response_data = response.json()  # Parse the JSON response

                    # Process the response data
                    tax_data = defaultdict(
                        lambda: {'taxable_amt': 0, 'tax_amt': 0, 'cgst_amt': 0, 'sgst_amt': 0, 'igst_amt': 0})

                    for line in response_data.get('data', []):  # Use 'data' key from the API response
                        taxable_amt = line.get('price_subtotal', 0)  # Taxable amount is the price before tax

                        # Loop through all the tax_ids for the order line
                        for tax in line.get('tax_ids', []):
                            tax_name = tax.get('name', '')
                            match = re.search(r'(\d+)%', tax_name)
                            if match:
                                tax_rate = int(match.group(1))  # Extract the number before '%' and convert to integer
                            else:
                                tax_rate = 0  # Default to 0 if no percentage is found


                            # Add taxable amount and tax amount to the corresponding tax rate
                            tax_data[tax_rate]['taxable_amt'] += taxable_amt
                            tax_data[tax_rate]['tax_amt'] += taxable_amt * tax_rate / 100

                            # Compute CGST and SGST for applicable GST rates
                            if tax_rate in [3, 5, 12, 18, 28]:  # For GST rates
                                tax_data[tax_rate][
                                    'cgst_amt'] += taxable_amt * tax_rate / 200  # CGST is half of the total tax
                                tax_data[tax_rate][
                                    'sgst_amt'] += taxable_amt * tax_rate / 200  # SGST is half of the total tax
                            else:
                                # For non-GST taxes, assume IGST is the full tax amount
                                tax_data[tax_rate]['igst_amt'] += taxable_amt * tax_rate / 100

                    # Prepare the final report data
                    report_data = []
                    for tax_rate, data in tax_data.items():
                        report_data.append({
                            'tax_percent': tax_rate,
                            'taxable_amt': data['taxable_amt'],
                            'cgst_amt': data['cgst_amt'],
                            'sgst_amt': data['sgst_amt'],
                            'igst_amt': data['igst_amt'],
                            'tax_amt': data['tax_amt'],  # Total tax amount
                        })

                    # Add the processed data to the report list
                    report_list.append({
                        'store_name': store.nhcl_store_name.name,
                        'report_data': report_data,
                        'start_date': from_date_str,
                        'end_date': to_date_str,
                    })

                except requests.exceptions.RequestException as e:
                    print(f"Failed to retrieve pos.order.line data for store {store.nhcl_store_name.name}: {e}")

        except Exception as outer_e:
            print("General error in tax report retrieval:", outer_e)

        # Define the final data dictionary
        final_data = {'doc': report_list}



        # Return the final data
        return self.env.ref('nhcl_ho_store_cmr_integration.report_pos_tax_pdfsss').report_action(self, data=final_data)


    def get_taxed_data_in_excel(self):
        """
        Fetches taxed data from the external API for pos.order.line,
        filters based on domain (create_date, state, and from_date_str, to_date_str),
        and computes tax-related information.
        """
        report_list = []
        try:
            for store in self.nhcl_store_id:
                # Fetch store details
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

                # Construct the domain for filtering
                store_date_entry_domain = [
                    ('create_date', '>=', from_date_str),
                    ('create_date', '<=', to_date_str),
                    ('order_id.state', 'in', ['paid', 'done'])
                ]

                # Convert domain to a string for query parameters
                domain_str = str(store_date_entry_domain).replace("'", "\"")

                # Construct the API endpoint URL for pos.order.line with the domain filter
                pos_order_lines_url = f"http://{ho_ip}:{ho_port}/api/pos.order.line/search?domain={domain_str}"

                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }

                try:
                    # Make the API call to get pos.order.line data with the domain filter
                    response = requests.get(pos_order_lines_url, headers=headers_source)
                    response.raise_for_status()  # Raise exception for HTTP error responses
                    response_data = response.json()

                    # Process the response data
                    tax_data = defaultdict(
                        lambda: {'taxable_amt': 0, 'tax_amt': 0, 'cgst_amt': 0, 'sgst_amt': 0, 'igst_amt': 0})

                    for line in response_data.get('data', []):  # Use 'data' key from the API response
                        taxable_amt = line.get('price_subtotal', 0)  # Taxable amount is the price before tax

                        # Loop through all the tax_ids for the order line
                        for tax in line.get('tax_ids', []):
                            tax_name = tax.get('name', '')
                            match = re.search(r'(\d+)%', tax_name)
                            if match:
                                tax_rate = int(match.group(1))  # Extract the number before '%' and convert to integer
                            else:
                                tax_rate = 0  # Default to 0 if no percentage is found

                            # Add taxable amount and tax amount to the corresponding tax rate
                            tax_data[tax_rate]['taxable_amt'] += taxable_amt
                            tax_data[tax_rate]['tax_amt'] += taxable_amt * tax_rate / 100

                            # Compute CGST and SGST for applicable GST rates
                            if tax_rate in [3, 5, 12, 18, 28]:  # For GST rates
                                tax_data[tax_rate][
                                    'cgst_amt'] += taxable_amt * tax_rate / 200  # CGST is half of the total tax
                                tax_data[tax_rate][
                                    'sgst_amt'] += taxable_amt * tax_rate / 200  # SGST is half of the total tax
                            else:
                                # For non-GST taxes, assume IGST is the full tax amount
                                tax_data[tax_rate]['igst_amt'] += taxable_amt * tax_rate / 100

                    # Prepare the final report data
                    report_data = []
                    for tax_rate, data in tax_data.items():
                        report_data.append({
                            'tax_percent': tax_rate,
                            'taxable_amt': data['taxable_amt'],
                            'cgst_amt': data['cgst_amt'],
                            'sgst_amt': data['sgst_amt'],
                            'igst_amt': data['igst_amt'],
                            'tax_amt': data['tax_amt'],
                        })

                    # Add the processed data to the report list
                    report_list.append({
                        'store_name': store.nhcl_store_name.name,
                        'report_data': report_data,
                        'start_date': from_date_str,
                        'end_date': to_date_str,
                    })

                except requests.exceptions.RequestException as e:
                    print(f"Failed to retrieve pos.order.line data for store {store.nhcl_store_name.name}: {e}")

        except Exception as outer_e:
            print("General error in tax report retrieval:", outer_e)

        # Create an Excel file in memory
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet('POS Tax Report')

        bold = workbook.add_format({'bold': True})

        # Write headers for the Excel report
        headers = ['Store', 'Tax %', 'Taxable Amount', 'CGST Amount', 'SGST Amount', 'IGST Amount', 'Total Tax Amount']
        worksheet.write_row(0, 0, headers, bold)

        row = 1
        grand_totals = {
            'taxable_amt': 0,
            'cgst_amt': 0,
            'sgst_amt': 0,
            'igst_amt': 0,
            'tax_amt': 0
        }

        # Write data for each store and tax rate
        for store_data in report_list:
            for line in store_data['report_data']:
                worksheet.write(row, 0, store_data['store_name'])
                worksheet.write(row, 1, line['tax_percent'])
                worksheet.write(row, 2, line['taxable_amt'])
                worksheet.write(row, 3, line['cgst_amt'])
                worksheet.write(row, 4, line['sgst_amt'])
                worksheet.write(row, 5, line['igst_amt'])
                worksheet.write(row, 6, line['tax_amt'])

                # Update grand totals
                grand_totals['taxable_amt'] += line['taxable_amt']
                grand_totals['cgst_amt'] += line['cgst_amt']
                grand_totals['sgst_amt'] += line['sgst_amt']
                grand_totals['igst_amt'] += line['igst_amt']
                grand_totals['tax_amt'] += line['tax_amt']

                row += 1

        # Write the Grand Totals row
        worksheet.write(row, 0, 'Grand Total', bold)
        worksheet.write(row, 2, grand_totals['taxable_amt'])
        worksheet.write(row, 3, grand_totals['cgst_amt'])
        worksheet.write(row, 4, grand_totals['sgst_amt'])
        worksheet.write(row, 5, grand_totals['igst_amt'])
        worksheet.write(row, 6, grand_totals['tax_amt'])

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
            'name': f'POS_Tax_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'POS_Tax_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

