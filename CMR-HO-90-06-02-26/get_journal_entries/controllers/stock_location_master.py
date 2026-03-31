import json
from odoo import http
from odoo.http import request
import logging
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)



def json_to_xml(json_obj, root_tag="locations"):
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
                # If it's a list of location, wrap it in <location>
                if isinstance(item, dict):
                    # Check if it's a location (dictionary)
                    line_element = ET.SubElement(parent_element, 'Location')
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



class GETLocations(http.Controller):

    @http.route('/odoo/get_location_data', type='http', auth='public', methods=['GET'])
    def get_location_data(self, **kwargs):
        result = []

        # Fetch location based on the provided date
        data = request.env['stock.location'].sudo().search([('nhcl_flag', '=', 'n'),('replenish_location', '=', True)])

        if not data:
            _logger.warning("No location found matching the criteria.")
            return request.make_response('<locations>No location found</locations>',
                                         headers=[('Content-Type', 'application/xml')])

        for location in data:
            if location.location_id:
                name = location.location_id.name + '/' + location.name
            else:
                name  = location.name
            location_entry = {
                'Name': name,
                'Company': location.company_id.name,
                'Barcode':location.barcode,
                'Street': location.company_id.street,
                'City': location.company_id.city,
                'State': location.company_id.state_id.code,
                'Zip': location.company_id.zip,
                'Country': location.company_id.country_id.code,
                'TaxId':location.company_id.vat
            }

            result.append(location_entry)  # Append each location entry to the result

        # If no valid locations were appended, log and return a suitable response
        if not result:
            _logger.warning("No valid location found.")
            return request.make_response('<locations>No valid locations found</locations>',
                                         headers=[('Content-Type', 'application/xml')])

        # Convert the result list directly to XML
        xml_data = json_to_xml(result, root_tag="locations")

        # Return the XML response with the appropriate content type
        return request.make_response(xml_data, headers=[('Content-Type', 'application/xml')])

    @http.route('/odoo/update_location_data', type='http', auth='public', methods=['POST'],csrf=False)
    def update_location_data(self, **kwargs):
        result = []
        try:
            if 'barcode' in kwargs:
                # Fetch location based on the provided name
                locations = request.env['stock.location'].sudo().search(
                    [('barcode', '=', kwargs['barcode']), ('nhcl_flag', '=', 'n')])

                if not locations:
                    locations = request.env['stock.location'].sudo().search(
                        [('barcode', '=', kwargs['barcode']), ('nhcl_flag', '=', 'y')])
                    if locations:
                        result = json.dumps({
                            'status': 'success',
                            'message': 'location Flag Already Updated successfully'
                        })
                    else:
                        result = json.dumps({
                            'status': 'error',
                            'message': 'location Not Found'
                        })
                else:
                    # Assuming the flag is a boolean field named 'nhcl_flag'
                    for location in locations:
                        if location.nhcl_flag == 'n':
                            location.write({'nhcl_flag': 'y'})
                            result = json.dumps({
                                'status': 'success',
                                'message': 'Location Flag updated successfully'
                            })
                        elif location.nhcl_flag == 'y':
                            result = json.dumps({
                                'status': 'success',
                                'message': 'location Flag Already Updated successfully'
                            })
                        else:
                            result = json.dumps({
                                'status': 'error',
                                'message': 'location Not Found'
                            })

        except Exception as e:
            result = json.dumps({
                'status': 'error',
                'message': str(e)
            })
        return result