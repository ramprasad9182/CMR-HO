import requests
import json
from odoo import models, fields, api, _
import logging
from urllib.parse import quote
_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_replication_id = fields.One2many('product.replication', 'product_replication_id')
    update_replication = fields.Boolean(string="Creation Status")
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')

    @api.model
    def get_pending_template(self):
        pending_template = self.search_count([('update_replication', '=', False), ('detailed_type','in',['product','consu'])])
        return {
            'pending_template': pending_template,
        }

    def get_product_temp_stores(self):
        return {
            'name': _('Product Template'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.product_temp',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_product_temp_view').id,
            'context': {'create': False, 'delete': False, 'duplicate': False,'default_nhcl_selected_ids': self.ids},
        }


    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM product_template")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(ProductTemplate, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def get_stores_data(self):
        for line in self:
            replication_data = []
            ho_store_id = self.env['nhcl.ho.store.master'].search(
                [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])

            for rec in line.product_replication_id:
                if rec.nhcl_terminal_ip not in ho_store_id.mapped('nhcl_terminal_ip'):
                    rec.sudo().unlink()
                elif rec.nhcl_api_key not in ho_store_id.mapped('nhcl_api_key'):
                    rec.sudo().unlink()
            existing_store_ids = []
            if line.product_replication_id:
                existing_store_ids = line.product_replication_id.mapped('store_id.id')

            for i in ho_store_id:
                for j in i.nhcl_store_data_id:
                    if j.model_id.name == 'Product' and j.nhcl_line_data == True:
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
            if replication_data:
                line.update({'product_replication_id': replication_data})

    def send_replication_data(self):
        get_records = []
        for line in self.product_replication_id:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                product_category_search_url = f"http://{ho_ip}:{ho_port}/api/product.category/search"
                category_name = self.categ_id.nhcl_id
                print(category_name)
                # category_domain = [('name','=',category_name)]
                category_domain = f"?domain=[('nhcl_id','=',\"{category_name}\")]"
                category_url_data = product_category_search_url + category_domain
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                search_store_url_data = f"http://{ho_ip}:{ho_port}/api/product.template/search"
                prod_tmpl_domain = [('nhcl_id', '=', self.nhcl_id)]
                store_url = f"{search_store_url_data}?domain={prod_tmpl_domain}"

                search_store_attribute_value = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                # prod_tmpl_domain = [('name', '=', self.name), ('default_code', '=', self.default_code)]
                # store_url = f"{search_store_url_data}?domain={prod_tmpl_domain}"
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()  # Raise an exception for bad responses
                    data = response.json()
                    product_data = data.get("data", [])

                    attribute_value_response = requests.get(search_store_attribute_value, headers=headers_source)
                    attribute_value_response.raise_for_status()  # Raise an exception for bad responses
                    attribute_value_data = attribute_value_response.json()
                    attribute_value_data1 = attribute_value_data.get("data", [])
                    # Check if Product already exists
                    if product_data:
                        _logger.info(f" '{self.name}' Already exists as Product on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(f" '{self.name}' Already exists as Product on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        self.update_replication = True
                        continue

                    store_url_data = f"http://{ho_ip}:{ho_port}/api/product.template/create"
                    category_get_data = requests.get(category_url_data, headers=headers_source).json()
                    category_id_data = category_get_data.get("data", [])
                    print("category_id_data",category_id_data)
                    if category_id_data:
                        category_id = category_id_data[0]['id']
                        print(category_id)
                    else:
                        category_id = None
                        _logger.info(f"No Category found with '{self.name}'. Skipping replication.")
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log(category_get_data['object_name'],
                                                                            self.id, 500, 'add',
                                                                            'failure',
                                                                            f"No Category found with '{self.name}'. Skipping replication.")
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log(
                                category_get_data['object_name'], self.id, 500,
                                'add', 'failure', 'No matching product attributes found. Skipping this attribute.')

                        # continue
                    product_attribute_line = []
                    for data in self.attribute_line_ids:
                        search_store_attribute = f"http://{ho_ip}:{ho_port}/api/product.attribute/search"
                        attribute1_domain = [('nhcl_id', '=', data.attribute_id.nhcl_id)]
                        attribute_url = f"{search_store_attribute}?domain={attribute1_domain}"
                        attribute_response = requests.get(attribute_url,
                                                          headers=headers_source)
                        attribute_response.raise_for_status()  # Raise an exception for bad responses
                        attribute_data = attribute_response.json()
                        attribute_data1 = attribute_data.get("data", [])
                        print("attribute_data1",attribute_data1)
                        attribute_id = False
                        if attribute_data1:
                            attribute_id = attribute_data1[0]['id']

                        value_ids = []
                        for da_val in data.value_ids:
                            search_store_attribute_value = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                            attribute_domain = [('nhcl_id', '=', da_val.nhcl_id)]
                            attribute_value_url = f"{search_store_attribute_value}?domain={attribute_domain}"
                            attribute_value_response = requests.get(attribute_value_url,
                                                                    headers=headers_source)
                            attribute_value_response.raise_for_status()  # Raise an exception for bad responses
                            attribute_value_data = attribute_value_response.json()
                            attribute_value_data1 = attribute_value_data.get("data", [])
                            if attribute_value_data1:
                                if attribute_value_data1[0]['nhcl_id'] == da_val.nhcl_id:
                                    value_ids.append(attribute_value_data1[0]['id'])
                        product_attribute_line.append((0, 0, {
                            'attribute_id': attribute_id,
                            'value_ids': value_ids,
                        }))
                    taxes = []
                    for tax_id in self.taxes_id:
                        search_store_url_tax_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                        tax_domain = [('name', '=', tax_id.name)]
                        tax_store_url = f"{search_store_url_tax_data}?domain={tax_domain}"
                        tax_data = requests.get(tax_store_url, headers=headers_source).json()
                        if not tax_data.get("data"):
                            continue
                        tax_name = tax_data.get("data")[0]
                        taxes.append(tax_name["id"])

                    print("product_attribute_line",product_attribute_line)
                    product_list = {
                        'name': self.name,
                        'nhcl_id':self.nhcl_id,
                        'category_abbr': self.category_abbr,
                        'uom_id': self.uom_id.id if self.uom_id else False,
                        'uom_po_id': self.uom_po_id.id if self.uom_po_id else False,
                        'detailed_type': self.detailed_type if self.detailed_type else None,
                        'nhcl_type': self.nhcl_type if self.nhcl_type else None,
                        'nhcl_product_type': self.nhcl_product_type if self.nhcl_product_type else None,
                        'invoice_policy': self.invoice_policy if self.invoice_policy else None,
                        'segment': self.segment if self.segment else None,
                        'list_price': self.list_price if self.list_price else None,
                        'available_in_pos': self.available_in_pos if self.available_in_pos else None,
                        'tracking': self.tracking if self.tracking else None,
                        'categ_id': category_id,
                        'l10n_in_hsn_code': self.l10n_in_hsn_code if self.l10n_in_hsn_code else None,
                        'default_code': self.default_code if self.default_code else None,
                        'web_product': self.web_product if self.web_product else None,
                        'product_description': self.product_description if self.product_description else None,
                        'to_weight': self.to_weight if self.to_weight else None,
                        'weight': self.weight if self.weight else None,
                        'volume': self.volume if self.volume else None,
                        'sale_delay': self.sale_delay if self.sale_delay else None,
                        'purchase_method': self.purchase_method if self.purchase_method else None,
                        'product_tag_ids': [tag.id for tag in self.product_tag_ids] if self.product_tag_ids else False,
                        'optional_product_ids': [product.id for product in self.optional_product_ids] if self.optional_product_ids else False,
                        'taxes_id': taxes,
                        'supplier_taxes_id': taxes,
                        # 'pos_categ_ids': [categ.id for categ in self.pos_categ_ids] if self.pos_categ_ids else False,
                        # 'route_ids': [route.id for route in self.route_ids] if self.route_ids else False,
                        'responsible_id': self.responsible_id.id if self.responsible_id else False,
                        'property_stock_production': self.property_stock_production.id if self.property_stock_production else False,
                        'property_stock_inventory': self.property_stock_inventory.id if self.property_stock_inventory else False,
                        'property_account_income_id': self.property_account_income_id.id if self.property_account_income_id else False,
                        'property_account_expense_id': self.property_account_expense_id.id if self.property_account_expense_id else False,
                        'property_account_creditor_price_difference': self.property_account_creditor_price_difference.id if self.property_account_creditor_price_difference else False,
                        'attribute_line_ids': product_attribute_line,
                    }
                    print("product_list",product_list)
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[product_list])
                        stores_data.raise_for_status()
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
                                f"Failed to create Product {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Product  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
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
                                f"Successfully create Product {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully create Product {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                'add', 'success', f"Successfully create Product {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add', 'success',
                                                                                          f"Successfully create Product {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(
                            f" '{self.name}'Failed to create Product '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                            f" '{self.name}' Failed to create Product '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('product.template',
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('product.template',
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(f" '{self.name}' Error checking Product on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Product on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
        return get_records

    def update_product_data(self):
        for line in self.product_replication_id:
            # if not line.update_status:
            ho_ip = line.nhcl_terminal_ip
            ho_port = line.nhcl_port_no
            ho_api_key = line.nhcl_api_key
            store_url_data = f"http://{ho_ip}:{ho_port}/api/product.template/search"
            store_url_data2 = f"http://{ho_ip}:{ho_port}/api/product.template.attribute.line/search"
            product_domain = self.nhcl_id
            prod_domain = [('nhcl_id', '=', product_domain)]
            store_url = f"{store_url_data}?domain={prod_domain}"
            headers_source = {'api-key': ho_api_key, 'Content-Type': 'application/json'}

            try:
                # Step 1: Retrieve the existing product template
                response = requests.get(store_url, headers=headers_source)
                response.raise_for_status()
                data = response.json()
                product_id_data = data.get("data", [])
                if not product_id_data:
                    _logger.warning(f"No matching product attribute found for '{self.name}'. Skipping update.")
                    continue
                product_tem_id = product_id_data[0].get('id')
                store_url1 = f"{store_url_data2}"
                prod_domain1 = [('product_tmpl_id', '=', product_tem_id)]
                store_url3 = f"{store_url1}?domain={prod_domain1}"

                # Retrieve attribute values based on attribute_id
                response1 = requests.get(store_url3, headers=headers_source)
                response1.raise_for_status()
                data1 = response1.json()
                product_templ_value_data = data1.get("data", [])
                product_templ_line = []

                # Check if local attribute_line_ids exist
                if not self.attribute_line_ids:
                    _logger.warning(f"No attribute lines found for '{self.name}'. Skipping update.")
                    continue

                for data in self.attribute_line_ids:
                    existing_value = next((val for val in product_templ_value_data if
                                           val.get('attribute_id')[0]['name'] == data.attribute_id.name),None)
                    search_store_attribute = f"http://{ho_ip}:{ho_port}/api/product.attribute/search"
                    attribute1_domain = [('nhcl_id', '=', data.attribute_id.nhcl_id)]
                    attribute_url = f"{search_store_attribute}?domain={attribute1_domain}"
                    attribute_response = requests.get(attribute_url,
                                                            headers=headers_source)
                    attribute_response.raise_for_status()  # Raise an exception for bad responses
                    attribute_data = attribute_response.json()
                    attribute_data1 = attribute_data.get("data", [])
                    attribute_id = attribute_data1[0]['id']

                    value_ids = []
                    for da_val in data.value_ids:
                        search_store_attribute_value = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                        attribute_domain = [('name', '=', da_val.name)]
                        domain_str = json.dumps(attribute_domain)
                        encoded_domain = quote(domain_str)
                        attribute_value_url = f"{search_store_attribute_value}?domain={encoded_domain}"
                        attribute_value_response = requests.get(attribute_value_url,
                                                                headers=headers_source)
                        attribute_value_response.raise_for_status()  # Raise an exception for bad responses
                        attribute_value_data = attribute_value_response.json()
                        attribute_value_data1 = attribute_value_data.get("data", [])
                        if attribute_value_data1:
                            if attribute_value_data1[0]['nhcl_id'] == da_val.nhcl_id:
                                value_ids.append(attribute_value_data1[0]['id'])

                    if existing_value:
                        product_templ_line.append([1, existing_value['id'], {
                            'attribute_id': attribute_id,
                            'value_ids': value_ids,
                        }])
                    else:

                        product_templ_line.append([0, 0, {
                            'attribute_id': attribute_id,
                            'value_ids': value_ids,
                        }])

                # Debugging: Log the product attribute line
                _logger.debug(f"Prepared product attribute line (create & update): {product_templ_line}")
                taxes = []
                for tax_id in self.taxes_id:
                    search_store_url_tax_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                    tax_domain = [('name', '=', tax_id.name)]
                    tax_store_url = f"{search_store_url_tax_data}?domain={tax_domain}"
                    tax_data = requests.get(tax_store_url, headers=headers_source).json()
                    if not tax_data.get("data"):
                        continue
                    tax_name = tax_data.get("data")[0]
                    taxes.append(tax_name["id"])
                # Construct the full product template update payload
                product_templ_list = {
                    'name': self.name,
                    'nhcl_product_type': self.nhcl_product_type,
                    'detailed_type': self.detailed_type,
                    'nhcl_type': self.nhcl_type,
                    'available_in_pos': self.available_in_pos,
                    'tracking': self.tracking,
                    'default_code': self.default_code,
                    'l10n_in_hsn_code': self.l10n_in_hsn_code if self.l10n_in_hsn_code else None,
                    'taxes_id': taxes,
                    'supplier_taxes_id': taxes,
                    'attribute_line_ids': product_templ_line,
                }

                # Log the final product template data
                _logger.debug(f"Product template data prepared for update: {product_templ_list}")

                # URL to update the product template
                store_url_data1 = f"http://{ho_ip}:{ho_port}/api/product.template/{product_tem_id}"

                # Send the update request
                update_response = requests.put(store_url_data1, headers=headers_source, json=product_templ_list)
                update_response.raise_for_status()
                # Update status upon successful update
                line.update_status = True
                self.update_status = True
                _logger.info(f"'{self.name}' Successfully updated Product '{ho_ip}' with partner '{ho_port}'.")
                logging.info(f"'{self.name}' Successfully updated Product '{ho_ip}' with partner '{ho_port}'.")
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log('product.template',
                                                                    self.id, 200, 'update', 'success',
                                                                    f"'{self.name}' Successfully updated Product")
                else:
                    line.master_store_id.create_cmr_old_store_replication_log('product.template',
                                                                              self.id, 200, 'update', 'success',
                                                                              f"'{self.name}' Successfully updated Product")
            except requests.exceptions.RequestException as e:
                _logger.error(
                    f"'{self.name}' Failed to update Product '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                logging.error(
                    f"'{self.name}' Failed to update Product '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                line.update_status = False
                self.update_status = False
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log('product.template',
                                                                    self.id, 500, 'update', 'failure',
                                                                    e)
                else:
                    line.master_store_id.create_cmr_old_store_replication_log('product.template',
                                                                              self.id, 500, 'update', 'failure',
                                                                              e)

    def send_replication_data_to_store(self, stores):
        for line in stores:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                product_category_search_url = f"http://{ho_ip}:{ho_port}/api/product.category/search"
                category_name = self.categ_id.nhcl_id
                print(category_name)
                # category_domain = [('name','=',category_name)]
                category_domain = f"?domain=[('nhcl_id','=',\"{category_name}\")]"
                category_url_data = product_category_search_url + category_domain
                # category_url_data = f"{product_category_search_url}?domain={category_domain}"
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                search_store_url_data = f"http://{ho_ip}:{ho_port}/api/product.template/search"
                prod_tmpl_domain = [('nhcl_id', '=', self.nhcl_id)]
                store_url = f"{search_store_url_data}?domain={prod_tmpl_domain}"

                search_store_attribute_value = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                # prod_tmpl_domain = [('name', '=', self.name), ('default_code', '=', self.default_code)]
                # store_url = f"{search_store_url_data}?domain={prod_tmpl_domain}"
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()  # Raise an exception for bad responses
                    data = response.json()
                    product_data = data.get("data", [])

                    attribute_value_response = requests.get(search_store_attribute_value, headers=headers_source)
                    attribute_value_response.raise_for_status()  # Raise an exception for bad responses
                    attribute_value_data = attribute_value_response.json()
                    attribute_value_data1 = attribute_value_data.get("data", [])
                    # Check if Product already exists
                    if product_data:
                        _logger.info(f" '{self.name}' Already exists as Product on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(f" '{self.name}' Already exists as Product on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        continue

                    store_url_data = f"http://{ho_ip}:{ho_port}/api/product.template/create"
                    category_get_data = requests.get(category_url_data, headers=headers_source).json()
                    category_id_data = category_get_data.get("data", [])
                    print("category_id_data", category_id_data)
                    if category_id_data:
                        category_id = category_id_data[0]['id']
                        print(category_id)
                    else:
                        category_id = None
                        _logger.info(f"No Category found with '{self.name}'. Skipping replication.")
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log(category_get_data['object_name'],
                                                                            self.id, 500, 'add',
                                                                            'failure',
                                                                            f"No Category found with '{self.name}'. Skipping replication.")
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log(
                                category_get_data['object_name'], self.id, 500,
                                'add', 'failure', 'No matching product attributes found. Skipping this attribute.')

                        # continue
                    product_attribute_line = []
                    for data in self.attribute_line_ids:
                        search_store_attribute = f"http://{ho_ip}:{ho_port}/api/product.attribute/search"
                        attribute1_domain = [('nhcl_id', '=', data.attribute_id.nhcl_id)]
                        attribute_url = f"{search_store_attribute}?domain={attribute1_domain}"
                        attribute_response = requests.get(attribute_url,
                                                          headers=headers_source)
                        attribute_response.raise_for_status()  # Raise an exception for bad responses
                        attribute_data = attribute_response.json()
                        attribute_data1 = attribute_data.get("data", [])
                        print("attribute_data1", attribute_data1)
                        attribute_id = False
                        if attribute_data1:
                            attribute_id = attribute_data1[0]['id']

                        value_ids = []
                        for da_val in data.value_ids:
                            search_store_attribute_value = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                            attribute_domain = [('nhcl_id', '=', da_val.nhcl_id)]
                            attribute_value_url = f"{search_store_attribute_value}?domain={attribute_domain}"
                            attribute_value_response = requests.get(attribute_value_url,
                                                                    headers=headers_source)
                            attribute_value_response.raise_for_status()  # Raise an exception for bad responses
                            attribute_value_data = attribute_value_response.json()
                            attribute_value_data1 = attribute_value_data.get("data", [])
                            if attribute_value_data1:
                                if attribute_value_data1[0]['nhcl_id'] == da_val.nhcl_id:
                                    value_ids.append(attribute_value_data1[0]['id'])
                        product_attribute_line.append((0, 0, {
                            'attribute_id': attribute_id,
                            'value_ids': value_ids,
                        }))
                    taxes = []
                    for tax_id in self.taxes_id:
                        search_store_url_tax_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                        tax_domain = [('name', '=', tax_id.name)]
                        tax_store_url = f"{search_store_url_tax_data}?domain={tax_domain}"
                        tax_data = requests.get(tax_store_url, headers=headers_source).json()
                        if not tax_data.get("data"):
                            continue
                        tax_name = tax_data.get("data")[0]
                        taxes.append(tax_name["id"])
                    search_store_url_uom_uom_data = f"http://{ho_ip}:{ho_port}/api/uom.uom/search"
                    uom_domain = [('name', '=', self.uom_id.name)]
                    uom_store_url = f"{search_store_url_uom_uom_data}?domain={uom_domain}"
                    uom_data = requests.get(uom_store_url, headers=headers_source).json()
                    if not uom_data.get("data"):
                        continue
                    uom_name = uom_data.get("data")[0]
                    search_store_url_purchase_uom_uom_data = f"http://{ho_ip}:{ho_port}/api/uom.uom/search"
                    purchase_uom_domain = [('name', '=', self.uom_po_id.name)]
                    purchase_uom_store_url = f"{search_store_url_purchase_uom_uom_data}?domain={purchase_uom_domain}"
                    purchase_uom_data = requests.get(purchase_uom_store_url, headers=headers_source).json()
                    if not purchase_uom_data.get("data"):
                        continue
                    purchase_uom_id = purchase_uom_data.get("data")[0]
                    print("product_attribute_line", product_attribute_line)
                    product_list = {
                        'name': self.name,
                        'nhcl_id': self.nhcl_id,
                        'category_abbr': self.category_abbr,
                        'uom_id': uom_name["id"] if uom_name else False,
                        'uom_po_id': purchase_uom_id['id'] if purchase_uom_id else False,
                        'detailed_type': self.detailed_type if self.detailed_type else None,
                        'nhcl_type': self.nhcl_type if self.nhcl_type else None,
                        'nhcl_product_type': self.nhcl_product_type if self.nhcl_product_type else None,
                        'invoice_policy': self.invoice_policy if self.invoice_policy else None,
                        'segment': self.segment if self.segment else None,
                        'list_price': self.list_price if self.list_price else None,
                        'available_in_pos': self.available_in_pos if self.available_in_pos else None,
                        'tracking': self.tracking if self.tracking else None,
                        'categ_id': category_id,
                        'l10n_in_hsn_code': self.l10n_in_hsn_code if self.l10n_in_hsn_code else None,
                        'default_code': self.default_code if self.default_code else None,
                        'web_product': self.web_product if self.web_product else None,
                        'product_description': self.product_description if self.product_description else None,
                        'to_weight': self.to_weight if self.to_weight else None,
                        'weight': self.weight if self.weight else None,
                        'volume': self.volume if self.volume else None,
                        'sale_delay': self.sale_delay if self.sale_delay else None,
                        'purchase_method': self.purchase_method if self.purchase_method else None,
                        'product_tag_ids': [tag.id for tag in self.product_tag_ids] if self.product_tag_ids else False,
                        'optional_product_ids': [product.id for product in
                                                 self.optional_product_ids] if self.optional_product_ids else False,
                        'taxes_id': taxes,
                        'supplier_taxes_id': taxes,
                        # 'pos_categ_ids': [categ.id for categ in self.pos_categ_ids] if self.pos_categ_ids else False,
                        # 'route_ids': [route.id for route in self.route_ids] if self.route_ids else False,
                        'responsible_id': self.responsible_id.id if self.responsible_id else False,
                        'property_stock_production': self.property_stock_production.id if self.property_stock_production else False,
                        'property_stock_inventory': self.property_stock_inventory.id if self.property_stock_inventory else False,
                        'property_account_income_id': self.property_account_income_id.id if self.property_account_income_id else False,
                        'property_account_expense_id': self.property_account_expense_id.id if self.property_account_expense_id else False,
                        'property_account_creditor_price_difference': self.property_account_creditor_price_difference.id if self.property_account_creditor_price_difference else False,
                        'attribute_line_ids': product_attribute_line if product_attribute_line else False,
                    }
                    print("product_list", product_list)
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[product_list])
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
                                f"Failed to create Product {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Product  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
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
                            _logger.info(
                                f"Successfully create Product {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully create Product {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id,
                                                                                200,
                                                                                'add', 'success',
                                                                                f"Successfully create Product {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add',
                                                                                          'success',
                                                                                          f"Successfully create Product {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(
                            f" '{self.name}'Failed to create Product '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                            f" '{self.name}' Failed to create Product '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('product.template',
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('product.template',
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Product on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Product on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
        self.env.cr.commit()


class ProductReplication(models.Model):
    _name = 'product.replication'

    product_replication_id = fields.Many2one('product.template', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')

