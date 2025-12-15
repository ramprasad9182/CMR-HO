import requests
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class UomCateg(models.Model):
    _inherit = 'uom.category'

    nhcl_product_uom_ids = fields.One2many('product.uom.replication', 'product_uom_id')
    update_replication = fields.Boolean(string="Creation Status")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")


    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM uom_category")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(UomCateg, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'


    def get_stores_data(self):
        for store in self:
            existing_store_ids = store.nhcl_product_uom_ids.mapped('store_id.id')
            replication_data = []
            ho_store_id = store.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
            for rec in store.nhcl_product_uom_ids:
                if rec.nhcl_terminal_ip not in ho_store_id.mapped('nhcl_terminal_ip'):
                    rec.sudo().unlink()
                elif rec.nhcl_api_key not in ho_store_id.mapped('nhcl_api_key'):
                    rec.sudo().unlink()
            existing_store_ids = []
            if store.nhcl_product_uom_ids:
                existing_store_ids = store.nhcl_product_uom_ids.mapped('store_id.id')
            for i in ho_store_id:
                for j in i.nhcl_store_data_id:
                    if j.model_id.name == 'Product UoM Categories' and j.nhcl_line_data == True:
                        if i.nhcl_store_name.id in existing_store_ids:
                            continue
                        vals = {
                            'store_id': i.nhcl_store_name.id,
                            'nhcl_terminal_ip': i.nhcl_terminal_ip,
                            'nhcl_port_no': i.nhcl_port_no,
                            'nhcl_api_key': i.nhcl_api_key,
                            'status': i.nhcl_active,
                            'master_store_id': i.id
                        }
                        replication_data.append((0, 0, vals))
            store.update({'nhcl_product_uom_ids': replication_data})

    def send_uom_category_replication_data(self):
        k = []
        for line in self.uom_ids:
            k.append((0, 0, {
                'name': line.name,
                'nhcl_id': line.nhcl_id,
                'uom_type': line.uom_type,
                'factor': line.factor,
                'factor_inv': line.factor_inv,
                'ratio': line.ratio,
                'active': line.active,
                'rounding': line.rounding,
            }))
        uom_category_data = {
            'name': self.name,
            'nhcl_id': self.nhcl_id,
            'uom_ids': k,

        }
        for line in self.nhcl_product_uom_ids:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                store_url_exist_data = f"http://{ho_ip}:{ho_port}/api/uom.category/search"
                uom_domain = [('nhcl_id','=',self.nhcl_id)]
                store_url = f"{store_url_exist_data}?domain={uom_domain}"
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()  # Raises an HTTPError for bad responses

                    # Parse the JSON response
                    data = response.json()  # Now `data` is a dictionary
                    uom_category_id_data = data.get("data", [])
                    # Check if Chart of Account already exists
                    if uom_category_id_data:
                        line.date_replication = True
                        self.update_replication = True
                        continue
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/uom.category/create"
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=uom_category_data)
                        stores_data.raise_for_status()
                        # Raise an exception for HTTP errors
                        stores_data.raise_for_status()

                        # Access the JSON content from the response
                        response_json = stores_data.json()

                        # Access specific values from the response (e.g., "message" or "responseCode")
                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create UOM Category {message} '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error: ")
                            logging.error(
                                f"Failed to create UOM Category  {message} '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error:")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                'add', 'failure', message)
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add', 'failure',
                                                                                          message)
                        else:
                            line.date_replication = True
                            self.update_replication = True
                            _logger.info(
                                f"Successfully created UOM Category {self.name} {message} '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'.")
                            logging.info(
                                f"Successfully created UOM Category {self.name} {message} '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                'add', 'success',  f"Successfully created UOM Category {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add', 'success',
                                                                                           f"Successfully created UOM Category {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(
                            f" '{self.name}'Failed to create UOM Category '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error: {e}")
                        logging.error(
                            f" '{self.name}' Failed to create UOM Category '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error: {e}")
                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('uom.category',
                                                                        self.id, 500,'add', 'failure',
                                                                        e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('uom.category',
                                                                        self.id, 500,'add', 'failure',
                                                                        e)
                except requests.exceptions.RequestException as e:
                    _logger.info(f" '{self.name}' Error checking UOM Category on '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error: {e}")
                    logging.error(f" '{self.name}' Error checking UOM Category on '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error: {e}")

    def update_uom_category_data(self):
        for line in self.nhcl_product_uom_ids:
            ho_ip = line.nhcl_terminal_ip
            ho_port = line.nhcl_port_no
            ho_api_key = line.nhcl_api_key
            store_url_data = f"http://{ho_ip}:{ho_port}/api/uom.category/search"
            store_url_data2 = f"http://{ho_ip}:{ho_port}/api/uom.uom/search"
            uom_category_domain = self.name
            uom_domain = [('name', '=', uom_category_domain)]
            store_url = f"{store_url_data}?domain={uom_domain}"
            headers_source = {'api-key': ho_api_key, 'Content-Type': 'application/json'}

            try:
                # Step 1: Retrieve the existing attribute
                response = requests.get(store_url, headers=headers_source)
                response.raise_for_status()
                data = response.json()
                attribute_id_data = data.get("data", [])

                if not attribute_id_data:
                    _logger.warning(f"No matching product attribute found for '{self.name}'. Skipping update.")
                    continue

                attribute_id = attribute_id_data[0].get('id')
                store_url1 = f"{store_url_data2}"
                payload = {'domain': [('attribute_id', '=', attribute_id)]}

                # Retrieve attribute values based on attribute_id
                response1 = requests.get(store_url1, headers=headers_source, json=payload)
                response1.raise_for_status()
                data1 = response1.json()
                attribute_value_data = data1.get("data", [])
                # Log the attribute value data
                _logger.debug(f"Retrieved attribute value data: {attribute_value_data}")

                # Check if the attribute ID was retrieved
                if not attribute_id:
                    _logger.error(f"Attribute ID not found for '{self.name}' in response. Skipping update.")
                    continue

                # Step 2: Prepare the update data
                product_attribute_line = []
                for data in self.uom_ids:
                    search_store_attribute = f"http://{ho_ip}:{ho_port}/api/uom.uom/search"
                    attribute1_domain = [('name', '=', data.name)]
                    attribute_url = f"{search_store_attribute}?domain={attribute1_domain}"
                    attribute_response = requests.get(attribute_url,
                                                      headers=headers_source)
                    attribute_response.raise_for_status()  # Raise an exception for bad responses
                    attribute_data = attribute_response.json()
                    attribute_data1 = attribute_data.get("data", [])
                    if attribute_data1:
                        existing_value = attribute_data1[0]['id']
                    # Check if the value already exists in destination (attribute_value_data)
                    # existing_value = next((val for val in attribute_value_data if val.get('name') == data.name),
                    #                       None)

                        # If the value exists, use the existing ID and update the values
                        product_attribute_line.append([1, existing_value, {
                            'name': data.name,
                            'uom_type': data.uom_type,
                            'factor': data.factor,
                            'factor_inv': data.factor_inv,
                            'ratio': data.ratio,
                            'rounding': data.rounding
                        }])

                    else:
                        # If the value doesn't exist, create a new one
                        product_attribute_line.append([0, 0, {
                            'name': data.name,
                            'uom_type': data.uom_type,
                            'factor': data.factor,
                            'factor_inv': data.factor_inv,
                            'ratio': data.ratio,
                            'rounding': data.rounding
                        }])

                # Log the product_attribute_line data for debugging
                _logger.debug(f"Prepared product attribute line: {product_attribute_line}")

                # Construct the full product attribute list
                product_attribute_list = {
                    'name': self.name,
                    'uom_ids': product_attribute_line,
                }

                # Log the final data for debugging
                _logger.debug(f"Product attribute data prepared for update: {product_attribute_list}")

                # Step 3: Send the update request
                store_url_data1 = f"http://{ho_ip}:{ho_port}/api/uom.category/{attribute_id}"
                update_response = requests.put(store_url_data1, headers=headers_source, json=product_attribute_list)
                update_response.raise_for_status()

                # Step 4: Update the status upon success
                line.update_status = True
                self.update_status = True
                _logger.info(f"Successfully updated UOM '{self.name}' at '{ho_ip}:{ho_port}'.")
                logging.info(f"Successfully updated UOM '{self.name}' at '{ho_ip}:{ho_port}'.")
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log('uom.category',
                                                                    self.id, 200, 'update', 'success',
                                                                    f"Successfully updated UOM '{self.name}'")
                else:
                    line.master_store_id.create_cmr_old_store_replication_log('uom.category',
                                                                              self.id, 200, 'update', 'success',
                                                                              f"Successfully updated UOM '{self.name}'")
            except requests.exceptions.RequestException as e:
                _logger.error(f"Failed to update UOM '{self.name}' at '{ho_ip}:{ho_port}'. Error: {e}")
                logging.error(f"Failed to update UOM '{self.name}' at '{ho_ip}:{ho_port}'. Error: {e}")
                line.update_status = False
                self.update_status = False
                # if line.master_store_id.nhcl_sink == False:
                #     line.master_store_id.create_cmr_replication_log(data['object_name'],
                #                                                     self.id, 500, 'update', 'failure',
                #                                                     e)
                # else:
                #     line.master_store_id.create_cmr_old_store_replication_log(data['object_name'],
                #                                                               self.id, 500, 'update', 'failure',
                #                                                               e)


class UoM(models.Model):
    _inherit = 'uom.uom'

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)

    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM uom_uom")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(UoM, self).create(vals)


class ProductUomReplication(models.Model):
    _name = 'product.uom.replication'

    product_uom_id = fields.Many2one('uom.category', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')

