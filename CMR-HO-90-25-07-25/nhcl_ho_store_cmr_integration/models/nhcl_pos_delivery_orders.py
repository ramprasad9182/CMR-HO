from odoo import models,fields,api,_
import requests
from datetime import datetime
import pytz
import logging
import random
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)



class StockPicking(models.Model):
    _inherit = "stock.picking"

    def get_damage_delivery_orders(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                # Fetching Damage delivery orders
                store_damage_delivery_orders_search = f"http://{store_ip}:{store_port}/api/stock.picking/search"
                store_damage_delivery_orders_domain = [('nhcl_operation_type', '=', "damage"), ('nhcl_replication_status','=',False), ('state','=','done')]
                store_damage_delivery_orders_url = f"{store_damage_delivery_orders_search}?domain={store_damage_delivery_orders_domain}"

                store_damage_delivery_orders_data = requests.get(store_damage_delivery_orders_url, headers=headers_source).json()
                store_damage_delivery_orders = store_damage_delivery_orders_data.get("data")
                if store_damage_delivery_orders:
                    for order in store_damage_delivery_orders:
                        if order.get("nhcl_operation_type") == "damage":
                            store_picking_id = order.get("id")
                            company = order.get("company_id")[0]["name"]
                            res_company_ids = self.env['res.company'].search([('name', '=', company)])

                            company_id = res_company_ids.id if res_company_ids else False
                            store_stock_picking_type = self.env['stock.picking.type'].search([('stock_picking_type', '=', "damage"),('company_id.name', '=', company)])
                            location = order.get("location_id")[0]["id"]
                            store_location_url = f"http://{store_ip}:{store_port}/api/stock.location/{location}"
                            store_location_data = requests.get(store_location_url,
                                                               headers=headers_source).json()
                            store_location_data1 = store_location_data.get("data")
                            location_data2 = store_location_data1[0]["complete_name"]
                            location_id = self.env['stock.location'].sudo().search(
                                [('complete_name', '=', location_data2), ("active", "!=", False),
                                 ('usage', '=', 'internal'),('company_id.name', '=', company)])
                            location_dest = order.get("location_dest_id")[0]["id"]
                            store_location_dest_url = f"http://{store_ip}:{store_port}/api/stock.location/{location_dest}"
                            store_location_dest_data = requests.get(store_location_dest_url,
                                                                    headers=headers_source).json()
                            store_location_dest_data1 = store_location_dest_data.get("data")
                            location_dest_data2 = store_location_dest_data1[0]["complete_name"]
                            location_dest_id = self.env['stock.location'].sudo().search(
                                [('complete_name', '=', location_dest_data2), ("active", "!=", False)])

                            stock_picking_data = {
                                'picking_type_id': store_stock_picking_type.id,
                                'origin': order.get("name"),
                                'location_id': location_id.id,
                                'location_dest_id': location_dest_id.id,
                                'company_id': company_id,
                                'move_type': 'direct',
                                'state': 'done',
                            }
                            stock_picking = self.env['stock.picking'].create(stock_picking_data)

                            # Creating stock move lines
                            for line in order.get("move_line_ids_without_package"):
                                store_account_move_line = f"http://{store_ip}:{store_port}/api/stock.move.line/search"
                                store_account_move_line_domain = [('id', '=', line['id'])]
                                store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                                store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                            headers=headers_source).json()
                                store_account_move_line_data1 = store_account_move_line_data.get("data")
                                product = store_account_move_line_data1[0]["product_id"][0]["id"]
                                store_product_url = f"http://{store_ip}:{store_port}/api/product.product/{product}"
                                store_product_data = requests.get(store_product_url,
                                                                  headers=headers_source).json()
                                store_product_data1 = store_product_data.get("data")
                                ho_product = self.env['product.product'].search(
                                    [('barcode', '=', store_product_data1[0]["barcode"])])
                                if store_account_move_line_data1 and store_account_move_line_data1[0].get("lot_id"):
                                    lot_id = store_account_move_line_data1[0]["lot_id"]
                                    lot_name = lot_id[0]["name"] if lot_id else False
                                else:
                                    lot_name = None

                                location = store_account_move_line_data1[0]["location_id"][0]["id"]
                                store_location_url = f"http://{store_ip}:{store_port}/api/stock.location/{location}"
                                store_location_data = requests.get(store_location_url,
                                                                   headers=headers_source).json()
                                store_location_data1 = store_location_data.get("data")
                                location_data2 = store_location_data1[0]["location_id"][0]["name"]
                                location_data3 = self.env['stock.location'].sudo().search(
                                    [('location_id.name', '=', location_data2), ("active", "!=", False),
                                     ('usage', '=', 'internal'),('company_id.name', '=', company)])
                                if store_account_move_line_data1:
                                    move_line_vals = {
                                        "picking_id": stock_picking.id,
                                        "product_id": ho_product.id,
                                        "product_uom_id": store_account_move_line_data1[0]["product_uom_id"][0]["id"],
                                        "quantity": store_account_move_line_data1[0]["quantity"],
                                        "location_id": location_id.id,
                                        "location_dest_id": location_dest_id.id,
                                        "lot_name": lot_name,
                                    }
                                stock_move_line = self.env['stock.move.line'].create(move_line_vals)
                            stock_picking.button_validate()
                            picking_list = {
                                'nhcl_replication_status': True,

                            }
                            store_pos_delivery_update = f"http://{store_ip}:{store_port}/api/stock.picking/{store_picking_id}"
                            response = requests.put(store_pos_delivery_update, headers=headers_source,
                                                    json=picking_list)
                            response.raise_for_status()
                            response_json = response.json()

                            message = response_json.get("message", "No message provided")
                            response_code = response_json.get("responseCode", "No response code provided")
                            if response_json.get("success") == False:
                                _logger.info(
                                    f"Failed to create Delivery Order {message} '{store_ip}' with partner '{store_port}'. Error: ")
                                logging.error(
                                    f"Failed to create Delivery Order {message} '{store_ip}' with partner '{store_port}'. Error:")
                                store.create_cmr_store_server_replication_log('success', message)
                                store.create_cmr_store_replication_log(response_json['object_name'], stock_picking.id,
                                                                       200,
                                                                       'add', 'failure', message)


                            else:
                                _logger.info(
                                    f"Successfully created Delivery Order {stock_picking.name} {message} '{store_ip}' with partner '{store_port}'.")
                                logging.info(
                                    f"Successfully created Delivery Order {stock_picking.name} {message} '{store_ip}' with partner '{store_port}'.")
                                store.create_cmr_store_server_replication_log('success', message)
                                store.create_cmr_store_replication_log(response_json['object_name'], stock_picking.id,
                                                                       200,
                                                                       'add', 'success', f"Successfully created Delivery Order {stock_picking.name}")
            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)


    def store_damage_order(self):
        self.env['nhcl.initiated.status.log'].create(
            {'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.initiated.status.log"),
             'nhcl_date_of_log': datetime.now(), 'nhcl_job_name': 'Main-Damage Transaction-Job',
             'nhcl_status': 'success',
             'nhcl_details_status': 'Function Triggered'})
        self.get_damage_delivery_orders()
        self.env['nhcl.initiated.status.log'].create(
            {'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.initiated.status.log"),
             'nhcl_date_of_log': datetime.now(), 'nhcl_job_name': 'Main-Damage Transaction-Job',
             'nhcl_status': 'success',
             'nhcl_details_status': 'Function Completed'})
