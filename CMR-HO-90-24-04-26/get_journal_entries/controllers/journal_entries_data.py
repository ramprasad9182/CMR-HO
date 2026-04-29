import json
from odoo import http
from odoo.http import request
import logging
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import html
from odoo.fields import Date

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


def error_response(message):
    safe_message = html.escape(message or "")
    xml_data = f"<transactions>{safe_message}</transactions>"
    return request.make_response(
        xml_data,
        headers=[('Content-Type', 'application/xml')],
        status=200
    )


class GETJournals(http.Controller):

    @http.route('/odoo/get_vendor_bill_journal_entries', type='http', auth='public', methods=['GET'])
    def get_vendor_bill_journal_entries(self, **kwargs):
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
        data = request.env['account.move'].sudo().search(
            [('move_type', 'in', ['in_invoice']), ('nhcl_flag', '=', 'n'), ('state', '=', 'posted')])

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
                tally_state = request.env['state.master'].sudo().search(
                    [('state_id', '=', move.company_id.state_id.id)])
                if tally_state:
                    tally_comp = html.unescape(tally_state.tally_company_name)
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

    @http.route('/odoo/get_vendor_payment_journal_entries', type='http', auth='public', methods=['GET'])
    def get_vendor_payment_journal_entries(self, **kwargs):

        try:
            integration = request.env['tally.integration'].sudo().search(
                [('active_record', '=', True)], limit=1)

            if not integration:
                return error_response("Integration configuration not done")

            api_key = kwargs.get('x-api-key') or request.httprequest.headers.get('x-api-key')
            if not api_key or api_key != integration.api_key:
                return error_response("Invalid API key")

            if not integration.journal_entries:
                return error_response("No journal types enabled")

            #  Optimized domain
            payments = request.env['account.payment'].sudo().search([
                ('state', '=', 'posted'),
                ('payment_type', '=', 'outbound'),
                ('vendor_nhcl_flag', '=', 'n'),
                ('company_id.nhcl_company_bool', '=', True),
                ('move_id', '!=', False),
                ('move_id.state', '=', 'posted'),
                ('move_id.nhcl_flag', '=', 'n'),
            ])
            _logger.info("Vendor Payment API Error: %s", payments)

            if not payments:
                return request.make_response(
                    "<transactions></transactions>",
                    headers=[('Content-Type', 'application/xml')]
                )

            result = []

            #  State cache (performance)
            state_cache = {}

            for pay in payments:
                move = pay.move_id
                if not move:
                    continue

                # narration
                narration = False
                if move.narration:
                    try:
                        soup = BeautifulSoup(move.narration or '', 'html.parser')
                        narration = soup.get_text()
                    except Exception:
                        narration = move.narration

                # company/state validation
                if not move.company_id or not move.company_id.state_id:
                    continue

                state_id = move.company_id.state_id.id

                #  Cached state lookup
                if state_id in state_cache:
                    tally_comp = state_cache[state_id]
                else:
                    tally_state = request.env['state.master'].sudo().search([
                        ('state_id', '=', state_id)
                    ], limit=1)

                    if not tally_state:
                        continue

                    tally_comp = html.unescape(tally_state.tally_company_name or '')
                    state_cache[state_id] = tally_comp

                # journal entry
                journal_entry = {
                    'Date': move.date.strftime('%Y-%m-%d') if move.date else '',
                    'Name': move.name or '',
                    'Ref': move.ref or move.name or '',
                    'Journal': move.journal_id.name if move.journal_id else '',
                    'Type': move.journal_id.type if move.journal_id else '',
                    'TallyCompany': tally_comp,
                    'State': move.company_id.state_id.code or '',
                    'CosCenter': move.company_id.name or '',
                    'Notes': narration,
                    'Lines': []
                }

                # lines
                for line in move.line_ids:
                    try:
                        branch = ''
                        sequence = ''

                        if line.account_id.account_type == 'liability_payable' and line.partner_id:
                            branch = line.partner_id.name or ''
                            sequence = line.partner_id.contact_sequence

                        journal_entry['Lines'].append({
                            'AccountCode': line.account_id.code or '',
                            'AccountName': line.account_id.name or '',
                            'AccountType': line.account_id.account_type or '',
                            'Branch': branch,
                            'Sequence': sequence,
                            'Debit': line.debit or 0,
                            'Credit': line.credit or 0
                        })
                    except Exception:
                        continue

                if journal_entry['Lines']:
                    result.append(journal_entry)

            # SAP safe
            if not result:
                return request.make_response(
                    "<transactions></transactions>",
                    headers=[('Content-Type', 'application/xml')]
                )

            xml_data = json_to_xml(result, root_tag="transactions")

            #  Optional (recommended in production)
            # payments.write({'vendor_get_flag': 'y'})

            return request.make_response(
                xml_data,
                headers=[('Content-Type', 'application/xml')]
            )

        except Exception as e:
            _logger.exception("Vendor Payment API Error: %s", str(e))

            #  NEVER break SAP
            return request.make_response(
                "<transactions></transactions>",
                headers=[('Content-Type', 'application/xml')]

            )

    @http.route('/odoo/update_journal_entries', type='http', auth='public', methods=['POST'], csrf=False)
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
                    [('name', '=', kwargs['name']), ('nhcl_flag', '=', 'n'), ('state', '=', 'posted')])

                if not journal_entry:
                    journal_entry = request.env['account.move'].sudo().search(
                        [('name', '=', kwargs['name']), ('nhcl_flag', '=', 'y'), ('state', '=', 'posted')])
                    if journal_entry:
                        for je in journal_entry:
                            if je.payment_id and je.payment_id.payment_type == 'outbound':
                                je.payment_id.write({'vendor_nhcl_flag': 'y'})
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
                            if je.payment_id and je.payment_id.payment_type == 'outbound':
                                je.payment_id.write({'vendor_nhcl_flag': 'y'})
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

    @http.route('/odoo/get_updated_vendor_bill_journal_entries', type='http', auth='public', methods=['GET'])
    def get_updated_vendor_bill_journal_entries(self, **kwargs):
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
        data = request.env['account.move'].sudo().search(
            [('move_type', 'in', ['in_invoice']), ('update_flag', '=', 'update'), ('state', '=', 'posted')])

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
                tally_state = request.env['state.master'].sudo().search(
                    [('state_id', '=', move.company_id.state_id.id)])
                if tally_state:
                    tally_comp = html.unescape(tally_state.tally_company_name)
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

    @http.route('/odoo/get_updated_vendor_payments', type='http', auth='public', methods=['GET'], csrf=False)
    def get_updated_vendor_payments(self, **kwargs):

        try:
            #  Integration validation
            integration = request.env['tally.integration'].sudo().search(
                [('active_record', '=', True)], limit=1)

            if not integration:
                return error_response("Integration configuration not done")

            #  API key validation
            # api_key = kwargs.get('x-api-key') or request.httprequest.headers.get('x-api-key')
            # if not api_key or api_key != integration.api_key:
            #     return error_response("Invalid API key")
            #
            # if not integration.journal_entries:
            #     return error_response("No journal types enabled")

            #  Fetch moves directly (optimized)
            moves = request.env['account.move'].sudo().search([
                ('state', '=', 'posted'),
                ('update_flag', '=', 'update'),
                ('payment_id.payment_type', '=', 'outbound')
            ])
            _logger.info("Updated Vendor Payment: %s", moves)

            if not moves:
                return request.make_response(
                    '<transactions></transactions>',
                    headers=[('Content-Type', 'application/xml')]
                )

            result = []

            #  State cache
            state_cache = {}

            for move in moves:
                # narration
                if move.narration:
                    try:
                        soup = BeautifulSoup(move.narration or '', 'html.parser')
                        narration = soup.get_text()
                    except Exception:
                        narration = move.narration
                else:
                    narration = False
                # ref
                ref = move.ref or move.name or ''
                # company/state
                if not move.company_id or not move.company_id.state_id:
                    continue

                state_id = move.company_id.state_id.id

                if state_id in state_cache:
                    tally_comp = state_cache[state_id]
                else:
                    tally_state = request.env['state.master'].sudo().search(
                        [('state_id', '=', state_id)],
                        limit=1
                    )

                    if not tally_state:
                        continue

                    tally_comp = html.unescape(tally_state.tally_company_name or '')
                    state_cache[state_id] = tally_comp

                # journal entry
                journal_entry = {
                    'Name': move.name or '',
                    'Ref': ref,
                    'Journal': move.journal_id.name if move.journal_id else '',
                    'TallyCompany': tally_comp,
                    'Notes': narration,
                }

                result.append(journal_entry)
            _logger.info("Updated Vendor Payment API Error: %s", result)
            #  SAP-safe empty
            if not result:
                return request.make_response(
                    '<transactions></transactions>',
                    headers=[('Content-Type', 'application/xml')]
                )

            # XML
            xml_data = json_to_xml(result, root_tag="transactions")

            return request.make_response(
                xml_data,
                headers=[('Content-Type', 'application/xml')]
            )

        except Exception as e:
            _logger.exception("Updated Vendor Payment API Error: %s", str(e))

            #  use error function OR empty (SAP-safe)
            return request.make_response(
                '<transactions></transactions>',
                headers=[('Content-Type', 'application/xml')]
            )

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
                    [('name', '=', kwargs['name']), ('update_flag', '=', 'update'), ('state', '=', 'posted')])

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

    # @http.route('/odoo/customer_invoice_journal_items', type='http', auth='public', methods=['GET'], csrf=False)
    # def customer_invoice_journal_items(self, **kwargs):
    #     try:
    #         #  Integration validation
    #         integration = request.env['tally.integration'].sudo().search(
    #             [('active_record', '=', True)], limit=1)
    #
    #         if not integration:
    #             return error_response("Integration configuration not done")
    #
    #         #  API key validation
    #         api_key = kwargs.get('x-api-key') or request.httprequest.headers.get('x-api-key')
    #         if not api_key or api_key != integration.api_key:
    #             return error_response("Invalid API key")
    #
    #         #  Journal config check
    #         if not integration.journal_entries:
    #             return error_response("No journal types enabled")
    #
    #         #  Today date
    #         today = Date.context_today(request.env.user)
    #
    #         #  Domain (with partner filter)
    #         # domain = [
    #         #     ('move_id.move_type', '=', 'out_invoice'),
    #         #     ('move_id.state', '=', 'posted'),
    #         #     ('move_id.invoice_date', '=', today),
    #         #     ('partner_id.name', 'not ilike', 'CMR')
    #         # ]
    #         domain = [
    #             ('move_id.move_type', '=', 'out_invoice'),
    #             ('move_id.state', '=', 'posted'),
    #             ('partner_id.name', 'not ilike', 'CMR')
    #         ]
    #
    #         lines = request.env['account.move.line'].sudo().search(domain)
    #         _logger.info("Invoice: %s", lines)
    #
    #         if not lines:
    #             return request.make_response(
    #                 "<transactions></transactions>",
    #                 headers=[('Content-Type', 'application/xml')]
    #             )
    #
    #         grouped_data = {}
    #
    #         for line in lines:
    #             try:
    #                 company = line.company_id.name or ''
    #                 journal = line.move_id.journal_id.name or ''
    #                 invoice_date = str(line.move_id.invoice_date or '')
    #                 account = line.account_id.name or ''
    #
    #                 key = (company, journal, invoice_date, account)
    #
    #                 if key not in grouped_data:
    #                     grouped_data[key] = {
    #                         'company': company,
    #                         'journal': journal,
    #                         'invoice_date': invoice_date,
    #                         'account': account,
    #                         'debit': 0.0,
    #                         'credit': 0.0
    #                     }
    #
    #                 grouped_data[key]['debit'] += line.debit or 0.0
    #                 grouped_data[key]['credit'] += line.credit or 0.0
    #
    #             except Exception:
    #                 continue
    #
    #         result = []
    #         for val in grouped_data.values():
    #             result.append({
    #                 'Company': val['company'],
    #                 'Journal': val['journal'],
    #                 'InvoiceDate': val['invoice_date'],
    #                 'Account': val['account'],
    #                 'Debit': round(val['debit'], 2),
    #                 'Credit': round(val['credit'], 2)
    #             })
    #         _logger.info("Invoice Result: %s", result)
    #
    #         if not result:
    #             return request.make_response(
    #                 "<transactions></transactions>",
    #                 headers=[('Content-Type', 'application/xml')]
    #             )
    #
    #         #  Convert to XML (unchanged logic)
    #         xml_data = json_to_xml({'JournalEntries': result}, root_tag='transactions')
    #
    #         return request.make_response(
    #             xml_data,
    #             headers=[('Content-Type', 'application/xml')]
    #         )
    #
    #     except Exception as e:
    #         _logger.exception("Customer Invoice API Error: %s", str(e))
    #
    #         #  SAP-safe fallback
    #         return request.make_response(
    #             "<transactions></transactions>",
    #             headers=[('Content-Type', 'application/xml')]
    #         )

    @http.route('/odoo/customer_invoice_journal_items', type='http', auth='public', methods=['GET'], csrf=False)
    def customer_invoice_journal_items(self, **kwargs):
        try:
            # Integration validation
            integration = request.env['tally.integration'].sudo().search(
                [('active_record', '=', True)], limit=1)

            if not integration:
                return error_response("Integration configuration not done")

            # API key validation
            api_key = kwargs.get('x-api-key') or request.httprequest.headers.get('x-api-key')
            if not api_key or api_key != integration.api_key:
                return error_response("Invalid API key")

            if not integration.journal_entries:
                return error_response("No journal types enabled")

            today = Date.context_today(request.env.user)

            # Domain
            domain = [
                ('move_id.move_type', '=', 'out_invoice'),
                ('move_id.state', '=', 'posted'),('move_id.nhcl_flag', '=', 'n'),
                # ('move_id.invoice_date', '=', today),
                ('partner_id.name', 'not like', '%CMR%')
            ]

            lines = request.env['account.move.line'].sudo().search(domain)
            _logger.info("Invoice Data: %s", lines)

            if not lines:
                return request.make_response(
                    "<transactions></transactions>",
                    headers=[('Content-Type', 'application/xml')]
                )

            # Header + Account wise grouping
            grouped = {}
            state_cache = {}

            for line in lines:
                company = line.company_id.name or ''
                journal = line.move_id.journal_id.name or ''
                invoice_date = str(line.move_id.invoice_date or line.move_id.date or '')
                account = line.account_id.name or ''
                state = line.company_id.state_id
                #  Check cache first
                if state.id in state_cache:
                    tally_comp = state_cache[state.id]
                else:
                    tally_state = request.env['state.master'].sudo().search(
                        [('state_id', '=', state.id)], limit=1
                    )

                    if not tally_state or not tally_state.tally_company_name:
                        continue

                    tally_comp = html.unescape(tally_state.tally_company_name)
                    state_cache[state.id] = tally_comp

                header_key = (company, journal, invoice_date)

                if header_key not in grouped:
                    grouped[header_key] = {
                        'Company': company,
                        'Journal': journal,
                        'InvoiceDate': invoice_date,
                        'TallyCompany': tally_comp,
                        'Lines': {}  # IMPORTANT
                    }

                if account not in grouped[header_key]['Lines']:
                    grouped[header_key]['Lines'][account] = {
                        'Account': account,
                        'Debit': 0.0,
                        'Credit': 0.0
                    }

                grouped[header_key]['Lines'][account]['Debit'] += line.debit or 0.0
                grouped[header_key]['Lines'][account]['Credit'] += line.credit or 0.0

            #  Prepare final list for json_to_xml
            final_result = []

            for header in grouped.values():
                lines_list = []

                for acc in header['Lines'].values():
                    lines_list.append({
                        'Account': acc['Account'],
                        'Debit': round(acc['Debit'], 2),
                        'Credit': round(acc['Credit'], 2),
                    })

                final_result.append({
                    'Company': header['Company'],
                    'Journal': header['Journal'],
                    'InvoiceDate': header['InvoiceDate'],
                    'TallyCompany': header['TallyCompany'],
                    'Lines': lines_list
                })
                _logger.info("Invoice Result: %s", final_result)

            #  IMPORTANT: pass list directly
            xml_data = json_to_xml(final_result, root_tag='transactions')

            return request.make_response(
                xml_data,
                headers=[('Content-Type', 'application/xml')]
            )

        except Exception as e:
            _logger.exception("Customer Invoice API Error: %s", str(e))
            return request.make_response(
                "<transactions></transactions>",
                headers=[('Content-Type', 'application/xml')]
            )



    @http.route('/odoo/bulk_update_customer_invoice', type='http', auth='public', methods=['POST'], csrf=False)
    def bulk_update_customer_invoice(self, **kwargs):
        try:
            integration = request.env['tally.integration'].sudo().search(
                [('active_record', '=', True)], limit=1)

            if not integration:
                return json.dumps({'status': 'error', 'message': 'Integration not configured'})

            # API key
            api_key = kwargs.get('x-api-key') or request.httprequest.headers.get('x-api-key')
            if not api_key or api_key != integration.api_key:
                return json.dumps({'status': 'error', 'message': 'Invalid API key'})

            data = json.loads(request.httprequest.data or '{}')
            companies = data.get('companies')
            invoice_date = data.get('invoice_date')

            if not companies or not invoice_date:
                return json.dumps({
                    'status': 'error',
                    'message': 'companies and invoice_date are required'
                })

            company_names = [c.strip() for c in companies.split(',') if c.strip()]

            company_ids = request.env['res.company'].sudo().search([
                ('name', 'in', company_names)
            ]).ids

            if not company_ids:
                return json.dumps({'status': 'error', 'message': 'No valid companies found'})

            #  Domain with invoice_date fallback to date
            domain = [
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('company_id', 'in', company_ids),
                ('nhcl_flag', '=', 'n'),
                ('invoice_date', '=', invoice_date),

            ]

            invoices = request.env['account.move'].sudo().search(domain)

            if not invoices:
                return json.dumps({
                    'status': 'success',
                    'updated_records': 0,
                    'message': 'No records found'
                })

            # Single bulk write
            invoices.write({'nhcl_flag': 'y'})

            return json.dumps({
                'status': 'success',
                'message': 'Create Flag Updated Succesfully',
                'updated_records': len(invoices)
            })

        except Exception as e:
            _logger.exception("Bulk Update Error: %s", str(e))
            return json.dumps({'status': 'error', 'message': str(e)})


    @http.route('/odoo/get_customer_payment_against_journal_items', type='http', auth='public', methods=['GET'], csrf=False)
    def get_customer_payment_against_journal_items(self, **kwargs):
        try:
            integration = request.env['tally.integration'].sudo().search(
                [('active_record', '=', True)], limit=1)

            if not integration:
                return request.make_response(
                    "<transactions></transactions>",
                    headers=[('Content-Type', 'application/xml')]
                )

            api_key = kwargs.get('x-api-key') or request.httprequest.headers.get('x-api-key')
            if not api_key or api_key != integration.api_key:
                return request.make_response(
                    "<transactions></transactions>",
                    headers=[('Content-Type', 'application/xml')]
                )

            payment_journals = [
                'AXIS', 'BAJAJ', 'Cash', 'CCMoP', 'CHEQUE', 'Credit Note Issued',
                'Credit Note Received', 'Debit Note Adjusted', 'Debit Note Issued',
                'Gift Voucher', 'HDFC', 'KOTAK', 'Mobikwik', 'PAYTM', 'PAYTM QR',
                'Redemption Token', 'SBI', 'SBI UPI', 'VOUCHER'
            ]

            domain = [
                ('move_id.state', '=', 'posted'),
                ('move_id.journal_id.name', 'in', payment_journals),('move_id.nhcl_flag', '=', 'n'),
            ]

            lines = request.env['account.move.line'].sudo().search(domain)

            if not lines:
                return request.make_response(
                    "<transactions></transactions>",
                    headers=[('Content-Type', 'application/xml')]
                )

            #  Same grouping logic
            grouped = {}
            state_cache = {}

            for line in lines:
                company = line.company_id.name or ''
                journal = line.move_id.journal_id.name or ''
                invoice_date = str(line.move_id.date or '')
                account = line.account_id.name or ''
                state = line.company_id.state_id
                #  Check cache first
                if state.id in state_cache:
                    tally_comp = state_cache[state.id]
                else:
                    tally_state = request.env['state.master'].sudo().search(
                        [('state_id', '=', state.id)], limit=1
                    )

                    if not tally_state or not tally_state.tally_company_name:
                        continue

                    tally_comp = html.unescape(tally_state.tally_company_name)
                    state_cache[state.id] = tally_comp

                header_key = (company, journal, invoice_date)

                if header_key not in grouped:
                    grouped[header_key] = {
                        'Company': company,
                        'Journal': journal,
                        'InvoiceDate': invoice_date,
                        'TallyCompany': tally_comp,
                        'Lines': {}
                    }

                if account not in grouped[header_key]['Lines']:
                    grouped[header_key]['Lines'][account] = {
                        'Account': account,
                        'Debit': 0.0,
                        'Credit': 0.0
                    }

                grouped[header_key]['Lines'][account]['Debit'] += line.debit or 0.0
                grouped[header_key]['Lines'][account]['Credit'] += line.credit or 0.0

            final_result = []

            for header in grouped.values():
                items = []
                for acc in header['Lines'].values():
                    items.append({
                        'Account': acc['Account'],
                        'Debit': round(acc['Debit'], 2),
                        'Credit': round(acc['Credit'], 2),
                    })

                final_result.append({
                    'Company': header['Company'],
                    'Journal': header['Journal'],
                    'InvoiceDate': header['InvoiceDate'],
                    'TallyCompany': header['TallyCompany'],
                    'Lines': items
                })

            xml_data = json_to_xml(final_result, root_tag='transactions')

            return request.make_response(
                xml_data,
                headers=[('Content-Type', 'application/xml')]
            )

        except Exception as e:
            _logger.exception("Customer Payment API Error: %s", str(e))
            return request.make_response(
                "<transactions></transactions>",
                headers=[('Content-Type', 'application/xml')]
            )

    @http.route('/odoo/update_customer_payment_against_journals', type='json', auth='public', methods=['POST'], csrf=False)
    def update_customer_payment_against_journals(self, **kwargs):

        data = request.jsonrequest
        company = data.get('companies')
        journal = data.get('journal')
        date = data.get('date')

        domain = [
            ('state', '=', 'posted'),
            ('company_id.name', '=', company),
            ('journal_id.name', '=', journal),
            ('date', '=', date),
            ('nhcl_flag', '=', 'n'),
        ]

        moves = request.env['account.move'].sudo().search(domain)

        if not moves:
            return {'status': 'success', 'updated_records': 0}

        moves.write({'nhcl_flag': 'y'})

        return {
            'status': 'success',
            'updated_records': len(moves)
        }


