import requests
import json
from odoo import models, fields, api, _
import logging
from urllib.parse import quote
import random
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    product_replication_list_id = fields.One2many('product.product.replication', 'product_product_replication_id')
    update_replication = fields.Boolean(string="Creation Status")
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')
    nhcl_create_status = fields.Boolean(string="Create Status")
    nhcl_display_name = fields.Char(
        string="NHCL Display Name",
        compute="_compute_nhcl_display_name",store=True)
    # icode_barcode = fields.Char(string="ICode Barcode")

    @api.depends("name", "product_template_attribute_value_ids")
    def _compute_nhcl_display_name(self):
        for product in self:
            base_name = product.name or ""
            variant_values = product.product_template_attribute_value_ids.sorted(
                key=lambda v: (v.attribute_name or "", v.name or "")
            ).mapped("name")
            if variant_values:
                product.nhcl_display_name = f"{base_name} ({', '.join(variant_values)})"
            else:
                product.nhcl_display_name = base_name


    @api.model
    def get_pending_product(self):
        pending_product = self.search_count([('update_replication', '=', False),('detailed_type','in',['product','consu'])])
        return {
            'pending_product': pending_product,
        }

    def get_product_product_stores(self):
        return {
            'name': _('Users'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.product_prod',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_product_prod_view').id,
            'context': {'create': False, 'delete': False, 'duplicate': False,'default_nhcl_selected_ids': self.ids},
        }

    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM product_product")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        res = super(ProductProduct, self).create(vals)
        return res



    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def button_fetch_replication_data(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
        for line in self:
            replication_data = []
            no_ip_lines = line.product_replication_list_id.filtered(
                lambda x: x.nhcl_terminal_ip not in ho_store_id.mapped('nhcl_terminal_ip'))
            no_api_lines = line.product_replication_list_id.filtered(
                lambda x: x.nhcl_api_key not in ho_store_id.mapped('nhcl_api_key'))
            if no_ip_lines:
                no_ip_lines.unlink()
            elif no_api_lines:
                no_api_lines.unlink()
            existing_store_ids = line.product_replication_list_id.mapped('store_id.id')
            for i in ho_store_id:
                for j in i.nhcl_store_data_id:
                    if j.model_id.name == 'Product Variant' and j.nhcl_line_data == True:
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
            line.update({'product_replication_list_id': replication_data})

    def send_replication_data(self):
        for line in self.product_replication_list_id:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key

                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                try:
                    product_attribute_search_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"
                    variable_name = self.display_name
                    if '+' in variable_name:
                        variable_name = variable_name.replace("+", "%2B")
                    elif '&' in variable_name:
                        variable_name = variable_name.replace("&", "%26")
                    if self.default_code:
                        product_display_name = len(self.default_code)
                        # display_name = self.display_name[product_display_name + 3:]
                        varient_domain = [('nhcl_display_name', '=', self.nhcl_display_name)]
                        # varient_domain = [('nhcl_display_name', '=', "PEACOCK-BLUE MULTI COLOR-SILK ABSTRACT-PRINTED KURTA SET (S, Dry clean, Blue)")]
                    else:
                        varient_domain = [
                            ('nhcl_display_name', '=', self.nhcl_display_name)]
                    product_template_name = self.product_tmpl_id.name
                    domain_str = json.dumps(varient_domain)
                    encoded_domain = quote(domain_str)


                    varient_url_data = f"{product_attribute_search_url}?domain={encoded_domain}"
                    product_varient_get_data = requests.get(varient_url_data, headers=headers_source).json()
                    varient_id_data = product_varient_get_data.get("data", [])
                    if not varient_id_data:
                        _logger.info(f"No matching product varints founddd {self.product_tmpl_id.name}. Skipping this attribute.")
                        logging.info(f"No matching product varintsss found {self.product_tmpl_id.name}. Skipping this attribute.")
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log(product_varient_get_data['object_name'],
                                                                            self.id, 500, 'add',
                                                                            'failure',
                                                                            f'No matching product attributes found {self.product_tmpl_id.name}. Skipping this attribute.')
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log(
                                product_varient_get_data['object_name'], self.id, 500,
                                'add', 'failure', f'No matchinggg product attributes found {self.product_tmpl_id.name}. Skipping this attribute.')

                        continue
                    varient_id = varient_id_data[0]['id']
                    combination_indices = varient_id_data[0]['combination_indices']
                    product_list = {
                        'default_code': self.default_code,
                        'barcode': self.barcode,
                        'nhcl_id': self.nhcl_id,
                    }
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/product.product/{varient_id}"
                    response = requests.put(store_url_data, headers=headers_source, json=product_list)
                    response.raise_for_status()
                    response_json = response.json()
                    message = response_json.get("message", "No message provided")
                    response_code = response_json.get("responseCode", "No response code provided")
                    if response_json.get("success") == False:
                        _logger.info(
                            f"Failed to update Product Variant {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                        logging.error(
                            f"Failed to update Product Variant  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200, 'add',
                                                                            'failure', message)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'], self.id, 200,
                                                                                      'add', 'failure', message)


                    else:
                        line.date_replication = True
                        self.update_replication = True
                        _logger.info(
                            f"Successfully updated Product Variant {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(
                            f"Successfully updated Product Variant {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200, 'update',
                                                                            'success', f"Successfully updated Product Variant {self.name}")
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'], self.id, 200,
                                                                                      'update', 'success', f"Successfully updated Product Variant {self.name}")

                except requests.exceptions.RequestException as e:
                    _logger.error(
                        f"'{self.name}' Failed to update Product Variant'{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f"'{self.name}' Failed to update Product Variant'{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    line.date_replication = False
                    self.update_replication = False
                    if line.master_store_id.nhcl_sink == False:
                        line.master_store_id.create_cmr_replication_log('product.product',
                                                                        self.id, 500, 'update', 'failure',
                                                                        e)
                    else:
                        line.master_store_id.create_cmr_old_store_replication_log('product.product',
                                                                                  self.id, 500, 'update', 'failure',
                                                                                    e)

    def send_replication_data_to_store(self, store):
        """Send product replication data to a store (single record API)."""
        for line in store:
            if line.date_replication:
                continue

            ho_ip = line.nhcl_terminal_ip
            ho_port = line.nhcl_port_no
            ho_api_key = line.nhcl_api_key

            headers_source = {
                'api-key': ho_api_key,
                'Content-Type': 'application/json'
            }

            try:
                product_attribute_search_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"

                if self.default_code:
                    product_display_name = len(self.default_code)
                    varient_domain = [
                        ('nhcl_display_name', '=', self.display_name[product_display_name + 3:])
                    ]
                else:
                    varient_domain = [('nhcl_display_name', '=', self.display_name)]

                domain_str = json.dumps(varient_domain)
                encoded_domain = quote(domain_str)
                varient_url_data = f"{product_attribute_search_url}?domain={encoded_domain}"

                product_varient_get_data = requests.get(varient_url_data, headers=headers_source).json()
                varient_id_data = product_varient_get_data.get("data", [])

                if not varient_id_data:
                    msg = f"No matching product variants found {self.product_tmpl_id.name}. Skipping."
                    _logger.warning(msg)
                    logging.warning(msg)
                    if not line.master_store_id.nhcl_sink:
                        line.master_store_id.create_cmr_replication_log(
                            product_varient_get_data.get('object_name', 'product.product'),
                            self.id, 500, 'add', 'failure', msg
                        )
                    else:
                        line.master_store_id.create_cmr_old_store_replication_log(
                            product_varient_get_data.get('object_name', 'product.product'),
                            self.id, 500, 'add', 'failure', msg
                        )
                    continue

                varient_id = varient_id_data[0]['id']
                product_list = {
                    'default_code': self.default_code,
                    'barcode': self.barcode,
                    'nhcl_id': self.nhcl_id,
                }

                store_url_data = f"http://{ho_ip}:{ho_port}/api/product.product/{varient_id}"
                response = requests.put(store_url_data, headers=headers_source, json=product_list)
                response.raise_for_status()
                response_json = response.json()

                message = response_json.get("message", "No message provided")
                if not response_json.get("success", False):
                    msg = f"Failed to update Product Variant {self.name}: {message}"
                    _logger.error(msg)
                    logging.error(msg)
                    if not line.master_store_id.nhcl_sink:
                        line.master_store_id.create_cmr_replication_log(
                            response_json.get('object_name', 'product.product'),
                            self.id, 200, 'add', 'failure', message
                        )
                    else:
                        line.master_store_id.create_cmr_old_store_replication_log(
                            response_json.get('object_name', 'product.product'),
                            self.id, 200, 'add', 'failure', message
                        )
                else:
                    line.date_replication = True
                    msg = f"Successfully updated Product Variant {self.name} {message}"
                    _logger.info(msg)
                    logging.info(msg)
                    if not line.master_store_id.nhcl_sink:
                        line.master_store_id.create_cmr_replication_log(
                            response_json.get('object_name', 'product.product'),
                            self.id, 200, 'update', 'success', msg
                        )
                    else:
                        line.master_store_id.create_cmr_old_store_replication_log(
                            response_json.get('object_name', 'product.product'),
                            self.id, 200, 'update', 'success', msg
                        )

            except requests.exceptions.RequestException as e:
                msg = f"{self.name} Failed to update Product Variant {ho_ip}:{ho_port}. Error: {e}"
                _logger.error(msg)
                logging.error(msg)
                line.date_replication = False
                self.update_replication = False
                if not line.master_store_id.nhcl_sink:
                    line.master_store_id.create_cmr_replication_log(
                        'product.product', self.id, 500, 'update', 'failure', str(e)
                    )
                else:
                    line.master_store_id.create_cmr_old_store_replication_log(
                        'product.product', self.id, 500, 'update', 'failure', str(e)
                    )



    # def send_variant_replication_to_store(self, stores):
    #     """
    #     Send product variants one by one to each store.
    #     Optimized to cache API lookups and handle errors gracefully.
    #     """
    #
    #     def _search_api(url, domain, headers, cache):
    #         key = (url, str(domain))
    #         if key in cache:
    #             return cache[key]
    #         full_url = f"{url}?domain={quote(json.dumps(domain))}"
    #         try:
    #             resp = requests.get(full_url, headers=headers, timeout=15)
    #             resp.raise_for_status()
    #             data = resp.json().get("data", [])
    #             cache[key] = data
    #             return data
    #         except Exception as e:
    #             _logger.error(f"API search error {url}: {e}")
    #             return []
    #
    #     for store_line in stores:
    #         if store_line.date_replication:
    #             continue
    #
    #         ho_ip = store_line.nhcl_terminal_ip
    #         ho_port = store_line.nhcl_port_no
    #         ho_api_key = store_line.nhcl_api_key
    #
    #         headers = {"api-key": ho_api_key, "Content-Type": "application/json"}
    #
    #         cache = {}  # For caching API search results
    #
    #         for variant in self:
    #             # Check if this variant already replicated for this store
    #             replicated = variant.product_replication_id.filtered(
    #                 lambda r: r.id == store_line.id and r.date_replication)
    #             if replicated:
    #                 continue
    #
    #             # Check if variant exists on remote by nhcl_id to avoid duplicates
    #             search_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"
    #             domain = [('nhcl_id', '=', variant.nhcl_id)]
    #             existing = _search_api(search_url, domain, headers, cache)
    #
    #             if existing:
    #                 _logger.info(f"Variant {variant.display_name} already exists on {ho_ip}, marking as replicated.")
    #                 # Mark replicated locally
    #                 variant.product_replication_id.filtered(lambda r: r.id == store_line.id).date_replication = True
    #                 continue
    #
    #             # Prepare payload (example - customize as needed)
    #             category_id = None
    #             if variant.product_tmpl_id.categ_id and variant.product_tmpl_id.categ_id.nhcl_id:
    #                 cat_url = f"http://{ho_ip}:{ho_port}/api/product.category/search"
    #                 cat_data = _search_api(cat_url, [('nhcl_id', '=', variant.product_tmpl_id.categ_id.nhcl_id)],
    #                                        headers, cache)
    #                 if cat_data:
    #                     category_id = cat_data[0]['id']
    #
    #             payload = {
    #                 "default_code": variant.default_code,
    #                 "barcode": variant.barcode,
    #                 "nhcl_id": variant.nhcl_id,
    #                 "product_tmpl_id": variant.product_tmpl_id.id,
    #                 "categ_id": category_id,
    #                 # Add other fields as required...
    #             }
    #
    #             # Send create request (or update if you want)
    #             try:
    #                 create_url = f"http://{ho_ip}:{ho_port}/api/product.product/create"
    #                 resp = requests.post(create_url, headers=headers, json=payload, timeout=30)
    #                 resp.raise_for_status()
    #                 res_json = resp.json()
    #
    #                 if not res_json.get("success"):
    #                     _logger.error(f"Failed to create variant {variant.display_name}: {res_json}")
    #                     variant.update_replication = False
    #                     variant.product_replication_id.filtered(
    #                         lambda r: r.id == store_line.id).date_replication = False
    #                     continue
    #
    #                 # Mark replicated
    #                 variant.product_replication_id.filtered(lambda r: r.id == store_line.id).date_replication = True
    #                 _logger.info(f"Successfully replicated variant {variant.display_name} to {ho_ip}")
    #
    #             except Exception as e:
    #                 _logger.error(f"Error replicating variant {variant.display_name} to {ho_ip}: {e}")
    #                 variant.update_replication = False
    #                 variant.product_replication_id.filtered(lambda r: r.id == store_line.id).date_replication = False
    #
    #         self.env.cr.commit()


class ProductProductReplication(models.Model):
    _name = 'product.product.replication'

    product_product_replication_id = fields.Many2one('product.product', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')

