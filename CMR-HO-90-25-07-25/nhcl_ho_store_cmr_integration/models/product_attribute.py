import requests

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    update_replication = fields.Boolean(string="Creation Status")
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    product_attribute_replication_id = fields.One2many('product.attribute.replication', 'product_attribute_replication_line_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')

    @api.model
    def get_pending_attribute(self):
        pending_attribute = self.search_count([('update_replication', '=', False)])
        return {
            'pending_attribute': pending_attribute,
        }

    def get_product_attribute_stores(self):
        return {
            'name': _('Product Attributes'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.attribute',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_attribute_view').id,
            'context': {'create': False, 'delete': False, 'duplicate': False,'default_nhcl_selected_ids': self.ids},
        }

    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM product_attribute")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(ProductAttribute, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def get_stores_data(self):
        for store in self:
            existing_store_ids = store.product_attribute_replication_id.mapped('store_id.id')
            replication_data = []
            ho_store_id = store.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
            for rec in store.product_attribute_replication_id:
                if rec.nhcl_terminal_ip not in ho_store_id.mapped('nhcl_terminal_ip'):
                    rec.unlink()
                elif rec.nhcl_api_key not in ho_store_id.mapped('nhcl_api_key'):
                    rec.unlink()
            for i in ho_store_id:
                for j in i.nhcl_store_data_id:
                    if j.model_id.name == 'Product Attribute' and j.nhcl_line_data == True:
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
            store.update({'product_attribute_replication_id': replication_data})

    def send_replication_data(self):
        product_attribute_line = []
        for data in self.value_ids:
            product_attribute_line.append((0, 0, {
                'name': data.name,
                'nhcl_id': data.nhcl_id,
                'is_custom': data.is_custom,
                'html_color': data.html_color,
                'image': data.image,
                'default_extra_price': data.default_extra_price,

            }))

        product_attribute_list = {
            'name': self.name if self.name else None,
            'nhcl_id': self.nhcl_id,
            'display_type': self.display_type if self.display_type else None,
            'create_variant': self.create_variant if self.create_variant else None,
            'value_ids': product_attribute_line,
        }
        get_records = []
        for line in self.product_attribute_replication_id:
            if line.date_replication == False and line.status == True:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                store_url_data = f"http://{ho_ip}:{ho_port}/api/product.attribute/search"
                attribute_domain = [('nhcl_id', '=', self.nhcl_id), ('display_type', '=', self.display_type)]
                store_url = f"{store_url_data}?domain={attribute_domain}"
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()  # Raise an exception for bad responses
                    data = response.json()
                    attribute_data = data.get("data", [])

                    # Check if Attribute already exists
                    if attribute_data:
                        _logger.info(f" '{self.name}' Already exists as Attribute on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(f" '{self.name}' Already exists as Attribute on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        self.update_replication = True
                        continue
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/product.attribute/create"
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[product_attribute_list])
                        stores_data.raise_for_status()  # Raises an HTTPError if the status code is 4xx, 5xx
                        # Raise an exception for HTTP errors
                        stores_data.raise_for_status()

                        # Access the JSON content from the response
                        response_json = stores_data.json()

                        if 'create_id' in response_json:
                            get_records.append(response_json['create_id'])
                            get_records.append(line.store_id.id)

                        # Access specific values from the response (e.g., "message" or "responseCode")
                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Attribute {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Attribute  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
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
                                f"Successfully create Attribute {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully create Attribute {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                'add', 'success', f"Successfully create Attribute {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add', 'success',
                                                                                          f"Successfully create Attribute {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(f"Failed to create Attribute '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                            f" '{self.name}' Failed to create Attribute '{ho_ip}' with partner '{ho_port}'. Error: {e}")

                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log(data['object_name'],
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log(data['object_name'],
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Attribute on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Attribute on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                return get_records

    def update_attribute_data(self):
        for line in self.product_attribute_replication_id:
            # if not line.update_status:
            ho_ip = line.nhcl_terminal_ip
            ho_port = line.nhcl_port_no
            ho_api_key = line.nhcl_api_key
            store_url_data = f"http://{ho_ip}:{ho_port}/api/product.attribute/search"
            store_url_data2 = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
            attribute_domain = self.nhcl_id
            attri_domain = [('nhcl_id', '=', attribute_domain)]
            store_url = f"{store_url_data}?domain={attri_domain}"
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

                # Debugging: Check the raw response data
                print("Raw response data:", data1)
                _logger.debug(f"Raw response data from store_url1: {data1}")

                # Log the attribute value data
                print("attribute_value_data", attribute_value_data)
                _logger.debug(f"Retrieved attribute value data: {attribute_value_data}")

                # Check if the attribute ID was retrieved
                if not attribute_id:
                    _logger.error(f"Attribute ID not found for '{self.name}' in response. Skipping update.")
                    continue

                # Step 2: Prepare the update data
                product_attribute_line = []
                for data in self.value_ids:
                    search_store_attribute = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                    attribute1_domain = [('nhcl_id', '=', data.nhcl_id)]
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
                            'nhcl_id': data.nhcl_id,
                            'is_custom': data.is_custom,
                            'html_color': data.html_color,
                            'image': data.image,
                            'default_extra_price': data.default_extra_price
                        }])

                    else:
                        # If the value doesn't exist, create a new one
                        product_attribute_line.append([0, 0, {
                            'name': data.name,
                            'nhcl_id': data.nhcl_id,
                            'is_custom': data.is_custom,
                            'html_color': data.html_color,
                            'image': data.image,
                            'default_extra_price': data.default_extra_price
                        }])

                # Log the product_attribute_line data for debugging
                _logger.debug(f"Prepared product attribute line: {product_attribute_line}")
                print("product_attribute_line", product_attribute_line)

                # Construct the full product attribute list
                product_attribute_list = {
                    'name': self.name,
                    'display_type': self.display_type,
                    'create_variant': self.create_variant,
                    'value_ids': product_attribute_line,
                }

                # Log the final data for debugging
                _logger.debug(f"Product attribute data prepared for update: {product_attribute_list}")
                print(product_attribute_list)

                # Step 3: Send the update request
                store_url_data1 = f"http://{ho_ip}:{ho_port}/api/product.attribute/{attribute_id}"
                print(store_url_data1)
                update_response = requests.put(store_url_data1, headers=headers_source, json=product_attribute_list)
                update_response.raise_for_status()
                print(update_response)

                # Step 4: Update the status upon success
                line.update_status = True
                self.update_status = True
                _logger.info(f"Successfully updated attribute '{self.name}' at '{ho_ip}:{ho_port}'.")
                logging.info(f"Successfully updated attribute '{self.name}' at '{ho_ip}:{ho_port}'.")
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log('product.attribute',
                                                                    self.id, 200, 'update', 'success',
                                                                    f"Successfully updated attribute '{self.name}'")
                else:
                    line.master_store_id.create_cmr_old_store_replication_log('product.attribute',
                                                                              self.id, 200, 'update', 'success',
                                                                              f"Successfully updated attribute '{self.name}'")
            except requests.exceptions.RequestException as e:
                _logger.error(f"Failed to update attribute '{self.name}' at '{ho_ip}:{ho_port}'. Error: {e}")
                logging.error(f"Failed to update attribute '{self.name}' at '{ho_ip}:{ho_port}'. Error: {e}")
                line.update_status = False
                self.update_status = False
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log(data['object_name'],
                                                                    self.id, 500, 'update', 'failure',
                                                                    e)
                else:
                    line.master_store_id.create_cmr_old_store_replication_log(data['object_name'],
                                                                              self.id, 500, 'update', 'failure',
                                                                              e)

    def send_replication_data_to_store(self,store_id):
        product_attribute_line = []
        for data in self.value_ids:
            product_attribute_line.append((0, 0, {
                'name': data.name,
                'nhcl_id': data.nhcl_id,
                'is_custom': data.is_custom,
                'html_color': data.html_color,
                'image': data.image,
                'default_extra_price': data.default_extra_price,

            }))

        product_attribute_list = {
            'name': self.name if self.name else None,
            'nhcl_id': self.nhcl_id,
            'display_type': self.display_type if self.display_type else None,
            'create_variant': self.create_variant if self.create_variant else None,
            'value_ids': product_attribute_line,
        }

        for line in store_id:
            if line.date_replication == False and line.status == True:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                store_url_data = f"http://{ho_ip}:{ho_port}/api/product.attribute/search"
                attribute_domain = [('nhcl_id', '=', self.nhcl_id), ('display_type', '=', self.display_type)]
                store_url = f"{store_url_data}?domain={attribute_domain}"
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()  # Raise an exception for bad responses
                    data = response.json()
                    attribute_data = data.get("data", [])

                    # Check if Attribute already exists
                    if attribute_data:
                        _logger.info(f" '{self.name}' Already exists as Attribute on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(f" '{self.name}' Already exists as Attribute on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        continue
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/product.attribute/create"
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[product_attribute_list])
                        stores_data.raise_for_status()  # Raises an HTTPError if the status code is 4xx, 5xx
                        # Raise an exception for HTTP errors
                        stores_data.raise_for_status()

                        # Access the JSON content from the response
                        response_json = stores_data.json()

                        # Access specific values from the response (e.g., "message" or "responseCode")
                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Attribute {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Attribute  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                'add', 'failure', message)
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add', 'failure',
                                                                                          message)
                        else:
                            line.date_replication = True
                            _logger.info(
                                f"Successfully create Attribute {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully create Attribute {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                'add', 'success', f"Successfully create Attribute {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add', 'success',
                                                                                          f"Successfully create Attribute {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(f"Failed to create Attribute '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                            f" '{self.name}' Failed to create Attribute '{ho_ip}' with partner '{ho_port}'. Error: {e}")

                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log(data['object_name'],
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log(data['object_name'],
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Attribute on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Attribute on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class ProductAttributeReplication(models.Model):
    _name = 'product.attribute.replication'

    product_attribute_replication_line_id = fields.Many2one('product.attribute', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Creation status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')



class dev_transport_details(models.Model):
    _inherit = 'dev.transport.details'

    update_replication = fields.Boolean(string="Creation Status")
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    dev_transport_details_ids = fields.One2many('dev.transport.details.replication',
                                                       'dev_transport_details_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')

    # @api.model
    # def get_pending_attribute(self):
    #     pending_attribute = self.search_count([('update_replication', '=', False)])
    #     return {
    #         'pending_attribute': pending_attribute,
    #     }
    #
    # def get_product_attribute_stores(self):
    #     return {
    #         'name': _('Product Attributes'),
    #         'type': 'ir.actions.act_window',
    #         'target': 'new',
    #         'res_model': 'nhcl.bulk.attribute',
    #         'view_mode': 'form',
    #         'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_attribute_view').id,
    #         'context': {'create': False, 'delete': False, 'duplicate': False, 'default_nhcl_selected_ids': self.ids},
    #     }

    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM dev_transport_details")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(dev_transport_details, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def get_stores_data(self):
        existing_store_ids = self.dev_transport_details_ids.mapped('store_id.id')
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Transport Details' and j.nhcl_line_data == True:
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
        self.update({'dev_transport_details_ids': replication_data})

    def send_replication_data(self):
        dev_transport_details_data = {
            'name': self.name if self.name else None,
            'contact_name': self.contact_name if self.contact_name else None,
            'nhcl_id': self.nhcl_id,
            'street': self.street if self.street else None,
            'street2': self.street2 if self.street2 else None,
            'city': self.city if self.city else None,
            'zip': self.zip if self.zip else None,
            'comment': self.comment if self.comment else None,
            'phone': self.phone if self.phone else None,
            'mobile': self.mobile if self.mobile else None,
            'state_id': self.state_id.id if self.state_id else False,
            'country_id': self.country_id.id if self.country_id else False,
        }

        for line in self.dev_transport_details_ids:
            if line.date_replication == False:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                store_url_data = f"http://{ho_ip}:{ho_port}/api/dev.transport.details/search"
                transport_details_domain = [('nhcl_id', '=', self.nhcl_id)]
                store_url = f"{store_url_data}?domain={transport_details_domain}"
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()
                    data = response.json()
                    transport_details_data = data.get("data", [])

                    # Check if Attribute already exists
                    if transport_details_data:
                        _logger.info(f" '{self.name}' Already exists as Transporter on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(f" '{self.name}' Already exists as Transporter on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        self.update_replication = True
                        continue
                    print("product_attribute_list",dev_transport_details_data)
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/dev.transport.details/create"
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[dev_transport_details_data])
                        stores_data.raise_for_status()
                        stores_data.raise_for_status()
                        response_json = stores_data.json()
                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Transporter {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Transporter  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
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
                                f"Successfully create Transporter {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully create Transporter {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id,
                                                                                200,
                                                                                'add', 'success', f"Successfully create Transporter {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add',
                                                                                          'success',
                                                                                          f"Successfully create Transporter {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(f"Failed to create Transporter '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                            f" '{self.name}' Failed to create Transporter '{ho_ip}' with partner '{ho_port}'. Error: {e}")

                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log(data['object_name'],
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log(data['object_name'],
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Transporter on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Transporter on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class dev_transport_details_line(models.Model):
    _name = 'dev.transport.details.replication'

    dev_transport_details_id = fields.Many2one('dev.transport.details', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Creation status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')


class routes_details(models.Model):
    _inherit = 'dev.routes.details'

    update_replication = fields.Boolean(string="Creation Status")
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    dev_transport_route_ids = fields.One2many('dev.routes.details.replication',
                                                'dev_transport_route_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')

    # @api.model
    # def get_pending_attribute(self):
    #     pending_attribute = self.search_count([('update_replication', '=', False)])
    #     return {
    #         'pending_attribute': pending_attribute,
    #     }
    #
    # def get_product_attribute_stores(self):
    #     return {
    #         'name': _('Product Attributes'),
    #         'type': 'ir.actions.act_window',
    #         'target': 'new',
    #         'res_model': 'nhcl.bulk.attribute',
    #         'view_mode': 'form',
    #         'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_attribute_view').id,
    #         'context': {'create': False, 'delete': False, 'duplicate': False, 'default_nhcl_selected_ids': self.ids},
    #     }

    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM dev_routes_details")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(routes_details, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def get_stores_data(self):
        existing_store_ids = self.dev_transport_route_ids.mapped('store_id.id')
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Routes Details' and j.nhcl_line_data == True:
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
        self.update({'dev_transport_route_ids': replication_data})

    def send_replication_data(self):
        for line in self.dev_transport_route_ids:
            if line.date_replication == False:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                store_url_data = f"http://{ho_ip}:{ho_port}/api/dev.routes.details/search"
                transport_details_domain = [('nhcl_id', '=', self.nhcl_id)]
                store_url = f"{store_url_data}?domain={transport_details_domain}"
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()
                    data = response.json()
                    transport_details_data = data.get("data", [])

                    # Check if Attribute already exists
                    if transport_details_data:
                        _logger.info(
                            f" '{self.name}' Already exists as Transporter on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(
                            f" '{self.name}' Already exists as Transporter on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        self.update_replication = True
                        continue
                    location_details_data = []
                    source_location_id = False
                    for location in self.location_details_ids:
                        source_location_url = f"http://{ho_ip}:{ho_port}/api/dev.location.location/search"
                        source_location_domain = [('nhcl_id', '=', location.source_location_id.nhcl_id)]
                        source_location_data_url = f"{source_location_url}?domain={source_location_domain}"
                        source_location_data = requests.get(source_location_data_url,headers=headers_source).json()
                        source_location_ids = source_location_data.get("data")
                        if source_location_ids:
                            source_location_id = source_location_ids[0]["id"]
                        dest_location_domain = [('nhcl_id', '=', location.destination_location_id.nhcl_id)]
                        dest_location_data_url = f"{source_location_url}?domain={dest_location_domain}"
                        dest_location_data = requests.get(dest_location_data_url, headers=headers_source).json()
                        dest_location_ids = dest_location_data.get("data")
                        dest_location_id = False
                        if dest_location_ids:
                            dest_location_id = dest_location_ids[0]["id"]
                        location_details_data.append((0, 0, {
                            'source_location_id': source_location_id,
                            'nhcl_id': location.nhcl_id,
                            'destination_location_id': dest_location_id,
                            'distance': location.distance,
                            'transport_charges': location.transport_charges,
                            'time_hour': location.time_hour,

                        }))
                    transpoter_url = f"http://{ho_ip}:{ho_port}/api/dev.transport.details/search"
                    transpoter_domain = [('nhcl_id', '=', self.transpoter_id.nhcl_id)]
                    transpoter_data_url = f"{transpoter_url}?domain={transpoter_domain}"
                    transpoter_data = requests.get(transpoter_data_url, headers=headers_source).json()
                    transpoter = transpoter_data.get("data")
                    transpoter_id = transpoter[0]["id"]
                    dev_transport_route_data = {
                        'name': self.name if self.name else None,
                        'nhcl_id': self.nhcl_id,
                        'transpoter_id': transpoter_id,
                        'location_details_ids': location_details_data if location_details_data else False ,
                    }
                    print("product_attribute_list", dev_transport_route_data)
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/dev.routes.details/create"
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source,
                                                    json=[dev_transport_route_data])
                        stores_data.raise_for_status()
                        stores_data.raise_for_status()
                        response_json = stores_data.json()
                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Transporter {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Transporter  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id,
                                                                                200,
                                                                                'add', 'failure', message)
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add',
                                                                                          'failure',
                                                                                          message)
                        else:
                            line.date_replication = True
                            self.update_replication = True
                            _logger.info(
                                f"Successfully create Transporter {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully create Transporter {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id,
                                                                                200,
                                                                                'add', 'success', f"Successfully create Transporter {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add',
                                                                                          'success',
                                                                                          f"Successfully create Transporter {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(f"Failed to create Transporter '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                            f" '{self.name}' Failed to create Transporter '{ho_ip}' with partner '{ho_port}'. Error: {e}")

                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log(data['object_name'],
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log(data['object_name'],
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Transporter on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Transporter on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class routes_details_line(models.Model):
    _name = 'dev.routes.details.replication'

    dev_transport_route_id = fields.Many2one('dev.routes.details', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Creation status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')


class location_location(models.Model):
    _inherit = 'dev.location.location'

    update_replication = fields.Boolean(string="Creation Status")
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    dev_location_ids = fields.One2many('dev.location.replication',
                                                'dev_location_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')

    # @api.model
    # def get_pending_attribute(self):
    #     pending_attribute = self.search_count([('update_replication', '=', False)])
    #     return {
    #         'pending_attribute': pending_attribute,
    #     }
    #
    # def get_product_attribute_stores(self):
    #     return {
    #         'name': _('Product Attributes'),
    #         'type': 'ir.actions.act_window',
    #         'target': 'new',
    #         'res_model': 'nhcl.bulk.attribute',
    #         'view_mode': 'form',
    #         'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_attribute_view').id,
    #         'context': {'create': False, 'delete': False, 'duplicate': False, 'default_nhcl_selected_ids': self.ids},
    #     }

    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM dev_location_location")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(location_location, self).create(vals)

    @api.depends('update_replication')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def get_stores_data(self):
        existing_store_ids = self.dev_location_ids.mapped('store_id.id')
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Location' and j.nhcl_line_data == True:
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
        self.update({'dev_location_ids': replication_data})

    def send_replication_data(self):
        dev_transport_details_data = {
            'name': self.name if self.name else None,
            'nhcl_id': self.nhcl_id,

        }

        for line in self.dev_location_ids:
            if line.date_replication == False:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                store_url_data = f"http://{ho_ip}:{ho_port}/api/dev.location.location/search"
                location_domain = [('nhcl_id', '=', self.nhcl_id)]
                store_url = f"{store_url_data}?domain={location_domain}"
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()
                    data = response.json()
                    location_data = data.get("data", [])

                    # Check if Attribute already exists
                    if location_data:
                        _logger.info(
                            f" '{self.name}' Already exists as Location on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(
                            f" '{self.name}' Already exists as Location on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        self.update_replication = True
                        continue
                    print("product_attribute_list", dev_transport_details_data)
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/dev.location.location/create"
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source,
                                                    json=[dev_transport_details_data])
                        stores_data.raise_for_status()
                        stores_data.raise_for_status()
                        response_json = stores_data.json()
                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Location {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Location  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id,
                                                                                200,
                                                                                'add', 'failure', message)
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add',
                                                                                          'failure',
                                                                                          message)
                        else:
                            line.date_replication = True
                            self.update_replication = True
                            _logger.info(
                                f"Successfully create Location {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully create Location {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id,
                                                                                200,
                                                                                'add', 'success', f"Successfully create Location {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add',
                                                                                          'success',
                                                                                          f"Successfully create Location {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(f"Failed to create Location '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                            f" '{self.name}' Failed to create Location '{ho_ip}' with partner '{ho_port}'. Error: {e}")

                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log(data['object_name'],
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log(data['object_name'],
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Location on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Location on '{ho_ip}' with partner '{ho_port}'. Error: {e}")



class location_location_line(models.Model):
    _name = 'dev.location.replication'

    dev_location_id = fields.Many2one('dev.location.location', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Creation status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')


