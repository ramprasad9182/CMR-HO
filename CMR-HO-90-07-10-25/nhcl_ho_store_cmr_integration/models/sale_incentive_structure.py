from odoo import models, fields, api, _
import requests
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class SetuSalesIncentiveStructure(models.Model):
    _inherit = 'setu.sales.incentive.structure'

    sale_incentive_replication_ids = fields.One2many('sale.incentive.structure.line', 'sale_incentive_replication_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')
    update_replication = fields.Boolean(string="Creation Status")
    update_status = fields.Boolean(string="Update status")
    delete_status = fields.Boolean(string="Delete status")

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM setu_sales_incentive_structure")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(SetuSalesIncentiveStructure, self).create(vals)

    def get_stores_data(self):
        replication_data = []
        existing_store_ids = self.sale_incentive_replication_ids.mapped('store_id.id')
        ho_store_id = self.env['nhcl.ho.store.master'].sudo().search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Sales Incentive Structure' and j.nhcl_line_data == True:
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
        self.update({'sale_incentive_replication_ids': replication_data})

    def send_sale_incentive_replication_data(self):
        for line in self.sale_incentive_replication_ids:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }

                search_store_url_incentive_data = f"http://{ho_ip}:{ho_port}/api/setu.sales.incentive.structure/search"
                setu_sale_domain = [('nhcl_id', '=', self.nhcl_id)]
                incentive_store_url = f"{search_store_url_incentive_data}?domain={setu_sale_domain}"
                try:
                    response = requests.get(incentive_store_url, headers=headers_source)
                    response.raise_for_status()  # Raise an exception for bad responses
                    data = response.json()
                    sale_incentive_data = data.get("data", [])
                    if sale_incentive_data:
                        _logger.info(f" '{self.name}' Already exists as Incentive on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(f" '{self.name}' Already exists as Incentive on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        self.update_replication = True
                        continue

                    sale_incentive_store_url_data = f"http://{ho_ip}:{ho_port}/api/setu.sales.incentive.structure/create"
                    sale_incentive_line = []
                    start_date = self.start_date
                    end_date = self.end_date
                    search_store_url_account_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                    account_domain = [('code', '=', self.incentive_account_id.code), ('nhcl_id', '=', self.incentive_account_id.nhcl_id)]
                    account_store_url = f"{search_store_url_account_data}?domain={account_domain}"
                    response = requests.get(account_store_url, headers=headers_source)
                    response.raise_for_status()  # Raise an exception for bad responses
                    data = response.json()
                    account_data = data.get("data", [])
                    account_id = False
                    if account_data:
                        account_id = account_data[0]["id"]
                    for line_data in self.incentive_structure_line_ids:
                        search_store_url_aging_data = f"http://{ho_ip}:{ho_port}/api/product.aging.line/search"
                        aging_domain = [('name', '=', line_data.aging_id.name)]
                        aging_store_url = f"{search_store_url_aging_data}?domain={aging_domain}"

                        response = requests.get(aging_store_url, headers=headers_source)
                        response.raise_for_status()
                        aging_response = response.json()
                        aging_data = aging_response.get("data", [])
                        aging_id = aging_data[0] if aging_data else {}

                        sale_incentive_line.append((0, 0, {
                            'role': line_data.role,
                            'calculate_based_on': line_data.calculate_based_on,
                            'target_based_on': line_data.target_based_on,
                            'calculation_method': line_data.calculation_method,
                            'incentive_value': line_data.incentive_value,
                            'target_value_min': line_data.target_value_min,
                            'target_value_max': line_data.target_value_max,
                            'day_ageing_incentive': line_data.day_ageing_incentive,
                            'aging_type': line_data.aging_type,
                            'aging_id': aging_id.get('id'),
                            'sales_team_ids': [
                                (6, 0, line_data.sales_team_ids.ids)] if line_data.sales_team_ids else [],
                        }))

                    incentive_list = {
                        'name': self.name,
                        'nhcl_id': self.nhcl_id,
                        'start_date': self.start_date.strftime('%Y-%m-%d') if self.start_date else None,
                        'end_date': self.end_date.strftime('%Y-%m-%d') if self.end_date else None,
                        'incentive_calculation_based_on': self.incentive_calculation_based_on,
                        'incentive_account_id': account_id,
                        'incentive_structure_line_ids': sale_incentive_line,
                        'incentive_state': 'confirmed',

                        }
                    try:
                        stores_data = requests.post(sale_incentive_store_url_data, headers=headers_source, json=incentive_list)
                        stores_data.raise_for_status()
                        stores_data.raise_for_status()

                        response_json = stores_data.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Incentive {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Incentive  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
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
                                f"Successfully create Incentive {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully create Incentive {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                'add', 'success', f"Successfully create Incentive {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add', 'success',
                                                                                          f"Successfully create Incentive {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(
                            f" '{self.name}'Failed to create Incentive '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                            f" '{self.name}' Failed to create Incentive '{ho_ip}' with partner '{ho_port}'. Error: {e}")
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
                    _logger.info(f" '{self.name}' Error checking Incentive on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Incentive on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class SaleIncentiveStructureLine(models.Model):
    _name = 'sale.incentive.structure.line'

    sale_incentive_replication_id = fields.Many2one('setu.sales.incentive.structure', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')