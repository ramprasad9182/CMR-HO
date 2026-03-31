import requests
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    account_tax_id = fields.One2many('tax.replication', 'tax_replication_id')
    update_replication = fields.Boolean(string="Creation Status")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")

    @api.model
    def get_pending_tax(self):
        pending_tax = self.search_count([('update_replication', '=', False)])
        return {
            'pending_tax': pending_tax,
        }

    def get_tax_stores(self):
        return {
            'name': _('Taxes'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.tax',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_tax_view').id,
            'context': {'create': False, 'delete': False, 'duplicate': False,'default_nhcl_selected_ids': self.ids},
        }

    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM account_tax")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(AccountTax, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        for rec in self:
            rec.warning_message = ''
            if rec.update_replication == False:
                rec.warning_message = 'Oops! Integration has not been completed.'
            else:
                rec.warning_message = 'Integration is Complete!'

    def get_stores_data(self):
        replication_data = []
        existing_store_ids = self.account_tax_id.mapped('store_id.id')
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Tax' and j.nhcl_line_data == True:
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
        self.update({'account_tax_id': replication_data})

    def send_tax_replication_data(self):
        children_tax = []
        for data in self.children_tax_ids:
            children_tax.append((0, 0, {
                'name': data.name,
                'amount_type': data.amount_type,
                'amount': data.amount,
            }))
        tax_list = {
            'name': self.name if self.name else None,
            'description': self.description if self.description else None,
            'tax_scope': self.tax_scope if self.tax_scope else None,
            'amount_type': self.amount_type if self.amount_type else None,
            'type_tax_use': self.type_tax_use if self.type_tax_use else None,
            'python_compute': self.python_compute if self.python_compute else None,
            'tax_group_id': self.tax_group_id.id if self.tax_group_id.id else False,
            'price_include': self.price_include if self.price_include else None,
            'invoice_label': self.invoice_label if self.invoice_label else None,
            'analytic': self.analytic if self.analytic else None,
            'min_amount': self.min_amount if self.min_amount else None,
            'max_amount': self.max_amount if self.max_amount else None,
            'include_base_amount': self.include_base_amount if self.include_base_amount else None,
            'is_base_affected': self.is_base_affected if self.is_base_affected else None,
            'l10n_in_reverse_charge': self.l10n_in_reverse_charge if self.l10n_in_reverse_charge else None,
            'country_id': self.country_id.id if self.country_id else False,
            'nhcl_id' : self.nhcl_id,
            'children_tax_ids' : children_tax,
        }

        for line in self.account_tax_id:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                store_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                tax_domain = [('nhcl_id', '=', self.nhcl_id), ('type_tax_use', '=', self.type_tax_use)]
                store_url = f"{store_url_data}?domain={tax_domain}"
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()  # Raise an exception for bad responses
                    data = response.json()
                    tax_acc_data = data.get("data", [])

                    # Check if tax already exists
                    if tax_acc_data:
                        _logger.info(f" '{self.name}' Already exists as Tax on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(f" '{self.name}' Already exists as Tax on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        self.update_replication = True
                        continue

                    # Tax does not exist, so create it
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/create"
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
                                f"Failed to create Tax {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Tax  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
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
                                f"Successfully created Tax {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully created Tax {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id,
                                                                                200,
                                                                                'add', 'success', f"Successfully created Tax {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add',
                                                                                          'success',
                                                                                          f"Successfully created Tax {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(
                            f" '{self.name}' Failed to create Tax on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                            f" '{self.name}' Failed to create Tax on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('account.tax',
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('account.tax',
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)

                except requests.exceptions.RequestException as e:
                    _logger.info(f" '{self.name}' Error checking Tax on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(f" '{self.name}' Error checking Tax on '{ho_ip}' with partner '{ho_port}'. Error: {e}")

    def update_account_tax_replication_data(self):
        for line in self.account_tax_id:
            ho_ip = line.nhcl_terminal_ip
            ho_port = line.nhcl_port_no
            ho_api_key = line.nhcl_api_key
            store_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
            account_tax_domain = self.nhcl_id
            tax_acc_domain = [('nhcl_id', '=', account_tax_domain)]
            store_url = f"{store_url_data}?domain={tax_acc_domain}"
            headers_source = {
                'api-key': ho_api_key,
                'Content-Type': 'application/json'
            }
            try:
                response = requests.get(store_url, headers=headers_source)
                response.raise_for_status()  # Raises an HTTPError for bad responses

                # Parse the JSON response
                data = response.json()  # Now `data` is a dictionary
                tax_acc_id_data = data.get("data", [])

                if not tax_acc_id_data:
                    continue

                tax_id = tax_acc_id_data[0]['id']
                tax_list = {
                    'name': self.name if self.name else None,
                    'amount_type': self.amount_type if self.amount_type else None,
                    'type_tax_use': self.type_tax_use if self.type_tax_use else None,
                    'python_compute': self.python_compute if self.python_compute else None,
                    'tax_group_id': self.tax_group_id.id if self.tax_group_id.id else False,
                    'price_include': self.price_include if self.price_include else None,
                    'min_amount': self.min_amount if self.min_amount else None,
                    'max_amount': self.max_amount if self.max_amount else None,
                    'tax_scope': self.tax_scope if self.tax_scope else None,
                }
                store_url_data1 = f"http://{ho_ip}:{ho_port}/api/account.tax/{tax_id}"

                # Update the product category
                update_response = requests.put(store_url_data1, headers=headers_source, json=tax_list)
                update_response.raise_for_status()

                # Update the status after successful request
                line.update_status = True
                self.update_status = True
                _logger.info(f"'{self.name}' Successfully updated Account Tax'{ho_ip}' with partner '{ho_port}'.")
                logging.info(f"'{self.name}' Successfully updated Account Tax '{ho_ip}' with partner '{ho_port}'.")
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log("account.tax", self.id,
                                                                    200,
                                                                    'update', 'success',
                                                                    f"Successfully updated Tax {self.name}")
                else:
                    line.master_store_id.create_cmr_old_store_replication_log("account.tax",
                                                                              self.id, 200, 'update',
                                                                              'success',
                                                                              f"Successfully updated Tax {self.name}")

            except requests.exceptions.RequestException as e:
                _logger.error(
                    f"'{self.name}' Failed to update Account Tax'{ho_ip}' with partner '{ho_port}'. Error: {e}")
                logging.error(
                    f"'{self.name}' Failed to update Account Tax'{ho_ip}' with partner '{ho_port}'. Error: {e}")
                line.update_status = False
                self.update_status = False
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log("account.tax", self.id,
                                                                    500,
                                                                    'update', 'failure',
                                                                    e)
                else:
                    line.master_store_id.create_cmr_old_store_replication_log("account.tax",
                                                                              self.id, 500, 'update',
                                                                              'failure',
                                                                              e)



class TaxReplication(models.Model):
    _name = 'tax.replication'

    tax_replication_id = fields.Many2one('account.tax', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')

