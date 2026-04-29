import json
from odoo import http
from odoo.fields import Date
from odoo.http import request
import logging
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import html

_logger = logging.getLogger(__name__)



def json_to_xml(json_obj, root_tag="transactions"):
    """ Convert JSON object to XML string. """

    def build_xml_element(obj, parent_element):
        """ Recursively build XML elements from JSON object. """
        if isinstance(obj, dict):
            for key, value in obj.items():
                # Create a new element for each key-value pair
                child = ET.SubElement(parent_element, key)
                build_xml_element(value, child)
        elif isinstance(obj, list):
            for item in obj:
                # If it's a list of journal entries, wrap it in <Journal Entry>
                if isinstance(item, dict):
                    # Check if it's a journal entry (dictionary)
                    if 'Lines' in item:
                        line_element = ET.SubElement(parent_element, 'JournalEntry')
                    else:
                        line_element = ET.SubElement(parent_element, 'item')
                    build_xml_element(item, line_element)
                elif isinstance(item, list):  # If it's lines (list of dictionaries)
                    for line in item:  # Wrap each line in <line> tags
                        line_element = ET.SubElement(parent_element, 'line')
                        build_xml_element(line, line_element)
        else:
            # For primitive data types, set the text of the element
            # parent_element.text = str(obj)
            # value = str(obj).strip() if obj not in [None, False] else ''
            # parent_element.text = value

            if obj is None or obj is False:
                value = ''
            elif isinstance(obj, (int, float)) and obj == 0:
                value = '0'
            else:
                value = str(obj).strip()
            parent_element.text = value

    # Create the root element
    root = ET.Element(root_tag)
    build_xml_element(json_obj, root)

    # Convert the tree to a string and return it
    return ET.tostring(root, encoding='unicode', method='xml')



