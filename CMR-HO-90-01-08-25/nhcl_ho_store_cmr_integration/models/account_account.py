import requests
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class AccountAccount(models.Model):
    _inherit = "account.account"

    chart_of_account_id = fields.One2many('account.account.replication', 'account_replication_id')
    update_replication = fields.Boolean(string="Creation Status")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")

    @api.model
    def get_pending_account(self):
        pending_account = self.env['account.account'].search_count([('update_replication', '=', False)])
        return {
            'pending_account': pending_account,
        }

    def get_account_stores(self):
        return {
            'name': _('Chart of Account'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.account',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_account_view').id,
            'context': {'create': False, 'delete': False, 'duplicate': False, 'default_nhcl_selected_ids': self.ids},
        }

    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM account_account")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(AccountAccount, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def get_stores_data(self):
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
        existing_store_ids = self.chart_of_account_id.mapped('store_id.id')
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
        self.update({'chart_of_account_id': replication_data})

    def send_chart_of_account_replication_data(self):
        tax_list = {
            'name': self.name if self.name else None,
            'code': self.code if self.code else None,
            'account_type': self.account_type if self.account_type else None,
            'currency_id': self.currency_id.id if self.currency_id.id else False,
            'reconcile': self.reconcile if self.reconcile else None,
            'deprecated': self.deprecated if self.deprecated else None,
            'tax_ids': [tax.id for tax in self.tax_ids] if self.tax_ids else False,
            'tag_ids': [tag.id for tag in self.tag_ids] if self.tag_ids else False,
            'allowed_journal_ids': [journal.id for journal in
                                    self.allowed_journal_ids] if self.allowed_journal_ids else False,
            'nhcl_id': self.nhcl_id
        }
        for line in self.chart_of_account_id:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                store_url_exist_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                chart_acc_domain = [('code', '=', self.code), ('nhcl_id', '=', self.nhcl_id)]
                store_url = f"{store_url_exist_data}?domain={chart_acc_domain}"
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()  # Raises an HTTPError for bad responses

                    # Parse the JSON response
                    data = response.json()  # Now `data` is a dictionary
                    chart_acc_id_data = data.get("data", [])
                    # Check if Chart of Account already exists
                    if chart_acc_id_data:
                        _logger.info(
                            f" '{self.name}' Already exists as Chart of Account on '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'.")
                        logging.info(
                            f" '{self.name}' Already exists as Chart of Account on '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'.")
                        line.date_replication = True
                        self.update_replication = True
                        continue
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/create"
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[tax_list])
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
                                f"Successfully created Chart of Account {self.name} {message} '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'.")
                            logging.info(
                                f"Successfully created Chart of Account {self.name} {message} '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id,
                                                                                200,
                                                                                'add', 'success',
                                                                                f"Successfully created Chart of Account {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add',
                                                                                          'success',
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
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('account.account',
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Chart of Account on '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Chart of Account on '{ho_ip}' with partner '{ho_port}' with '{ho_api_key}'. Error: {e}")

    def update_chart_of_account_replication_data(self):
        for line in self.chart_of_account_id:
            ho_ip = line.nhcl_terminal_ip
            ho_port = line.nhcl_port_no
            ho_api_key = line.nhcl_api_key
            store_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
            chart_account_domain = self.nhcl_id
            chart_acc_domain = [('nhcl_id', '=', chart_account_domain)]
            store_url = f"{store_url_data}?domain={chart_acc_domain}"
            headers_source = {
                'api-key': ho_api_key,
                'Content-Type': 'application/json'
            }
            try:
                response = requests.get(store_url, headers=headers_source)
                response.raise_for_status()  # Raises an HTTPError for bad responses
                # Parse the JSON response
                data = response.json()  # Now `data` is a dictionary
                chart_acc_id_data = data.get("data", [])
                if not chart_acc_id_data:
                    continue

                chart_id = chart_acc_id_data[0]['id']
                tax_list = {
                    'name': self.name if self.name else None,
                    'code': self.code if self.code else None,
                    'account_type': self.account_type if self.account_type else None,
                    'currency_id': self.currency_id.id if self.currency_id.id else None,
                    'reconcile': self.reconcile if self.reconcile else None,
                    'deprecated': self.deprecated if self.deprecated else None,
                }
                store_url_data1 = f"http://{ho_ip}:{ho_port}/api/account.account/{chart_id}"

                # Update the product category
                update_response = requests.put(store_url_data1, headers=headers_source, json=tax_list)
                update_response.raise_for_status()

                # Update the status after successful request
                line.update_status = True
                self.update_status = True
                _logger.info(f"'{self.name}' Successfully updated Chart Of Account '{ho_ip}' with partner '{ho_port}'.")
                logging.info(f"'{self.name}' Successfully updated Chart Of Account '{ho_ip}' with partner '{ho_port}'.")
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log("account.account", self.id, 200,
                                                                    'update', 'success',
                                                                    f"Successfully updated Chart Of Account '{self.name}'")
                else:
                    line.master_store_id.create_cmr_old_store_replication_log("account.account",
                                                                              self.id, 200, 'update', 'success',
                                                                              f"Successfully updated Chart Of Account '{self.name}'")
            except requests.exceptions.RequestException as e:
                _logger.error(
                    f"'{self.name}' Failed to update Chart Of Account '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                logging.error(
                    f"'{self.name}' Failed to update Chart Of Account '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                line.update_status = False
                self.update_status = False
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log("account.account", self.id, 500,
                                                                    'update', 'failure',
                                                                    e)
                else:
                    line.master_store_id.create_cmr_old_store_replication_log("account.account",
                                                                              self.id, 500, 'update', 'failure',
                                                                              e)


class AccountAccountReplication(models.Model):
    _name = 'account.account.replication'

    account_replication_id = fields.Many2one('account.account', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')
