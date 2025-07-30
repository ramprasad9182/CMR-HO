import requests
from odoo import api, models, api, _, fields
import logging
_logger = logging.getLogger(__name__)


class Users(models.Model):
    _inherit = 'res.users'

    update_replication = fields.Boolean(string="Flag", copy=False)
    user_replication_id = fields.One2many('res.users.replication', 're_user_replication_line_id', copy=False)
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")

    @api.model
    def get_pending_users(self):
        pending_users = self.search_count([('update_replication', '=', False)])
        return {
            'pending_users': pending_users,
        }
    def get_user_stores(self):
        return {
            'name': _('Users'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.user',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_user_view').id,
            'context': {'create': False, 'delete': False, 'duplicate': False,'default_nhcl_selected_ids': self.ids},
        }


    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM res_users")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(Users, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'


    def get_stores_data(self):
        # self.user_replication_id.unlink()
        replication_data = []
        existing_store_ids = self.user_replication_id.mapped('store_id.id')
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True),('nhcl_store_name.company_id.name', '=', self.company_id.name)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'User' and j.nhcl_line_data == True:
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
        self.update({'user_replication_id': replication_data})

    def send_replication_data(self):
        user_list = {
            'name': self.name,
            'login': self.login,
            'nhcl_id':self.nhcl_id,
            'groups_id': [group.id for group in self.groups_id] if self.groups_id else False,
        }
        for line in self.user_replication_id:
            if line.date_replication == False:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                search_store_url_data = f"http://{ho_ip}:{ho_port}/api/res.users/search"
                user_domain = [('name', '=', self.name), ('login', '=', self.login)]
                store_url = f"{search_store_url_data}?domain={user_domain}"
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()  # Raise an exception for bad responses
                    data = response.json()
                    user_data = data.get("data", [])

                    # Check if User already exists
                    if user_data:
                        _logger.info(
                            f" '{self.name}' Already exists as User on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(
                            f" '{self.name}' Already exists as User on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        self.update_replication = True
                        continue
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/res.users/create"
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[user_list])
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
                                f"Failed to create User {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create User  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
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
                                f"Successfully created User {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully created User {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log('res.users',
                                                                                self.id, 200, 'add', 'success',
                                                                                f"Successfully created User {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log('res.users',
                                                                                          self.id, 200, 'add',
                                                                                          'success',
                                                                                          f"Successfully created User {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(
                            f" '{self.name}'Failed to create User '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                            f" '{self.name}' Failed to create User '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('res.users',
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('res.users',
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking User on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking User on '{ho_ip}' with partner '{ho_port}'. Error: {e}")

    def update_user_replication_data(self):
        for line in self.user_replication_id:
            ho_ip = line.nhcl_terminal_ip
            ho_port = line.nhcl_port_no
            ho_api_key = line.nhcl_api_key
            store_url_data = f"http://{ho_ip}:{ho_port}/api/res.users/search"
            users_domain = self.nhcl_id
            res_user_domain = [('nhcl_id', '=', users_domain)]
            store_url = f"{store_url_data}?domain={res_user_domain}"
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            try:
                response = requests.get(store_url, headers=headers_source)
                response.raise_for_status()  # Raises an HTTPError for bad responses

                # Parse the JSON response
                data = response.json()  # Now `data` is a dictionary
                users_id_data = data.get("data", [])
                # print(users_id_data)
                if not users_id_data:
                    continue

                user_id = users_id_data[0]['id']
                groups_id = [value.id for value in self.groups_id]
                partner_list = {
                    'name': self.name,
                    'login': self.login,
                }
                store_url_data1 = f"http://{ho_ip}:{ho_port}/api/res.users/{user_id}"

                # Update the product category
                update_response = requests.put(store_url_data1, headers=headers_source, json=partner_list)
                update_response.raise_for_status()

                # Update the status after successful request
                line.update_status = True
                self.update_status = True
                _logger.info(
                    f"'{self.name}' Successfully updated User '{ho_ip}' with partner '{ho_port}'.")
                logging.info(
                    f"'{self.name}' Successfully updated User'{ho_ip}' with partner '{ho_port}'.")
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log('res.users',
                                                                    self.id, 200, 'update', 'success',
                                                                    f"'{self.name}' Successfully updated User")
                else:
                    line.master_store_id.create_cmr_old_store_replication_log('res.users',
                                                                              self.id, 200, 'update', 'success',
                                                                              f"'{self.name}' Successfully updated User")
            except requests.exceptions.RequestException as e:
                _logger.error(
                    f"'{self.name}' Failed to update User '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                logging.error(
                    f"'{self.name}' Failed to update User '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                line.update_status = False
                self.update_status = False
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log('res.users',
                                                                    self.id, 500, 'update', 'failure',
                                                                    e)
                else:
                    line.master_store_id.create_cmr_old_store_replication_log('res.users',
                                                                              self.id, 500, 'update', 'failure',
                                                                              e)


class UsersReplication(models.Model):
    _name = 'res.users.replication'

    re_user_replication_line_id = fields.Many2one('res.users', string="Replication", copy=False)
    store_id = fields.Many2one('stock.warehouse', string="Store", copy=False)
    status = fields.Boolean(string="Active Status", copy=False)
    date_replication = fields.Boolean(string="Store status", copy=False)
    nhcl_terminal_ip = fields.Char('Terminal IP', copy=False)
    nhcl_port_no = fields.Char('Port', copy=False)
    nhcl_api_key = fields.Char(string='API Secret key', copy=False)
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')
