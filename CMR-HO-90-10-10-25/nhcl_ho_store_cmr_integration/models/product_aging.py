import requests
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class ProductAging(models.Model):
    _inherit = 'product.aging'

    nhcl_product_aging_ids = fields.One2many('product.aging.replication', 'product_aging_id')
    update_replication = fields.Boolean(string="Creation Status")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")


    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM product_aging")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(ProductAging, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def get_stores_data(self):
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        existing_store_ids = self.nhcl_product_aging_ids.mapped('store_id.id')
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Account' and j.nhcl_line_data == True:
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
        self.update({'nhcl_product_aging_ids': replication_data})

    def send_product_aging_replication_data(self):
        k = []
        for line in self.product_aging_ids:
            k.append((0, 0, {
                'name': line.name,
                'nhcl_id': line.nhcl_id,
                'from_date': line.from_date.isoformat() if line.from_date else None,
                'to_date': line.to_date.isoformat() if line.to_date else None,
            }))
        aging_data = {
            'name': self.name,
            'nhcl_id': self.nhcl_id,
            'from_date': self.from_date.isoformat() if self.from_date else None,
            'to_date': self.to_date.isoformat() if self.to_date else None,
            'product_aging_ids': k,

        }
        for line in self.nhcl_product_aging_ids:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                store_url_exist_data = f"http://{ho_ip}:{ho_port}/api/product.aging/search"
                aging_domain = [('nhcl_id','=',self.nhcl_id)]
                store_url = f"{store_url_exist_data}?domain={aging_domain}"
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()  # Raises an HTTPError for bad responses

                    # Parse the JSON response
                    data = response.json()  # Now `data` is a dictionary
                    aging_id_data = data.get("data", [])
                    # Check if Chart of Account already exists
                    if aging_id_data:
                        line.date_replication = True
                        self.update_replication = True
                        continue
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/product.aging/create"
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=aging_data)
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
                                f"Failed to create Chart of Account {message} '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error: ")
                            logging.error(
                                f"Failed to create Chart of Account  {message} '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error:")
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
                                f"Successfully created Chart of Account {self.name} {message} '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'.")
                            logging.info(
                                f"Successfully created Chart of Account {self.name} {message} '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                'add', 'success',  f"Successfully created Chart of Account {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add', 'success',
                                                                                           f"Successfully created Chart of Account {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(
                            f" '{self.name}'Failed to create Chart of Account '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error: {e}")
                        logging.error(
                            f" '{self.name}' Failed to create Chart of Account '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error: {e}")
                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('account.account',
                                                                        self.id, 500,'add', 'failure',
                                                                        e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('account.account',
                                                                        self.id, 500,'add', 'failure',
                                                                        e)
                except requests.exceptions.RequestException as e:
                    _logger.info(f" '{self.name}' Error checking Chart of Account on '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error: {e}")
                    logging.error(f" '{self.name}' Error checking Chart of Account on '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error: {e}")

class ProductAgingLine(models.Model):
    _inherit = 'product.aging.line'

    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM product_aging_line")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(ProductAgingLine, self).create(vals)


class ProductAgingReplication(models.Model):
    _name = 'product.aging.replication'

    product_aging_id = fields.Many2one('product.aging', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')

