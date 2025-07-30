import requests
from odoo import api, models, api, _, fields
import logging

from odoo.exceptions import UserError

# Configure logging at the module level or application entry point
logger = logging.getLogger(__name__)


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    update_replication = fields.Boolean(string="Flag", copy=False)
    warehouse_replication_id = fields.One2many('stock.warehouse.replication', 'warehouse_replication_line_id', copy=False)

    @api.model
    def default_get(self, fields_list):
        res = super(StockWarehouse, self).default_get(fields_list)
        return res

    def button_fetch_replication_data(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '=', 'ho'),('nhcl_active', '=', True)])
        if not ho_store_id:
            raise UserError('No HO Store found.')

        ho_ip = ho_store_id.nhcl_terminal_ip
        ho_port = ho_store_id.nhcl_port_no
        ho_api_key = ho_store_id.nhcl_api_key
        store_url_data = f"http://{ho_ip}:{ho_port}/api/nhcl.ho.store.master/search"
        headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}

        try:
            stores_data = requests.get(store_url_data, headers=headers_source).json()
            store_data = stores_data.get("data", [])
            replication_data = []

            for i in store_data[1:]:
                store_name = i.get("nhcl_store_name")
                store_id = store_name[0]["id"] if store_name else None
                terminal_ip = i.get("nhcl_terminal_ip")
                port_no = i.get("nhcl_port_no")
                api_key = i.get("nhcl_api_key")
                active = i.get("nhcl_active")

                vals = {
                    'store_id': store_id,
                    'nhcl_terminal_ip': terminal_ip,
                    'nhcl_port_no': port_no,
                    'nhcl_api_key': api_key,
                    'status': active,
                }
                replication_data.append((0, 0, vals))

            self.update({'warehouse_replication_id': replication_data})
            return True

        except requests.exceptions.RequestException as e:
            raise UserError(f"Failed to fetch replication data. Error: {e}")

    def send_replication_data(self):
        for line in self.warehouse_replication_id:
            if not line.date_replication:  # More Pythonic way to check for False
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                store_url_data = f"http://{ho_ip}:{ho_port}/api/stock.warehouse/search"
                warehouse_name = self.name
                warehouse_domain = f"?domain=[('name','=',\"{warehouse_name}\")]"
                warehouse_url_data = store_url_data + warehouse_domain
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                warehouse_url = requests.get(warehouse_url_data, headers=headers_source).json()
                warehouse_data = warehouse_url.get("data", [])
                try:
                    if warehouse_data:
                        line.date_replication = True
                        self.update_replication = True

                except requests.exceptions.RequestException as e:
                    line.date_replication = False
                    self.update_replication = False


class WareHouseReplication(models.Model):
    _name = 'stock.warehouse.replication'

    warehouse_replication_line_id = fields.Many2one('stock.warehouse', string="Replication", copy=False)
    store_id = fields.Many2one('stock.warehouse', string="Store", copy=False)
    status = fields.Boolean(string="Active Status", copy=False)
    date_replication = fields.Boolean(string="Store status", copy=False)
    nhcl_terminal_ip = fields.Char('Terminal IP', copy=False)
    nhcl_port_no = fields.Char('Port', copy=False)
    nhcl_api_key = fields.Char(string='API Secret key', copy=False)


