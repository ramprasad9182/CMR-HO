import json
from odoo import http
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

    @http.route('/odoo/get_journal_entries', type='http', auth='public', methods=['GET'])
    def get_journal_entries(self, **kwargs):
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
        data = request.env['account.move'].sudo().search([('nhcl_flag', '=', 'n'),('state', '=','posted')])

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
                    tally_comp =html.unescape(tally_state.tally_company_name or '')
            journal_entry = {
                'Date': move.date.strftime('%Y-%m-%d'),
                'Name': move.name,
                'Ref': move.ref,
                'Journal': move.journal_id.name,
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

    @http.route('/odoo/get_updated_journal_entries', type='http', auth='public', methods=['GET'])
    def get_updated_journal_entries(self, **kwargs):
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
        data = request.env['account.move'].sudo().search([('update_flag', '=', 'update'),('state', '=','posted')])

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
                    tally_comp =html.unescape(tally_state.tally_company_name or '')
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