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
        return super(ProductProduct, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def button_fetch_replication_data(self):
        for line in self:
            replication_data = []
            existing_store_ids = line.product_replication_list_id.mapped('store_id.id')
            ho_store_id = self.env['nhcl.ho.store.master'].search(
                [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
            for rec in line.product_replication_list_id:
                if rec.nhcl_terminal_ip not in ho_store_id.mapped('nhcl_terminal_ip'):
                    rec.unlink()
                elif rec.nhcl_api_key not in ho_store_id.mapped('nhcl_api_key'):
                    rec.unlink()
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
                        varient_domain = [('nhcl_display_name', '=', self.display_name[product_display_name + 3:])]
                    else:
                        varient_domain = [
                            ('nhcl_display_name', '=', self.display_name)]
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

    def send_replication_data_to_store(self,store):
        for line in store:
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

                    if self.default_code:
                        product_display_name = len(self.default_code)
                        varient_domain = [('nhcl_display_name', '=', self.display_name[product_display_name + 3:])]
                    else:
                        varient_domain = [
                            ('nhcl_display_name', '=', self.display_name)]
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
        self.env.cr.commit()

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

