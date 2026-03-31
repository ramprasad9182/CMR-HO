import json
from odoo import http
from odoo.http import request
import logging
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)



def json_to_xml(json_obj, root_tag="companies"):
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
                # If it's a list of companies, wrap it in <Company>
                if isinstance(item, dict):
                    # Check if it's a companies (dictionary)
                    line_element = ET.SubElement(parent_element, 'Company')
                    build_xml_element(item, line_element)
                elif isinstance(item, list):  # If it's lines (list of dictionaries)
                    for line in item:  # Wrap each line in <line> tags
                        line_element = ET.SubElement(parent_element, 'line')
                        build_xml_element(line, line_element)
        else:
            # For primitive data types, set the text of the element
            parent_element.text = str(obj)

    # Create the root element
    root = ET.Element(root_tag)
    build_xml_element(json_obj, root)

    # Convert the tree to a string and return it
    return ET.tostring(root, encoding='unicode', method='xml')



class GETCompanies(http.Controller):

    @http.route('/odoo/get_company_data', type='http', auth='public', methods=['GET'])
    def get_companies_data(self, **kwargs):
        result = []

        # Fetch companies based on the provided date
        data = request.env['res.company'].sudo().search([('nhcl_flag', '=', 'n')])

        if not data:
            _logger.warning("No company found matching the criteria.")
            return request.make_response('<companies>No company found</companies>',
                                         headers=[('Content-Type', 'application/xml')])

        for company in data:
            company_list = {
                'Name': company.name,
                'ShortName':company.warehouse_id.code,
                'Street':company.street,
                'City': company.city,
                'State' : company.state_id.code,
                'Zip': company.zip,
                'Country': company.country_id.code,
                'TAXID' : company.vat,
                'Phone':company.phone,
                'Email':company.email,
                'IsMainCompany' : company.nhcl_company_bool
            }

            result.append(company_list)  # Append each companies to the result

        # If no valid companies were appended, log and return a suitable response
        if not result:
            _logger.warning("No valid company found.")
            return request.make_response('<companies>No valid company found</companies>',
                                         headers=[('Content-Type', 'application/xml')])

        # Convert the result list directly to XML
        xml_data = json_to_xml(result, root_tag="companies")

        # Return the XML response with the appropriate content type
        return request.make_response(xml_data, headers=[('Content-Type', 'application/xml')])

    @http.route('/odoo/update_company_data', type='http', auth='public', methods=['POST'],csrf=False)
    def update_companies_data(self, **kwargs):
        result = []
        try:
            if 'name' in kwargs:
                # Fetch company based on the provided name
                companies = request.env['res.company'].sudo().search(
                    [('name', '=', kwargs['name']), ('nhcl_flag', '=', 'n')])

                if not companies:
                    companies = request.env['res.company'].sudo().search(
                        [('name', '=', kwargs['name']), ('nhcl_flag', '=', 'y')])
                    if companies:
                        result = json.dumps({
                            'status': 'success',
                            'message': 'Company Flag Already Updated successfully'
                        })
                    else:
                        result = json.dumps({
                            'status': 'error',
                            'message': 'Company Not Found'
                        })
                else:
                    # Assuming the flag is a boolean field named 'nhcl_flag'
                    for company in companies:
                        company.write({'nhcl_flag': 'y'})
                        if company.nhcl_flag == 'n':
                            result = json.dumps({
                                'status': 'success',
                                'message': 'Company Flag updated successfully'
                            })
                        elif company.nhcl_flag == 'y':
                            result = json.dumps({
                                'status': 'success',
                                'message': 'Company Flag Already Updated successfully'
                            })
                        else:
                            result = json.dumps({
                                'status': 'error',
                                'message': 'Company Not Found'
                            })

        except Exception as e:
            result = json.dumps({
                'status': 'error',
                'message': str(e)
            })
        return result