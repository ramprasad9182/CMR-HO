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

    nhcl_tracking_number = fields.Char(string='Source Number')

    def get_store_delivery_orders(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                # Fetching delivery orders
                store_pos_delivery_orders_search = f"http://{store_ip}:{store_port}/api/stock.picking/search"
                store_pos_delivery_orders_domain = [('picking_type_id.name', '=', "Delivery Orders"),
                                                    ('nhcl_replication_status', '=', False)]
                store_pos_delivery_orders_url = f"{store_pos_delivery_orders_search}?domain={store_pos_delivery_orders_domain}"

                store_pos_delivery_orders_data = requests.get(store_pos_delivery_orders_url,
                                                              headers=headers_source).json()
                store_pos_delivery_orders = store_pos_delivery_orders_data.get("data")

                if store_pos_delivery_orders:
                    for order in store_pos_delivery_orders:
                        try:
                            if not order.get("move_line_ids_without_package"):
                                continue

                            store_picking_id = order.get("id")
                            company = order.get("company_id")[0]["name"]
                            res_company_ids = self.env['res.company'].search([('name', '=', company)])
                            company_id = res_company_ids.id if res_company_ids else False

                            # Create Sale Order
                            sale_order_data = {
                                'partner_id': 1,
                                'origin': order.get("name"),
                                'so_type': order.get("stock_type"),
                                'company_id': company_id,
                            }
                            sale_order = self.env['sale.order'].create(sale_order_data)

                            for line in order.get("move_line_ids_without_package"):
                                store_account_move_line = f"http://{store_ip}:{store_port}/api/stock.move.line/search"
                                store_account_move_line_domain = [('id', '=', line['id'])]
                                store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                                store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                            headers=headers_source).json()
                                store_account_move_line_data1 = store_account_move_line_data.get("data")

                                if store_account_move_line_data1:
                                    product = store_account_move_line_data1[0]["product_id"][0]["id"]
                                    store_product_url = f"http://{store_ip}:{store_port}/api/product.product/{product}"
                                    store_product_data = requests.get(store_product_url, headers=headers_source).json()
                                    store_product_data1 = store_product_data.get("data")

                                    ho_product = self.env['product.product'].search(
                                        [('barcode', '=', store_product_data1[0]["barcode"])])

                                    # Handle lot IDs
                                    if store_account_move_line_data1 and store_account_move_line_data1[0].get("lot_id"):
                                        lot_ids = store_account_move_line_data1[0]["lot_id"]
                                        lot_name = lot_ids[0]["name"] if lot_ids else False
                                        ho_lot_id = self.env['stock.lot'].sudo().search(
                                            [('name', '=', lot_name), ('company_id.name', '=', company)])
                                        lot_id = ho_lot_id.id if ho_lot_id else False
                                    else:
                                        lot_id = False

                                    if ho_product:
                                        order_lines = {
                                            'order_id': sale_order.id,
                                            'product_id': ho_product.id,
                                            'product_uom_qty': store_account_move_line_data1[0]["quantity"],
                                            'price_unit': ho_lot_id.cost_price,
                                        }

                                        # Add lot_ids only if a valid lot_id exists
                                        if lot_id:
                                            order_lines['lot_ids'] = [(4, lot_id)]

                                        self.env['sale.order.line'].create(order_lines)
                                    else:
                                        _logger.warning(f"Product not found for ID {product}")
                                else:
                                    _logger.warning(f"No move line data found for line {line['id']}")

                            sale_order.action_confirm()

                            # Update delivery order in store
                            picking_list = {'nhcl_replication_status': True}
                            store_pos_delivery_update = f"http://{store_ip}:{store_port}/api/stock.picking/{store_picking_id}"
                            response = requests.put(store_pos_delivery_update, headers=headers_source,
                                                    json=picking_list)
                            response.raise_for_status()
                            response_json = response.json()

                            message = response_json.get("message", "No message provided")
                            if not response_json.get("success"):
                                _logger.error(f"Delivery Order sync failed: {message}")
                                store.create_cmr_store_server_replication_log('failure', message)
                                store.create_cmr_store_replication_log(
                                    response_json['object_name'], self.id, 200, 'add', 'failure', message)
                            else:
                                _logger.info(f"Delivery Order synced: {message}")
                                store.create_cmr_store_server_replication_log('success', message)
                                store.create_cmr_store_replication_log(
                                    response_json['object_name'], self.id, 200, 'add', 'success',
                                    f"Successfully created Delivery Order {self.name}")

                        except Exception as order_exception:
                            _logger.error(f"Error processing order {order.get('name')}: {order_exception}")
                            continue

            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def return_batch_orders(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                # Fetching delivery orders
                store_return_batch_orders_search = f"http://{store_ip}:{store_port}/api/stock.picking.batch/search"
                store_return_batch_orders_domain = [('picking_type_id.name', '=', "Delivery Orders"),
                                                    ('nhcl_replication_status', '=', False)]
                store_return_batch_orders_url = f"{store_return_batch_orders_search}?domain={store_return_batch_orders_domain}"

                store_return_batch_orders_data = requests.get(store_return_batch_orders_url, headers=headers_source).json()
                store_return_batch_orders = store_return_batch_orders_data.get("data")

                if store_return_batch_orders:
                    for order in store_return_batch_orders:
                        return_batch_id = order.get("id")
                        # Ensure to loop through all picking_ids, not just the first one
                        batch = []
                        if order.get("picking_ids"):
                            for picking in order.get("picking_ids"):
                                picking_name = picking["name"]

                                # Search for the sale order related to the picking
                                sale_document = self.env['sale.order'].sudo().search([('origin', '=', picking_name)])

                                # Search for stock.picking related to the sale order
                                return_ids = self.env['stock.picking'].sudo().search([('origin', '=', sale_document.name)])

                                if return_ids:
                                    for return_id in return_ids:
                                        store_return_picking_orders_search = f"http://{store_ip}:{store_port}/api/stock.picking/search"
                                        store_return_picking_orders_domain = [('name', '=', picking_name), ]
                                        store_return_picking_orders_url = f"{store_return_picking_orders_search}?domain={store_return_picking_orders_domain}"

                                        store_return_picking_orders_data = requests.get(store_return_picking_orders_url,
                                                                                        headers=headers_source).json()
                                        store_return_picking_orders = store_return_picking_orders_data.get("data")
                                        store_return_picking_orders_data = store_return_picking_orders[0]
                                        transporter_name = store_return_picking_orders_data.get("transpoter_id")
                                        transported_id = False
                                        if transporter_name:
                                            transporter = transporter_name[0]["name"]
                                            transported_id = self.env['dev.transport.details'].sudo().search(
                                                [('name', '=', transporter)])

                                        transporter_route_name = store_return_picking_orders_data.get("transpoter_route_id")
                                        transported_route_id = False
                                        if transporter_route_name:
                                            transporter_route = transporter_route_name[0]["name"]
                                            transported_route_id = self.env['dev.routes.details'].sudo().search(
                                                [('name', '=', transporter_route)])
                                        if store_return_picking_orders_data:
                                            transport_data = {
                                                'lr_number': store_return_picking_orders_data.get("lr_number"),
                                                'vehicle_number': store_return_picking_orders_data.get("vehicle_number"),
                                                'driver_name': store_return_picking_orders_data.get("driver_name"),
                                                'no_of_parcel': store_return_picking_orders_data.get("no_of_parcel"),
                                                'nhcl_tracking_number': store_return_picking_orders_data.get(
                                                    "tracking_number"),
                                                'transpoter_id': transported_id,
                                                'transpoter_route_id': transported_route_id,
                                            }
                                            return_id.write(transport_data)
                                        batch.append(return_id.id)  # Append the picking ID to the batch list


                        # Now batch should contain all picking ids associated with the order

                        # Fetch the company details for the order
                        company = order.get("company_id")[0]["name"]
                        store_stock_picking_type = self.env['stock.picking.type'].search(
                            [('name', '=', "Delivery Orders"), ('company_id.name', '=', company)])

                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        company_id = res_company_ids.id if res_company_ids else False

                        if batch:
                            # Prepare the batch order data
                            batch_data = {
                                "user_id": 2,
                                "nhcl_company": 1,
                                'picking_type_id': store_stock_picking_type.id,
                                'name': order.get("name"),
                                'picking_ids': batch,
                                'company_id': company_id,
                            }
                            # Create the stock.picking.batch record
                            batch_order = self.env['stock.picking.batch'].create(batch_data)
                            batch_list = {
                                'nhcl_replication_status': True,
                            }
                            store_return_batch_update = f"http://{store_ip}:{store_port}/api/stock.picking.batch/{return_batch_id}"
                            response = requests.put(store_return_batch_update, headers=headers_source, json=batch_list)
                            response.raise_for_status()
                            response_json = response.json()

                            message = response_json.get("message", "No message provided")
                            response_code = response_json.get("responseCode", "No response code provided")
                            if response_json.get("success") == False:
                                _logger.info(
                                    f"Failed to create Batch Transfer {message} '{store_ip}' with partner '{store_port}'. Error: ")
                                logging.error(
                                    f"Failed to create Batch Transfer  {message} '{store_ip}' with partner '{store_port}'. Error:")
                                ho_store_id.create_cmr_store_server_replication_log('success', message)
                                ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                             'add', 'failure', message)
                            else:
                                _logger.info(
                                    f"Successfully created Batch Transfer {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                                logging.info(
                                    f"Successfully created Product Variant {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                                ho_store_id.create_cmr_store_server_replication_log('success', message)
                                ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                             'add', 'success', f"Successfully created Product Variant {self.name}")
            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def store_return_order(self):
        self.env['nhcl.initiated.status.log'].create(
            {'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.initiated.status.log"),
             'nhcl_date_of_log': datetime.now(), 'nhcl_job_name': 'Store Goods Return Transaction',
             'nhcl_status': 'success',
             'nhcl_details_status': 'Function Triggered'})
        self.get_store_delivery_orders()
        self.return_batch_orders()
        self.env['nhcl.initiated.status.log'].create(
            {'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.initiated.status.log"),
             'nhcl_date_of_log': datetime.now(), 'nhcl_job_name': 'Store Goods Return Transaction',
             'nhcl_status': 'success',
             'nhcl_details_status': 'Function Completed'})