class GETJournals(http.Controller):

    @http.route('/odoo/get_customer_vendor_invoice_journal_entries', type='http', auth='public', methods=['GET'])
    def get_customer_vendor_invoice_journal_entries(self, **kwargs):
        integration = request.env['tally.integration'].sudo().search([('active_record', '=', True)])

        if not integration:
            _logger.warning("No active Tally Integration configuration found.")
            return request.make_response('<transactions>Integration configuration not done</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Validate API key
        api_key = kwargs.get('x-api-key') or request.httprequest.headers.get('x-api-key')
        if not api_key or api_key != integration.api_key:
            print(api_key)
            _logger.warning("Invalid API key.")
            return request.make_response('<transactions>Invalid API key</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Build domain based on integration flags
        if not integration.journal_entries:
            _logger.warning("No journal type selected in integration configuration.")
            return request.make_response(
                '<transactions>No journal types enabled in integration settings</transactions>',
                headers=[('Content-Type', 'application/xml')])

        result = []

        # Fetch journal entries based on the provided date
        data = request.env['account.move'].sudo().search([('move_type', 'in', ['in_invoice', 'out_invoice']),('nhcl_flag', '=', 'n'),('state', '=','posted')])

        if not data:
            _logger.warning("No journal entries found matching the criteria.")
            return request.make_response('<transactions>No journal entries found</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        for move in data:
            if move.narration != False:
                soup = BeautifulSoup(move.narration or '', 'html.parser')
                narration = soup.get_text()
            else:
                narration = False
            # getting payment_type
            payment_types = move.payment_id.payment_type
            if move.company_id.state_id:
                tally_state = request.env['state.master'].sudo().search([('state_id', '=', move.company_id.state_id.id)])
                if tally_state:
                    tally_comp =html.unescape(tally_state.tally_company_name)
                else:
                    continue

            journal_entry = {
                'Date': move.date.strftime('%Y-%m-%d'),
                'Name': move.name,
                'Ref': move.ref,
                'Journal': move.journal_id.name,
                'Type': move.journal_id.type,
                'TallyCompany': tally_comp,
                # 'TallyCompany': html.unescape(move.nhcl_tally_company_name or ''),
                "State": move.company_id.state_id.code,
                'CosCenter': move.company_id.name,
                'Notes': narration,
                'Lines': []  # Prepare list for journal lines
            }

            # Add line items to the journal entry
            for line in move.line_ids:
                # siva
                branch = " "
                sequence = " "
                if line.account_id.account_type == 'liability_payable':
                    branch = line.partner_id.name
                    sequence = line.partner_id.contact_sequence
                # if move.move_type == 'out_invoice' and line.account_id.name == 'Debtors' and line.partner_id:
                #     branch = line.partner_id.name
                #     sequence = line.partner_id.contact_sequence
                # elif move.move_type == 'in_invoice' and line.account_id.name == 'Creditors' and line.partner_id:
                #     branch = line.partner_id.name
                #     sequence = line.partner_id.contact_sequence
                # elif payment_types == 'outbound' and line.account_id.name == 'Creditors':
                #     branch = line.partner_id.name
                #     sequence = line.partner_id.contact_sequence
                # elif payment_types == 'inbound' and line.account_id.name == 'Debtors':
                #     branch = line.partner_id.name
                #     sequence = line.partner_id.contact_sequence
                # elif move.move_type == 'out_refund' and line.account_id.name == 'Debtors':
                #     branch = move.partner_id.name
                #     sequence = line.partner_id.contact_sequence
                # elif move.move_type == 'in_refund' and line.account_id.name == 'Creditors':
                #     branch = line.partner_id.name
                #     sequence = line.partner_id.contact_sequence

                journal_entry['Lines'].append({
                    'AccountCode': line.account_id.code,
                    'AccountName': line.account_id.name,
                    'AccountType': line.account_id.account_type,
                    'Branch': branch,  # Use "False" if no branch
                    'Sequence': sequence,
                    'Debit': line.debit,
                    'Credit': line.credit
                })

                # If no lines are added, log the information
            if not journal_entry['Lines']:
                _logger.warning(f"Journal entry {move.name} has no line items.")

            result.append(journal_entry)  # Append each journal entry to the result

        # If no valid journal entries were appended, log and return a suitable response
        if not result:
            _logger.warning("No valid journal entries with lines found.")
            return request.make_response('<transactions>No valid journal entries found</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Convert the result list directly to XML
        xml_data = json_to_xml(result, root_tag="transactions")

        # Return the XML response with the appropriate content type
        return request.make_response(xml_data, headers=[('Content-Type', 'application/xml')])

    @http.route('/odoo/update_journal_entries', type='http', auth='public', methods=['POST'],csrf=False)
    def update_journal_entries(self, **kwargs):
        integration = request.env['tally.integration'].sudo().search([('active_record', '=', True)], limit=1)

        if not integration:
            _logger.warning("No active Tally Integration configuration found.")
            return request.make_response('<transactions>Integration configuration not done</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Validate API key
        # api_key = kwargs.get('api_key') or request.httprequest.headers.get('api_key')
        # if not api_key or api_key != integration.api_key:
        #     _logger.warning("Invalid API key.")
        #     return request.make_response('<transactions>Invalid API key</transactions>',
        #                                  headers=[('Content-Type', 'application/xml')])

        # Build domain based on integration flags
        if not integration.journal_entries:
            _logger.warning("No journal type selected in integration configuration.")
            return request.make_response(
                '<transactions>No journal types enabled in integration settings</transactions>',
                headers=[('Content-Type', 'application/xml')])
        result = []
        try:
            if 'name' in kwargs:
                # Fetch journal entries based on the provided name
                journal_entry = request.env['account.move'].sudo().search(
                    [('name', '=', kwargs['name']), ('nhcl_flag', '=', 'n'),('state', '=','posted')])

                if not journal_entry:
                    journal_entry = request.env['account.move'].sudo().search(
                        [('name', '=', kwargs['name']), ('nhcl_flag', '=', 'y'),('state', '=','posted')])
                    if journal_entry:
                        result = json.dumps({
                            'status': 'success',
                            'message': 'JE Flag Already Updated successfully'
                        })
                    else:
                        result = json.dumps({
                            'status': 'error',
                            'message': 'JE Not Found'
                        })
                else:
                    # Assuming the flag is a boolean field named 'nhcl_flag'
                    for je in journal_entry:
                        if je.nhcl_flag == 'n':
                            je.write({'nhcl_flag': 'y'})
                            result = json.dumps({
                                'status': 'success',
                                'message': 'JE Flag updated successfully'
                            })
                        elif je.nhcl_flag == 'y':
                            result = json.dumps({
                                'status': 'success',
                                'message': 'JE Flag Already Updated successfully'
                            })
                        else:
                            result = json.dumps({
                                'status': 'error',
                                'message': 'JE Not Found'
                            })

        except Exception as e:
            result = json.dumps({
                'status': 'error',
                'message': str(e)
            })
        return result

    @http.route('/odoo/get_updated_customer_vendor_invoice_journal_entries', type='http', auth='public', methods=['GET'])
    def get_updated_customer_vendor_invoice_journal_entries(self, **kwargs):
        integration = request.env['tally.integration'].sudo().search([('active_record', '=', True)], limit=1)

        if not integration:
            _logger.warning("No active Tally Integration configuration found.")
            return request.make_response('<transactions>Integration configuration not done</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Validate API key
        # api_key = kwargs.get('api_key') or request.httprequest.headers.get('api_key')
        # if not api_key or api_key != integration.api_key:
        #     _logger.warning("Invalid API key.")
        #     return request.make_response('<transactions>Invalid API key</transactions>',
        #                                  headers=[('Content-Type', 'application/xml')])

        # Build domain based on integration flags
        if not integration.journal_entries:
            _logger.warning("No journal type selected in integration configuration.")
            return request.make_response(
                '<transactions>No journal types enabled in integration settings</transactions>',
                headers=[('Content-Type', 'application/xml')])
        result = []

        # Fetch journal entries based on the provided date
        data = request.env['account.move'].sudo().search([('move_type', 'in', ['in_invoice', 'out_invoice']),('update_flag', '=', 'update'),('state', '=','posted')])

        if not data:
            _logger.warning("No Updated journal entries found matching the criteria.")
            return request.make_response('<transactions>No Updated journal entries found</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        for move in data:
            if move.narration != False:
                soup = BeautifulSoup(move.narration or '', 'html.parser')
                narration = soup.get_text()
            else:
                narration = False
            if move.company_id.state_id:
                tally_state = request.env['state.master'].sudo().search([('state_id', '=', move.company_id.state_id.id)])
                if tally_state:
                    tally_comp =html.unescape(tally_state.tally_company_name)
                else:
                    continue
            journal_entry = {
                'Name': move.name,
                'Ref': move.ref,
                'TallyCompany': tally_comp,
                'Notes': narration,
            }

            result.append(journal_entry)  # Append each journal entry to the result

        # If no valid journal entries were appended, log and return a suitable response
        if not result:
            _logger.warning("No Updated Valid journal entries with lines found.")
            return request.make_response('<transactions>No Updated Valid journal entries found</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Convert the result list directly to XML
        xml_data = json_to_xml(result, root_tag="transactions")

        # Return the XML response with the appropriate content type
        return request.make_response(xml_data, headers=[('Content-Type', 'application/xml')])

    @http.route('/odoo/update_updated_journal_entries', type='http', auth='public', methods=['POST'], csrf=False)
    def update_updated_journal_entries(self, **kwargs):
        integration = request.env['tally.integration'].sudo().search([('active_record', '=', True)], limit=1)

        if not integration:
            _logger.warning("No active Tally Integration configuration found.")
            return request.make_response('<transactions>Integration configuration not done</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Validate API key
        # api_key = kwargs.get('api_key') or request.httprequest.headers.get('api_key')
        # if not api_key or api_key != integration.api_key:
        #     _logger.warning("Invalid API key.")
        #     return request.make_response('<transactions>Invalid API key</transactions>',
        #                                  headers=[('Content-Type', 'application/xml')])

        # Build domain based on integration flags
        if not integration.journal_entries:
            _logger.warning("No journal type selected in integration configuration.")
            return request.make_response(
                '<transactions>No journal types enabled in integration settings</transactions>',
                headers=[('Content-Type', 'application/xml')])

        result = []
        try:
            if 'name' in kwargs:
                # Fetch journal entries based on the provided name
                journal_entry = request.env['account.move'].sudo().search(
                    [('name', '=', kwargs['name']), ('update_flag', '=', 'update'),('state', '=','posted')])

                if not journal_entry:
                    journal_entry = request.env['account.move'].sudo().search(
                        [('name', '=', kwargs['name']), ('update_flag', '=', 'no_update')])
                    if journal_entry:
                        result = json.dumps({
                            'status': 'success',
                            'message': 'JE Flag Already Updated successfully'
                        })
                    else:
                        result = json.dumps({
                            'status': 'error',
                            'message': 'Updated JE Not Found'
                        })
                else:
                    # Assuming the flag is a boolean field named 'update_flag'
                    for je in journal_entry:
                        if je.update_flag == 'update':
                            je.write({'update_flag': 'no_update'})
                            result = json.dumps({
                                'status': 'success',
                                'message': 'JE Flag updated successfully'
                            })
                        elif je.update_flag == 'no_update':
                            result = json.dumps({
                                'status': 'success',
                                'message': 'JE Flag Already Updated successfully'
                            })
                        else:
                            result = json.dumps({
                                'status': 'error',
                                'message': 'Updated JE Not Found'
                            })

        except Exception as e:
            result = json.dumps({
                'status': 'error',
                'message': str(e)
            })
        return result



    def _serialize_move_with_lines(self, move):
        """Return (payload_dict, skip_bool) using same ‘Lines’ logic as your JE API."""
        # Notes / narration (plain text)
        print("serial",move)
        if move.narration is not False:
            soup = BeautifulSoup(move.narration or '', 'html.parser')
            narration = soup.get_text()
        else:
            narration = False
        if move.ref:
            ref = move.ref
        else:
            ref = move.name

        if move.company_id.state_id:
            tally_state = request.env['state.master'].sudo().search([('state_id', '=', move.company_id.state_id.id)])
            if tally_state:
                tally_comp = html.unescape(tally_state.tally_company_name)
            else:
                return None, True  # skip


        journal_entry = {
            'Odoo_id': str(move.id),
            'Date': move.date.strftime('%d-%m-%Y'),
            'Name': move.name,
            'Ref': move.ref,
            'Journal': move.journal_id.name,
            'TallyCompany': tally_comp,
            # 'TallyCompany': html.unescape(move.nhcl_tally_company_name or ''),
            "State": move.company_id.state_id.code,
            'CosCenter': move.company_id.name,
            'Notes': narration,
            'Lines': []
        }

        for line in move.line_ids:
            branch = " "
            sequence = " "
            if line.account_id.account_type == 'liability_payable':
                branch = line.partner_id.name
                sequence = line.partner_id.contact_sequence


            # derive Branch from any payable line's partner
            # if line.account_id.account_type == 'liability_payable':
            #     branch = line.partner_id.name
            #     print("batch")
            # elif line.account_id.account_type == 'asset_receivable':
            #     branch = line.partner_id.name
            # else:
            #     branch = " "

            line_dict = {
                'AccountCode': line.account_id.code,
                'AccountName': line.account_id.name,
                'AccountType': line.account_id.account_type,
                'Branch': branch if branch else False,
                'Sequence': sequence,
                'Debit': line.debit,
                'Credit': line.credit,
            }
            journal_entry['Lines'].append(line_dict)


        if not journal_entry['Lines']:
            _logger.warning(f"Move {move.name} has no line items.")
        return journal_entry, False

    def _response_from_moves(self, moves, wrapper_key):
        """Serialize moves with lines and return a JSON response using wrapper_key."""
        result = []
        for m in moves:
            payload, skip = self._serialize_move_with_lines(m)
            print("pay",payload)
            if skip:
                continue
            result.append(payload)

        if not result:
            return request.make_response('<transactions>No valid payment journal entry records found</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        xml_data = json_to_xml(result, root_tag="transactions")
        return request.make_response(xml_data, headers=[('Content-Type', 'application/xml')])


    @http.route('/odoo/api/get_customer_payments', type='http', auth='public', methods=['GET'])
    def get_customer_payments(self, **kwargs):
        integration = request.env['tally.integration'].sudo().search([('active_record', '=', True)])

        if not integration:
            _logger.warning("No active Tally Integration configuration found.")
            return request.make_response('<transactions>Integration configuration not done</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Validate API key
        api_key = kwargs.get('x-api-key') or request.httprequest.headers.get('x-api-key')
        if not api_key or api_key != integration.api_key:
            print(api_key)
            _logger.warning("Invalid API key.")
            return request.make_response('<transactions>Invalid API key</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Build domain based on integration flags
        if not integration.journal_entries:
            _logger.warning("No journal type selected in integration configuration.")
            return request.make_response(
                '<transactions>No journal types enabled in integration settings</transactions>',
                headers=[('Content-Type', 'application/xml')])

        payments = request.env['account.payment'].sudo().search([
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
        ])
        if not payments:
            return request.make_response('<transactions>No customer payments found</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Filter by move flag if you use nhcl_tally_flag on the journal entry
        moves = []
        for pay in payments:
            if pay.move_id and pay.move_id.state == 'posted' and pay.move_id.nhcl_flag == 'n':
                moves.append(pay.move_id)
        print("****",moves)
        if not moves:
            return request.make_response('<transactions>No customer payments Journal entry found</transactions>',
                                         headers=[('Content-Type', 'application/json')], status=404)
        return self._response_from_moves(moves, 'CustomerPaymentsJournalEntry')

    @http.route('/odoo/api/get_vendor_payments', type='http', auth='public', methods=['GET'])
    def get_vendor_payments(self, **kwargs):
        integration = request.env['tally.integration'].sudo().search([('active_record', '=', True)])

        if not integration:
            _logger.warning("No active Tally Integration configuration found.")
            return request.make_response('<transactions>Integration configuration not done</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Validate API key
        api_key = kwargs.get('x-api-key') or request.httprequest.headers.get('x-api-key')
        if not api_key or api_key != integration.api_key:
            print(api_key)
            _logger.warning("Invalid API key.")
            return request.make_response('<transactions>Invalid API key</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Build domain based on integration flags
        if not integration.journal_entries:
            _logger.warning("No journal type selected in integration configuration.")
            return request.make_response(
                '<transactions>No journal types enabled in integration settings</transactions>',
                headers=[('Content-Type', 'application/xml')])

        payments = request.env['account.payment'].sudo().search([
            ('payment_type', '=', 'outbound'),
            ('state', '=', 'posted'),
        ])
        if not payments:
            return request.make_response('<transactions>No vendor payments found</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Filter by move flag if you use nhcl_tally_flag on the journal entry
        moves = []
        for pay in payments:
            if pay.move_id and pay.move_id.state == 'posted' and pay.move_id.nhcl_flag == 'n':
                moves.append(pay.move_id)
        if not moves:
            return request.make_response('<transactions>No vendor payments Journal entry found</transactions>',
                                         headers=[('Content-Type', 'application/json')], status=404)
        return self._response_from_moves(moves, 'VendorPaymentsJournalEntry')

    def _update_serialize_move_with_lines(self, move):
        """Return (payload_dict, skip_bool) using same ‘Lines’ logic as your JE API."""
        # Notes / narration (plain text)
        print("serial",move)
        if move.narration is not False:
            soup = BeautifulSoup(move.narration or '', 'html.parser')
            narration = soup.get_text()
        else:
            narration = False
        if move.ref:
            ref = move.ref
        else:
            ref = move.name

        if move.company_id.state_id:
            tally_state = request.env['state.master'].sudo().search([('state_id', '=', move.company_id.state_id.id)])
            if tally_state:
                tally_comp = html.unescape(tally_state.tally_company_name)
            else:
                return None, True  # skip


        journal_entry = {
            'Name': move.name,
            'Ref': move.ref,
            'Journal': move.journal_id.name,
            'TallyCompany': tally_comp,
            # 'TallyCompany': html.unescape(move.nhcl_tally_company_name or ''),
            # "State": move.company_id.state_id.code,
            # 'CosCenter': move.company_id.name,
            'Notes': narration,

        }
        return journal_entry, False

    def _update_response_from_moves(self, moves, wrapper_key):
        """Serialize moves with lines and return a JSON response using wrapper_key."""
        result = []
        for m in moves:
            payload, skip = self._update_serialize_move_with_lines(m)
            # print("pay",payload)
            if skip:
                continue
            result.append(payload)

        if not result:
            return request.make_response('<transactions>No valid payment journal entry records found</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        xml_data = json_to_xml(result, root_tag="transactions")
        return request.make_response(xml_data, headers=[('Content-Type', 'application/xml')])

    @http.route('/odoo/api/get_updated_customer_payments', type='http', auth='public', methods=['GET'])
    def get_updated_customer_payments(self, **kwargs):
        integration = request.env['tally.integration'].sudo().search([('active_record', '=', True)])

        if not integration:
            _logger.warning("No active Tally Integration configuration found.")
            return request.make_response('<transactions>Integration configuration not done</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Validate API key
        api_key = kwargs.get('x-api-key') or request.httprequest.headers.get('x-api-key')
        if not api_key or api_key != integration.api_key:
            print(api_key)
            _logger.warning("Invalid API key.")
            return request.make_response('<transactions>Invalid API key</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Build domain based on integration flags
        if not integration.journal_entries:
            _logger.warning("No journal type selected in integration configuration.")
            return request.make_response(
                '<transactions>No journal types enabled in integration settings</transactions>',
                headers=[('Content-Type', 'application/xml')])

        payments = request.env['account.payment'].sudo().search([
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
        ])
        if not payments:
            return request.make_response('<transactions>No customer payments found</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Filter by move flag if you use nhcl_tally_flag on the journal entry
        moves = []
        for pay in payments:
            if pay.move_id and pay.move_id.state == 'posted' and pay.move_id.update_flag == 'update':
                moves.append(pay.move_id)
        # print("****", moves)
        if not moves:
            return request.make_response('<transactions>No updated customer payments Journal entry found</transactions>',
                                         headers=[('Content-Type', 'application/json')], status=404)
        return self._update_response_from_moves(moves, 'CustomerPaymentsJournalEntry')

    @http.route('/odoo/api/get_updated_vendor_payments', type='http', auth='public', methods=['GET'])
    def get_updated_vendor_payments(self, **kwargs):
        integration = request.env['tally.integration'].sudo().search([('active_record', '=', True)])

        if not integration:
            _logger.warning("No active Tally Integration configuration found.")
            return request.make_response('<transactions>Integration configuration not done</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Validate API key
        api_key = kwargs.get('x-api-key') or request.httprequest.headers.get('x-api-key')
        if not api_key or api_key != integration.api_key:
            # print(api_key)
            _logger.warning("Invalid API key.")
            return request.make_response('<transactions>Invalid API key</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Build domain based on integration flags
        if not integration.journal_entries:
            _logger.warning("No journal type selected in integration configuration.")
            return request.make_response(
                '<transactions>No journal types enabled in integration settings</transactions>',
                headers=[('Content-Type', 'application/xml')])

        payments = request.env['account.payment'].sudo().search([
            ('payment_type', '=', 'outbound'),
            ('state', '=', 'posted'),
        ])
        if not payments:
            return request.make_response('<transactions>No vendor payments found</transactions>',
                                         headers=[('Content-Type', 'application/xml')])

        # Filter by move flag if you use nhcl_tally_flag on the journal entry
        moves = []
        for pay in payments:
            if pay.move_id and pay.move_id.state == 'posted' and pay.move_id.update_flag == 'update':
                moves.append(pay.move_id)
        if not moves:
            return request.make_response('<transactions>No updated vendor payments Journal entry found</transactions>',
                                         headers=[('Content-Type', 'application/json')], status=404)
        return self._update_response_from_moves(moves, 'VendorPaymentsJournalEntry')

    @http.route('/api/get_customer_invoice_journal_items', type='http', auth='public', methods=['GET'], csrf=False)
    def get_customer_invoice_journal_items(self, **kwargs):
        today = Date.context_today(request.env.user)
        domain = [
            ('move_id.move_type', '=', 'out_invoice'),
            ('move_id.state', '=', 'posted'),
            ('move_id.invoice_date', '=', today),
            ('partner_id.name', 'not ilike', 'CMR')
        ]

        lines = request.env['account.move.line'].sudo().search(domain)
        print("+++++",lines)

        grouped_data = {}

        for line in lines:
            company = line.company_id.name or ''
            journal = line.move_id.journal_id.name or ''
            invoice_date = str(line.move_id.invoice_date or '')
            account = line.account_id.name or ''

            key = (company, journal, invoice_date, account)

            if key not in grouped_data:
                grouped_data[key] = {
                    'company': company,
                    'journal': journal,
                    'invoice_date': invoice_date,
                    'account': account,
                    'debit': 0.0,
                    'credit': 0.0
                }

            grouped_data[key]['debit'] += line.debit
            grouped_data[key]['credit'] += line.credit

        result = []
        for val in grouped_data.values():
            result.append({
                'Company': val['company'],
                'Journal': val['journal'],
                'InvoiceDate': val['invoice_date'],
                'Account': val['account'],
                'Debit': round(val['debit'], 2),
                'Credit': round(val['credit'], 2)
            })

        # Convert to XML
        xml_data = json_to_xml({'JournalEntries': result}, root_tag='Root')

        return request.make_response(
            xml_data,
            headers=[('Content-Type', 'application/xml')]
        )



    @http.route('/api/get_customer_payment_journal_items', type='http', auth='public', methods=['GET'], csrf=False)
    def get_customer_payment_journal_items(self, **kwargs):

        # ✅ Integration config
        integration = request.env['tally.integration'].sudo().search(
            [('active_record', '=', True)], limit=1
        )

        # if not integration:
        #     return error_response("Integration configuration not done")

        # ✅ API Key Validation
        api_key = kwargs.get('x-api-key') or request.httprequest.headers.get('x-api-key')
        # if not api_key or api_key != integration.api_key:
        #     return error_response("Invalid API key")

        # ✅ Journal config check
        # if not integration.journal_entries:
        #     return error_response("No journal types enabled")

        # ✅ Date
        today = Date.context_today(request.env.user)

        # ✅ Domain (Customer Payments JE)
        domain = [
            ('move_id.state', '=', 'posted'),
            ('move_id.move_type', '=', 'entry'),
            ('move_id.date', '=', today),
            ('move_id.payment_id.payment_type', '=', 'inbound')
        ]

        lines = request.env['account.move.line'].sudo().search(domain)

        grouped_data = {}

        # ✅ Grouping logic (same as invoice)
        for line in lines:
            company = line.company_id.name or ''
            journal = line.move_id.journal_id.name or ''
            date = str(line.move_id.date or '')
            account = line.account_id.name or ''

            key = (company, journal, date, account)

            if key not in grouped_data:
                grouped_data[key] = {
                    'company': company,
                    'journal': journal,
                    'date': date,
                    'account': account,
                    'debit': 0.0,
                    'credit': 0.0
                }

            grouped_data[key]['debit'] += line.debit
            grouped_data[key]['credit'] += line.credit

        result = []

        for val in grouped_data.values():
            result.append({
                'Company': val['company'],
                'Journal': val['journal'],
                'Date': val['date'],
                'Account': val['account'],
                'Debit': round(val['debit'], 2),
                'Credit': round(val['credit'], 2)
            })

        # 🔴 SAP SAFE: No data
        if not result:
            xml_data = "<transactions></transactions>"
            return request.make_response(
                xml_data,
                headers=[('Content-Type', 'application/xml')]
            )

        # ✅ XML conversion
        xml_data = json_to_xml({'JournalEntries': result}, root_tag='transactions')

        return request.make_response(
            xml_data,
            headers=[('Content-Type', 'application/xml')]
        )
