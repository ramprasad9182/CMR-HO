import requests

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class PartnerCategory(models.Model):
    _inherit = 'res.partner.category'

    update_replication = fields.Boolean(string="Flag")
    partner_category_id = fields.One2many('res.partner.category.replication', 'partner_category_line_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")



    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM res_partner_category")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(PartnerCategory, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def get_stores_data(self):
        replication_data = []
        existing_store_ids = self.partner_category_id.mapped('store_id.id')
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Partner Tags' and j.nhcl_line_data == True:
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
        self.update({'partner_category_id': replication_data})

    def send_replication_data(self):
        partner_category_list = {
            'name': self.name,
            'color': self.color,
            'active': self.active,

        }

        for line in self.partner_category_id:
            if line.date_replication == False:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                search_store_url_data = f"http://{ho_ip}:{ho_port}/api/res.partner.category/search"
                partner_domain = [('nhcl_id', '=', self.nhcl_id)]
                store_url = f"{search_store_url_data}?domain={partner_domain}"
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()  # Raise an exception for bad responses
                    data = response.json()
                    contact_data = data.get("data", [])

                    # Check if Contact already exists
                    if contact_data:
                        _logger.info(f" '{self.name}' Already exists as Contact on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(f" '{self.name}' Already exists as Contact on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        continue
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/res.partner.category/create"
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[partner_category_list])
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
                                f"Failed to create Partner {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Partner  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
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
                                f"Successfully created Partner {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully created Partner {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id,
                                                                                200,
                                                                                'add', 'success', f"Successfully created Partner {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add',
                                                                                          'success',
                                                                                          f"Successfully created Partner {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(f"Failed to create Partner '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(f"Failed to create Partner '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        line.date_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('res.partner.category',
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('res.partner.category',
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Contact on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Contact on '{ho_ip}' with partner '{ho_port}'. Error: {e}")



class PartnerCategoryReplication(models.Model):
    _name = 'res.partner.category.replication'

    partner_category_line_id = fields.Many2one('res.partner.category', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')
