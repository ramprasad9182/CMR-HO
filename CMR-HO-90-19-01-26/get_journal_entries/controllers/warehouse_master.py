import json
from odoo import http
from odoo.http import request
import logging
import xml.etree.ElementTree as ET

_logger = logging.getLogger(__name__)



def json_to_xml(json_obj, root_tag="warehouses"):
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
                # If it's a list of warehouse, wrap it in <Warehouse>
                if isinstance(item, dict):
                    # Check if it's a warehouse (dictionary)
                    line_element = ET.SubElement(parent_element, 'Warehouse')
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



class GETWarehouse(http.Controller):

    @http.route('/odoo/get_warehouse_data', type='http', auth='public', methods=['GET'])
    def get_warehouse_data(self, **kwargs):
        result = []

        # Fetch warehouse based on the provided date
        data = request.env['stock.warehouse'].sudo().search([('nhcl_flag', '=', 'n')])

        if not data:
            _logger.warning("No warehouse found matching the criteria.")
            return request.make_response('<warehouses>No warehouse found</warehouses>',
                                         headers=[('Content-Type', 'application/xml')])

        for warehouse in data:
            if warehouse.lot_stock_id.location_id:
                location = warehouse.lot_stock_id.location_id.name + '/' + warehouse.lot_stock_id.name
            else:
                location = warehouse.lot_stock_id.name
            warehouse_entry = {
                'Name': warehouse.name,
                'ShortName': warehouse.code,
                'StockLocation': location,
                'Address': warehouse.partner_id.name,
                'Company': warehouse.company_id.name,
                'Street': warehouse.company_id.street,
                'City': warehouse.company_id.city,
                'State': warehouse.company_id.state_id.code,
                'Zip': warehouse.company_id.zip,
                'Country': warehouse.company_id.country_id.code,
            }

            result.append(warehouse_entry)  # Append each warehouse entry to the result

        # If no valid warehouses were appended, log and return a suitable response
        if not result:
            _logger.warning("No valid warehouse found.")
            return request.make_response('<warehouses>No valid warehouses found</warehouses>',
                                         headers=[('Content-Type', 'application/xml')])

        # Convert the result list directly to XML
        xml_data = json_to_xml(result, root_tag="warehouses")

        # Return the XML response with the appropriate content type
        return request.make_response(xml_data, headers=[('Content-Type', 'application/xml')])

    @http.route('/odoo/update_warehouse_data', type='http', auth='public', methods=['POST'],csrf=False)
    def update_warehouse_data(self, **kwargs):
        result = []
        try:
            if 'ShortName' in kwargs:
                # Fetch warehouse based on the provided name
                warehouses = request.env['stock.warehouse'].sudo().search(
                    [('code', '=', kwargs['ShortName']), ('nhcl_flag', '=', 'n')])

                if not warehouses:
                    warehouses = request.env['stock.warehouse'].sudo().search(
                        [('code', '=', kwargs['ShortName']), ('nhcl_flag', '=', 'y')])
                    if warehouses:
                        result = json.dumps({
                            'status': 'success',
                            'message': 'Warehouse Flag Already Updated successfully'
                        })
                    else:
                        result = json.dumps({
                            'status': 'error',
                            'message': 'Warehouse Not Found'
                        })
                else:
                    # Assuming the flag is a boolean field named 'nhcl_flag'
                    for warehouse in warehouses:
                        if warehouse.nhcl_flag == 'n':
                            warehouse.write({'nhcl_flag': 'y'})
                            result = json.dumps({
                                'status': 'success',
                                'message': 'Warehouse Flag updated successfully'
                            })
                        elif warehouse.nhcl_flag == 'y':
                            result = json.dumps({
                                'status': 'success',
                                'message': 'Warehouse Flag Already Updated successfully'
                            })
                        else:
                            result = json.dumps({
                                'status': 'error',
                                'message': 'Warehouse Not Found'
                            })

        except Exception as e:
            result = json.dumps({
                'status': 'error',
                'message': str(e)
            })
        return result