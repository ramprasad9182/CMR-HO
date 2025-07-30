import json
from odoo import http
from odoo.http import request
import logging
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

_logger = logging.getLogger(__name__)



def json_to_xml(json_obj, root_tag="contacts"):
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
                # If it's a list of contact, wrap it in <contact>
                if isinstance(item, dict):
                    # Check if it's a contact (dictionary)
                    line_element = ET.SubElement(parent_element, 'Partner')
                    build_xml_element(item, line_element)
                elif isinstance(item, list):  # If it's lines (list of dictionaries)
                    for line in item:  # Wrap each line in <line> tags
                        line_element = ET.SubElement(parent_element, 'line')
                        build_xml_element(line, line_element)
        else:
            # For primitive data types, set the text of the element
            # parent_element.text = str(obj)
            # parent_element.text = '' if obj in [None, '', False] else str(obj)
            value = str(obj).strip() if obj not in [None, False] else ''
            parent_element.text = value

    # Create the root element
    root = ET.Element(root_tag)
    build_xml_element(json_obj, root)

    # Convert the tree to a string and return it
    return ET.tostring(root, encoding='unicode', method='xml')



class GETContacts(http.Controller):

    @http.route('/odoo/get_contact_data', type='http', auth='public', methods=['GET'])
    def get_contact_data(self, **kwargs):
        integration = request.env['tally.integration'].sudo().search([('active_record', '=', True)])

        if not integration:
            _logger.warning("No active Tally Integration configuration found.")
            return request.make_response('<contacts>Integration configuration not done</contacts>',
                                         headers=[('Content-Type', 'application/xml')])

        # Validate API key
        api_key = kwargs.get('api_key') or request.httprequest.headers.get('api_key')
        if not api_key or api_key != integration.api_key:
            _logger.warning("Invalid API key.")
            return request.make_response('<contacts>Invalid API key</contacts>',
                                         headers=[('Content-Type', 'application/xml')], )

        # Build domain based on integration flags
        domain = [('nhcl_flag', '=', 'n')]
        print(domain)
        if integration.customers and integration.vendors:
            domain += ['|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]
            print(domain)
        elif integration.customers:
            domain += [('customer_rank', '>', 0)]
            print(domain)
        elif integration.vendors:
            domain += [('supplier_rank', '>', 0)]
            print(domain)
        else:
            _logger.warning("Neither customer nor vendor flag enabled.")
            return request.make_response('<contacts>No contact found</contacts>',
                                         headers=[('Content-Type', 'application/xml')])

        partners = request.env['res.partner'].sudo().search(domain)
        if not partners:
            _logger.warning("No matching partners found.")
            return request.make_response('<contacts>No valid contact found</contacts>',
                                         headers=[('Content-Type', 'application/xml')])
        result = []

        for contact in partners:
            narration = ''
            contact_tally_company_code = ''
            cleaned_code_str = ''
            if contact.comment:
                soup = BeautifulSoup(contact.comment or '', 'html.parser')
                narration = soup.get_text()

            if contact.group_contact.name == 'Customer':
                terms = contact.property_payment_term_id.name or ''
                contact_tally_company_code_data = integration.customers_tally_company_code_ids
                contact_tally_company_code = [code.strip() for code in contact_tally_company_code_data.split(',')]
                cleaned_code_str = ",".join(contact_tally_company_code)
                print(terms)
            elif contact.group_contact.name == 'Vendor':
                terms = contact.property_supplier_payment_term_id.name or ''
                contact_tally_company_code_data = integration.vendors_tally_company_code_ids
                contact_tally_company_code = [code.strip() for code in contact_tally_company_code_data.split(',')]
                cleaned_code_str = ",".join(contact_tally_company_code)

            else:
                terms = ''
            contact = {
                'Name': contact.name,
                'Group': contact.group_contact.name,
                'Sequence': contact.contact_sequence,
                'Company': contact.company_id.name,
                'TallyCompanyCodes': cleaned_code_str,
                'Phone':contact.phone,
                'Mobile': contact.mobile,
                'Website': contact.website,
                'Email':contact.email,
                'Street':contact.street,
                'City': contact.city,
                'State' : contact.state_id.code,
                'Zip': contact.zip,
                'Country': contact.country_id.code,
                'TAXID' : contact.vat,
                'PAN' : contact.l10n_in_pan,
                'PaymentTerms': terms,
                # 'PaymentTerms': contact.property_supplier_payment_term_id.name,
                # 'Company Name' : contact.company_id.name
            }

            result.append(contact)  # Append each contact entry to the result

        # If no valid Contacts were appended, log and return a suitable response
        if not result:
            _logger.warning("No valid contact found.")
            return request.make_response('<contacts>No valid Contacts found</contacts>',
                                         headers=[('Content-Type', 'application/xml')])

        # Convert the result list directly to XML
        xml_data = json_to_xml(result, root_tag="contacts")

        # Return the XML response with the appropriate content type
        return request.make_response(xml_data, headers=[('Content-Type', 'application/xml')])

    @http.route('/odoo/update_contacts_data', type='http', auth='public', methods=['POST'],csrf=False)
    def update_contacts_data(self, **kwargs):
        integration = request.env['tally.integration'].sudo().search([('active_record', '=', True)])

        if not integration:
            _logger.warning("No active Tally Integration configuration found.")
            return request.make_response('<contacts>Integration configuration not done</contacts>',
                                         headers=[('Content-Type', 'application/xml')])

        # Validate API key
        api_key = kwargs.get('api_key') or request.httprequest.headers.get('api_key')
        if not api_key or api_key != integration.api_key:
            _logger.warning("Invalid API key.")
            return request.make_response('<contacts>Invalid API key</contacts>',
                                         headers=[('Content-Type', 'application/xml')], )
        result = []
        try:
            if 'sequence' in kwargs:
                # Fetch contact based on the provided name
                contact = request.env['res.partner'].sudo().search(
                    [('contact_sequence', '=', kwargs['sequence']), ('nhcl_flag', '=', 'n')])

                if not contact:
                    contact = request.env['res.partner'].sudo().search(
                        [('contact_sequence', '=', kwargs['sequence']), ('nhcl_flag', '=', 'y')])
                    if contact:
                        result = json.dumps({
                            'status': 'success',
                            'message': 'Contact Flag Already Updated successfully'
                        })
                    else:
                        result = json.dumps({
                            'status': 'error',
                            'message': 'contact Not Found'
                        })
                else:
                    # Assuming the flag is a boolean field named 'nhcl_flag'
                    if contact.nhcl_flag == 'n':
                        contact.write({'nhcl_flag': 'y'})
                        result = json.dumps({
                            'status': 'success',
                            'message': 'Contact Flag updated successfully'
                        })
                    elif contact.nhcl_flag == 'y':
                        result = json.dumps({
                            'status': 'success',
                            'message': 'Contact Flag Already Updated successfully'
                        })
                    else:
                        result = json.dumps({
                            'status': 'error',
                            'message': 'Contact Not Found'
                        })

        except Exception as e:
            result = json.dumps({
                'status': 'error',
                'message': str(e)
            })
        return result

    # siva
    @http.route('/odoo/get_updated_contacts_data', type='http', auth='public', methods=['GET'], csrf=False)
    def get_updated_contacts_data(self, **kwargs):
        integration = request.env['tally.integration'].sudo().search([('active_record', '=', True)])

        if not integration:
            _logger.warning("No active Tally Integration configuration found.")
            return request.make_response('<contacts>Integration configuration not done</contacts>',
                                         headers=[('Content-Type', 'application/xml')])

        # Validate API key
        api_key = kwargs.get('api_key') or request.httprequest.headers.get('api_key')
        if not api_key or api_key != integration.api_key:
            _logger.warning("Invalid API key.")
            return request.make_response('<contacts>Invalid API key</contacts>',
                                         headers=[('Content-Type', 'application/xml')], )

        # Build domain based on integration flags
        domain = [('update_flag', '=', 'update')]
        print(domain)
        if integration.customers and integration.vendors:
            domain += ['|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0)]
            print(domain)
        elif integration.customers:
            domain += [('customer_rank', '>', 0)]
            print(domain)
        elif integration.vendors:
            domain += [('supplier_rank', '>', 0)]
            print(domain)
        else:
            _logger.warning("Neither customer nor vendor flag enabled.")
            return request.make_response('<contact>>No partner type enabled</contact>',
                                         headers=[('Content-Type', 'application/xml')])

        partners = request.env['res.partner'].sudo().search(domain)
        if not partners:
            _logger.warning("No matching partners found.")
            return request.make_response('<contact>No valid contact found</contact>',
                                         headers=[('Content-Type', 'application/xml')])
        result = []

        for contact in partners:
            narration = ''
            contact_tally_company_code = ''
            cleaned_code_str = ''
            if contact.comment:
                soup = BeautifulSoup(contact.comment or '', 'html.parser')
                narration = soup.get_text()

            if contact.group_contact.name == 'Customer':
                terms = contact.property_payment_term_id.name or ''
                contact_tally_company_code_data = integration.customers_tally_company_code_ids
                contact_tally_company_code = [code.strip() for code in contact_tally_company_code_data.split(',')]
                cleaned_code_str = ",".join(contact_tally_company_code)
                print(terms)
            elif contact.group_contact.name == 'Vendor':
                terms = contact.property_supplier_payment_term_id.name or ''
                contact_tally_company_code_data = integration.vendors_tally_company_code_ids
                contact_tally_company_code = [code.strip() for code in contact_tally_company_code_data.split(',')]
                cleaned_code_str = ",".join(contact_tally_company_code)
            else:
                terms = ''
            contact = {
                'Name': contact.name,
                'Sequence': contact.contact_sequence,
                'Phone': contact.phone,
                'Email': contact.email,
                'Website': contact.website,
                'TallyCompanyCodes':cleaned_code_str
                # 'PaymentTerms': terms
                # 'PaymentTerms': contact.property_supplier_payment_term_id.name,
                # 'Street': contact.street,
                # 'City': contact.city,
                # 'State': contact.state_id.code,
                # 'Zip': contact.zip,
                # 'Country': contact.country_id.code,
                # 'TAXID': contact.vat,
                # 'PAN': contact.l10n_in_pan
            }

            result.append(contact)  # Append each contact entry to the result

        # If no valid Contacts were appended, log and return a suitable response
        if not result:
            _logger.warning("No Updated valid contact found.")
            return request.make_response('<contacts>No Updated valid Contacts found</contacts>',
                                         headers=[('Content-Type', 'application/xml')])

        # Convert the result list directly to XML
        xml_data = json_to_xml(result, root_tag="Contacts")

        # Return the XML response with the appropriate content type
        return request.make_response(xml_data, headers=[('Content-Type', 'application/xml')])


    # siva
    @http.route('/odoo/update_updated_contacts_data', type='http', auth='public', methods=['POST'], csrf=False)
    def update_updated_contacts_data(self, **kwargs):
        integration = request.env['tally.integration'].sudo().search([('active_record', '=', True)], limit=1)

        if not integration:
            _logger.warning("No active Tally Integration configuration found.")
            return request.make_response(json.dumps({"message": "Integration configuration not done"}),
                                         headers=[('Content-Type', 'application/json')], status=400)

        # Validate API key
        api_key = kwargs.get('api_key') or request.httprequest.headers.get('api_key')
        if not api_key or api_key != integration.api_key:
            _logger.warning("Invalid API key.")
            return request.make_response(json.dumps({"message": "Invalid API key"}),
                                         headers=[('Content-Type', 'application/json')], status=404)
        result = []
        try:
            if 'sequence' in kwargs:
                data = request.env['res.partner'].sudo().search(
                    [('contact_sequence', '=',  kwargs['sequence']), ('update_flag', '=', 'update')])

                if not data:
                    data = request.env['res.partner'].sudo().search(
                        [('contact_sequence', '=',  kwargs['sequence']), ('update_flag', '=', 'no_update')])
                    if data:
                        result = json.dumps({
                            'status': 'success',
                            'message': 'Contact Update Flag Already Updated successfully'
                        })
                    else:
                        result = json.dumps({
                            'status': 'error',
                            'message': 'Update Contact Not Found'
                        })
                else:
                    for contact in data:
                        if contact.update_flag == 'update':
                            contact.write({'update_flag': 'no_update'})
                            result = json.dumps({
                                'status': 'success',
                                'message': 'Contact Update Flag Updated successfully'
                            })
                        elif contact.update_flag == 'no_update':
                            result = json.dumps({
                                'status': 'success',
                                'message': 'Contact Update Flag Already Updated successfully'
                            })
                        else:
                            result = json.dumps({
                                'status': 'error',
                                'message': 'Contact Update Flag Not Found'
                            })
        except Exception as e:
            result = json.dumps({
                'status': 'error',
                'message': str(e)
            })

        return result