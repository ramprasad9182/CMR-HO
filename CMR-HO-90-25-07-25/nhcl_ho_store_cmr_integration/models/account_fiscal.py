import requests
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class AccountFiscalYear(models.Model):
    _inherit = "account.fiscal.year"

    account_fiscal_year_id = fields.One2many('account.fiscal.year.replication', 'account_fiscal_year_replication_id')
    update_replication = fields.Boolean(string="Creation status",compute='check_update_replication', store=True)
    nhcl_create_status = fields.Boolean(string="Create Status")

    @api.depends('name')
    def check_update_replication(self):
        for j in self:
            b = len(j.account_fiscal_year_id)
            a = self.env['account.fiscal.year.replication'].search_count([('account_fiscal_year_replication_id','=',j.id),('date_replication','=',True)])
            if a == b:
                j.update_replication = True
            else:
                j.update_replication = False

    @api.model
    def get_pending_fiscal(self):
        pending_fiscal = self.search_count([('update_replication', '=', False)])
        return {
            'pending_fiscal': pending_fiscal,
        }

    def get_fin_year_stores(self):
        return {
            'name': _('Fiscal Years'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.fin_year',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_fin_year_view').id,
            'context': {'create': False, 'delete': False, 'duplicate': False,'default_nhcl_selected_ids': self.ids},
        }

    def get_stores_data(self):
        replication_data = []
        existing_store_ids = self.account_fiscal_year_id.mapped('store_id.id')
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Fiscal Year' and j.nhcl_line_data == True:
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
        self.update({'account_fiscal_year_id': replication_data})

    def send_fiscal_year_replication_data(self):
        tax_list = {
            'name': self.name,
            'date_from': self.date_from.strftime('%Y-%m-%d') if self.date_from else None,
            'date_to': self.date_to.strftime('%Y-%m-%d') if self.date_to else None,
        }
        for line in self.account_fiscal_year_id:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                search_store_url_data = f"http://{ho_ip}:{ho_port}/api/account.fiscal.year/search"
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                date_from = self.date_from.strftime('%Y-%m-%d')
                date_to = self.date_to.strftime('%Y-%m-%d')
                acc_fisc_domain = [('name', '=', self.name),('date_from', '=', date_from),('date_to', '=', date_to)]
                store_url = f"{search_store_url_data}?domain={acc_fisc_domain}"
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()  # Raises an HTTPError for bad responses

                    # Parse the JSON response
                    data = response.json()  # Now `data` is a dictionary
                    account_fiscal_id_data = data.get("data", [])
                    # Check if Fiscal Year already exists
                    if account_fiscal_id_data:
                        _logger.info(
                            f" '{self.name}' Already exists as Account Fiscal Year on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(
                            f" '{self.name}' Already exists as Account Fiscal Year on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        self.update_replication = True
                        continue
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/account.fiscal.year/create"
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
                                f"Failed to create Fiscal Year {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Fiscal Year  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], 200,
                                                                                'add', 'failure', message)
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          200, 'add', 'failure',
                                                                                          message)
                        else:
                            line.date_replication = True
                            self.update_replication = True
                            _logger.info(
                                f"Successfully created Fiscal Year {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully created Fiscal Year {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], 200,
                                                                                'add', 'success', f"Successfully created Fiscal Year {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          200, 'add', 'success',
                                                                                          f"Successfully created Fiscal Year {self.name}")

                    except requests.exceptions.RequestException as e:
                        _logger.error(
                            f"'{self.name}' Failed to Create Fiscal Year '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                            f"'{self.name}' Failed to Create Fiscal Year '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('account.fiscal',
                                                                            500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('account.fiscal',
                                                                                      500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Account Fiscal Year on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Account Fiscal Year on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class AccountFiscalYearReplication(models.Model):
    _name = 'account.fiscal.year.replication'

    account_fiscal_year_replication_id = fields.Many2one('account.fiscal.year', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')

