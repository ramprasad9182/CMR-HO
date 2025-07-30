
from odoo import models, fields, api, _, Command
import requests
import logging
import random
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)
from datetime import datetime
import pytz

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    nhcl_store_je = fields.Boolean('Store Payment', default=False, copy=False)


class Picking(models.Model):
    _inherit = "stock.picking"

    nhcl_store_delivery = fields.Boolean('Store Delivery', default=False, copy=False)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    nhcl_store_delivery = fields.Boolean('Store Delivery', default=False, copy=False)


class AccountMove(models.Model):
    _inherit = "account.move"

    nhcl_store_je = fields.Boolean('Store JE', default=False, copy=False)

    @api.model
    def create(self, vals_list):
        res = super(AccountMove, self).create(vals_list)
        if res and 'line_ids' in vals_list and 'nhcl_store_je' in vals_list and vals_list['nhcl_store_je'] == True:
            res.action_post()
        elif res and 'invoice_line_ids' in vals_list and 'nhcl_store_je' in vals_list and vals_list['nhcl_store_je'] == True:
            res.sudo().action_post()
            journal_id = self.env['account.journal'].sudo().search(
                [('name', '=', 'Cash'), ('company_id', '=', res.company_id.id)])
            payment = self.env['account.payment'].sudo().create({
                'amount': res.amount_total,
                'date': res.invoice_date,
                'journal_id': journal_id.id,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': res.partner_id.id,
                'ref':res.name,
                'company_id':res.company_id.id,
                'currency_id':res.currency_id.id,
            })
            payment.action_post()
        return res

    def get_pos_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True),])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "Point of Sale"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        parent_company = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])
                        company_id = res_company_ids.id if res_company_ids else False
                        journal = self.env['account.journal'].sudo().search([('name','=','Point of Sale'),('company_id.name','=',company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','Point of Sale'),
                                 ('company_id.name', '=', parent_company.name)])
                        move_id = self.env['account.move']
                        tax_id_var = False
                        for line in entry.get("line_ids"):
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                        headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            if store_account_move_line_data1[0]["tax_line_id"] and tax_id_var == False:
                                tax_id_var = True
                            if tax_id_var == True:
                                move_id = self.env['account.move'].search(
                                    [('ref', '=', entry.get("ref")), ('company_id.name', '=', company)])

                                if not move_id:
                                    vals = {
                                        "name": entry.get("name"),
                                        "ref": entry.get("ref"),
                                        "date": entry.get("date"),
                                        "move_type": entry.get("move_type"),
                                        "journal_id": journal.id,
                                        "amount_total": entry.get("amount_total"),
                                        "company_id": company_id,
                                    }
                                    move_id = self.create(vals)
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]), ('company_id.name', '=', company)])
                                if not account_id and parent_company:
                                    account_id = self.env['account.account'].sudo().search(
                                        [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                         ('company_id.name', '=', parent_company.name)])
                                invoice_line_vals = {
                                    "id": line['id'],
                                    "name": line['name'] if 'name' in line else False,
                                    "account_id": account_id.id,
                                    "move_id":move_id.id,
                                    "debit":store_account_move_line_data1[0]["debit"],
                                    "credit":store_account_move_line_data1[0]["credit"],

                                    }
                                move_line_ids = move_id.line_ids.with_context(check_move_validity=False).create(invoice_line_vals)

                        if move_id.line_ids:
                            move_id.action_post()

                        journal_list = {
                            'nhcl_replication_status': True,

                        }
                        store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                        response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                        response.raise_for_status()
                        response_json = response.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                            logging.error(
                                f"Failed to create Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', message)

                        else:
                            _logger.info(
                                f"Successfully created Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            logging.info(
                                f"Successfully created Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'success', f"Successfully created Journal Entry {self.name}")

                else:
                    _logger.info(
                        f"Failed to create Journal Entry'{store_ip}' with partner '{store_port}'. Error: ")
                    logging.error(
                        f"Failed to create Journal Entry'{store_ip}' with partner '{store_port}'. Error:")
            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_delivery_orders(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                # Fetching delivery orders
                store_pos_delivery_orders_search = f"http://{store_ip}:{store_port}/api/stock.picking/search"
                store_pos_delivery_orders_domain = [('picking_type_id.name', '=', "PoS Orders"), ('nhcl_replication_status','=',False), ('state','=','done')]
                store_pos_delivery_orders_url = f"{store_pos_delivery_orders_search}?domain={store_pos_delivery_orders_domain}"

                store_pos_delivery_orders_data = requests.get(store_pos_delivery_orders_url, headers=headers_source).json()
                store_pos_delivery_orders = store_pos_delivery_orders_data.get("data")
                if store_pos_delivery_orders:
                    for order in store_pos_delivery_orders:
                        if order.get("location_id")[0]["name"] != "Customers":
                            store_picking_id = order.get("id")
                            company = order.get("company_id")[0]["name"]
                            res_company_ids = self.env['res.company'].search([('name', '=', company)])

                            company_id = res_company_ids.id if res_company_ids else False
                            store_stock_picking_type = self.env['stock.picking.type'].search([('name', '=', "PoS Orders"),('company_id.name', '=', company)])
                            location = order.get("location_id")[0]["id"]
                            store_location_url = f"http://{store_ip}:{store_port}/api/stock.location/{location}"
                            store_location_data = requests.get(store_location_url,
                                                               headers=headers_source).json()
                            store_location_data1 = store_location_data.get("data")
                            location_data2 = store_location_data1[0]["location_id"][0]["name"]
                            location_id = self.env['stock.location'].sudo().search(
                                [('location_id.name', '=', location_data2), ("active", "!=", False),
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
                                        # "location_id": store_account_move_line_data1[0]["location_id"][0]["id"],
                                        "location_id": location_data3.id,
                                        "location_dest_id": store_account_move_line_data1[0]["location_dest_id"][0]["id"],
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

    def get_pos_bank_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "Bank"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        parent_company  = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])

                        company_id = res_company_ids.id if res_company_ids else False
                        journal = self.env['account.journal'].sudo().search(
                            [('name', '=', 'Bank'), ('company_id.name', '=', company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','Bank'),
                                 ('company_id.name', '=', parent_company.name)])
                        vals = {
                            "name": entry.get("name"),
                            "ref": entry.get("ref"),
                            "date": entry.get("date"),
                            "move_type": entry.get("move_type"),
                            "journal_id": journal.id,
                            "amount_total": entry.get("amount_total"),
                            "company_id": company_id,
                        }
                        move_id = self.create(vals)

                        for line in entry.get("line_ids"):
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                        headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            account_id = self.env['account.account'].sudo().search(
                                [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                 ('company_id.name', '=', company)])
                            if not account_id and parent_company:
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                     ('company_id.name', '=', parent_company.name)])
                            invoice_line_vals = {
                                "id": line['id'],
                                "name": line['name'] if 'name' in line else False,
                                "account_id": account_id.id,
                                "move_id": move_id.id,
                                "debit": store_account_move_line_data1[0]["debit"],
                                "credit": store_account_move_line_data1[0]["credit"],

                            }
                            move_line_ids = move_id.line_ids.with_context(check_move_validity=False).create(
                                invoice_line_vals)
                        move_id.action_post()
                        journal_list = {
                            'nhcl_replication_status': True,

                        }
                        store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                        response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                        response.raise_for_status()
                        response_json = response.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Bank Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                            logging.error(
                                f"Failed to create Bank Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', message)

                        else:
                            _logger.info(
                                f"Successfully created Bank Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            logging.info(
                                f"Successfully created Bank Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'success', f"Successfully created Bank Journal Entry {self.name}")

            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_cash_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "Cash"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        parent_company  = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])

                        company_id = res_company_ids.id if res_company_ids else False
                        journal = self.env['account.journal'].sudo().search(
                            [('name', '=', 'Cash'), ('company_id.name', '=', company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','Cash'),
                                 ('company_id.name', '=', parent_company.name)])
                        vals = {
                            "name": entry.get("name"),
                            "ref": entry.get("ref"),
                            "date": entry.get("date"),
                            "move_type": entry.get("move_type"),
                            "journal_id": journal.id,
                            "amount_total": entry.get("amount_total"),
                            "company_id": company_id,
                        }
                        move_id = self.create(vals)

                        for line in entry.get("line_ids"):
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                        headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            account_id = self.env['account.account'].sudo().search(
                                [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                 ('company_id.name', '=', company)])
                            if not account_id and parent_company:
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                     ('company_id.name', '=', parent_company.name)])
                            invoice_line_vals = {
                                "id": line['id'],
                                "name": line['name'] if 'name' in line else False,
                                "account_id": account_id.id,
                                "move_id": move_id.id,
                                "debit": store_account_move_line_data1[0]["debit"],
                                "credit": store_account_move_line_data1[0]["credit"],

                            }
                            move_line_ids = move_id.line_ids.with_context(check_move_validity=False).create(
                                invoice_line_vals)
                        journal_list = {
                            'nhcl_replication_status': True,

                        }
                        store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                        response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                        response.raise_for_status()
                        response_json = response.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Cash Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                            logging.error(
                                f"Failed to create Cash Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', message)

                        else:
                            _logger.info(
                                f"Successfully created Cash Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            logging.info(
                                f"Successfully created Cash Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'success', f"Successfully created Cash Journal Entry {self.name}")

                        move_id.action_post()

            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_hdfc_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "HDFC"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        parent_company  = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])

                        company_id = res_company_ids.id if res_company_ids else False
                        journal = self.env['account.journal'].sudo().search(
                            [('name', '=', 'HDFC'), ('company_id.name', '=', company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','HDFC'),
                                 ('company_id.name', '=', parent_company.name)])
                        vals = {
                            "name": entry.get("name"),
                            "ref": entry.get("ref"),
                            "date": entry.get("date"),
                            "move_type": entry.get("move_type"),
                            "journal_id": journal.id,
                            "amount_total": entry.get("amount_total"),
                            "company_id": company_id,
                        }
                        move_id = self.create(vals)

                        for line in entry.get("line_ids"):
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                        headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            account_id = self.env['account.account'].sudo().search(
                                [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                 ('company_id.name', '=', company)])
                            if not account_id and parent_company:
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                     ('company_id.name', '=', parent_company.name)])
                            invoice_line_vals = {
                                "id": line['id'],
                                "name": line['name'] if 'name' in line else False,
                                "account_id": account_id.id,
                                "move_id": move_id.id,
                                "debit": store_account_move_line_data1[0]["debit"],
                                "credit": store_account_move_line_data1[0]["credit"],

                            }
                            move_line_ids = move_id.line_ids.with_context(check_move_validity=False).create(
                                invoice_line_vals)
                        journal_list = {
                            'nhcl_replication_status': True,

                        }
                        store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                        response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                        response.raise_for_status()
                        response_json = response.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create HDFC Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                            logging.error(
                                f"Failed to create HDFC Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', message)

                        else:
                            _logger.info(
                                f"Successfully created HDFC Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            logging.info(
                                f"Successfully created HDFC Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'success', f"Successfully created HDFC Journal Entry {self.name}")

                        move_id.action_post()

            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_bajaj_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "BAJAJ"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        parent_company  = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])

                        company_id = res_company_ids.id if res_company_ids else False
                        journal = self.env['account.journal'].sudo().search(
                            [('name', '=', 'BAJAJ'), ('company_id.name', '=', company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','BAJAJ'),
                                 ('company_id.name', '=', parent_company.name)])
                        vals = {
                            "name": entry.get("name"),
                            "ref": entry.get("ref"),
                            "date": entry.get("date"),
                            "move_type": entry.get("move_type"),
                            "journal_id": journal.id,
                            "amount_total": entry.get("amount_total"),
                            "company_id": company_id,
                        }
                        move_id = self.create(vals)

                        for line in entry.get("line_ids"):
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                        headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            account_id = self.env['account.account'].sudo().search(
                                [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                 ('company_id.name', '=', company)])
                            if not account_id and parent_company:
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                     ('company_id.name', '=', parent_company.name)])
                            invoice_line_vals = {
                                "id": line['id'],
                                "name": line['name'] if 'name' in line else False,
                                "account_id": account_id.id,
                                "move_id": move_id.id,
                                "debit": store_account_move_line_data1[0]["debit"],
                                "credit": store_account_move_line_data1[0]["credit"],

                            }
                            move_line_ids = move_id.line_ids.with_context(check_move_validity=False).create(
                                invoice_line_vals)
                        journal_list = {
                            'nhcl_replication_status': True,

                        }
                        store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                        response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                        response.raise_for_status()
                        response_json = response.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create BAJAJ Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                            logging.error(
                                f"Failed to create BAJAJ Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', message)

                        else:
                            _logger.info(
                                f"Successfully created BAJAJ Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            logging.info(
                                f"Successfully created BAJAJ Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'success', f"Successfully created BAJAJ Journal Entry {self.name}")
                        move_id.action_post()
            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_mobikwik_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "Mobikwik"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        parent_company  = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])

                        company_id = res_company_ids.id if res_company_ids else False
                        journal = self.env['account.journal'].sudo().search(
                            [('name', '=', 'Mobikwik'), ('company_id.name', '=', company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','Mobikwik'),
                                 ('company_id.name', '=', parent_company.name)])
                        vals = {
                            "name": entry.get("name"),
                            "ref": entry.get("ref"),
                            "date": entry.get("date"),
                            "move_type": entry.get("move_type"),
                            "journal_id": journal.id,
                            "amount_total": entry.get("amount_total"),
                            "company_id": company_id,
                        }
                        move_id = self.create(vals)

                        for line in entry.get("line_ids"):
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                        headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            account_id = self.env['account.account'].sudo().search(
                                [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                 ('company_id.name', '=', company)])
                            if not account_id and parent_company:
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                     ('company_id.name', '=', parent_company.name)])
                            invoice_line_vals = {
                                "id": line['id'],
                                "name": line['name'] if 'name' in line else False,
                                "account_id": account_id.id,
                                "move_id": move_id.id,
                                "debit": store_account_move_line_data1[0]["debit"],
                                "credit": store_account_move_line_data1[0]["credit"],

                            }
                            move_line_ids = move_id.line_ids.with_context(check_move_validity=False).create(
                                invoice_line_vals)
                        journal_list = {
                            'nhcl_replication_status': True,

                        }
                        store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                        response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                        response.raise_for_status()
                        response_json = response.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create mobikwik Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                            logging.error(
                                f"Failed to create mobikwik Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', message)

                        else:
                            _logger.info(
                                f"Successfully created mobikwik Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            logging.info(
                                f"Successfully created mobikwik Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', f"Successfully created mobikwik Journal Entry {self.name}")
                        move_id.action_post()

            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def  get_pos_sbi_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "SBI"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        parent_company  = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])

                        company_id = res_company_ids.id if res_company_ids else False
                        journal = self.env['account.journal'].sudo().search(
                            [('name', '=', 'SBI'), ('company_id.name', '=', company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','SBI'),
                                 ('company_id.name', '=', parent_company.name)])
                        vals = {
                            "name": entry.get("name"),
                            "ref": entry.get("ref"),
                            "date": entry.get("date"),
                            "move_type": entry.get("move_type"),
                            "journal_id": journal.id,
                            "amount_total": entry.get("amount_total"),
                            "company_id": company_id,
                        }
                        move_id = self.create(vals)

                        for line in entry.get("line_ids"):
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                        headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            account_id = self.env['account.account'].sudo().search(
                                [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                 ('company_id.name', '=', company)])
                            if not account_id and parent_company:
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                     ('company_id.name', '=', parent_company.name)])
                            invoice_line_vals = {
                                "id": line['id'],
                                "name": line['name'] if 'name' in line else False,
                                "account_id": account_id.id,
                                "move_id": move_id.id,
                                "debit": store_account_move_line_data1[0]["debit"],
                                "credit": store_account_move_line_data1[0]["credit"],

                            }
                            move_line_ids = move_id.line_ids.with_context(check_move_validity=False).create(
                                invoice_line_vals)
                        journal_list = {
                            'nhcl_replication_status': True,

                        }
                        store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                        response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                        response.raise_for_status()
                        response_json = response.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create SBI Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                            logging.error(
                                f"Failed to create SBI Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', message)

                        else:
                            _logger.info(
                                f"Successfully created SBI Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            logging.info(
                                f"Successfully created SBI Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'success', f"Successfully created SBI Journal Entry {self.name}")
                        move_id.action_post()

            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_paytm_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "Paytm"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        parent_company  = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])

                        company_id = res_company_ids.id if res_company_ids else False
                        journal = self.env['account.journal'].sudo().search(
                            [('name', '=', 'Paytm'), ('company_id.name', '=', company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','Paytm'),
                                 ('company_id.name', '=', parent_company.name)])
                        vals = {
                            "name": entry.get("name"),
                            "ref": entry.get("ref"),
                            "date": entry.get("date"),
                            "move_type": entry.get("move_type"),
                            "journal_id": journal.id,
                            "amount_total": entry.get("amount_total"),
                            "company_id": company_id,
                        }
                        move_id = self.create(vals)

                        for line in entry.get("line_ids"):
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                        headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            account_id = self.env['account.account'].sudo().search(
                                [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                 ('company_id.name', '=', company)])
                            if not account_id and parent_company:
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                     ('company_id.name', '=', parent_company.name)])
                            invoice_line_vals = {
                                "id": line['id'],
                                "name": line['name'] if 'name' in line else False,
                                "account_id": account_id.id,
                                "move_id": move_id.id,
                                "debit": store_account_move_line_data1[0]["debit"],
                                "credit": store_account_move_line_data1[0]["credit"],

                            }
                            move_line_ids = move_id.line_ids.with_context(check_move_validity=False).create(
                                invoice_line_vals)
                        journal_list = {
                            'nhcl_replication_status': True,

                        }
                        store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                        response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                        response.raise_for_status()
                        response_json = response.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Paytm Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                            logging.error(
                                f"Failed to create Paytm Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', message)

                        else:
                            _logger.info(
                                f"Successfully created Paytm Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            logging.info(
                                f"Successfully created Paytm Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'success', f"Successfully created Paytm Journal Entry {self.name}")
                        move_id.action_post()

            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_axis_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "Axis"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        parent_company  = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])

                        company_id = res_company_ids.id if res_company_ids else False
                        journal = self.env['account.journal'].sudo().search(
                            [('name', '=', 'Axis'), ('company_id.name', '=', company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','Axis'),
                                 ('company_id.name', '=', parent_company.name)])
                        vals = {
                            "name": entry.get("name"),
                            "ref": entry.get("ref"),
                            "date": entry.get("date"),
                            "move_type": entry.get("move_type"),
                            "journal_id": journal.id,
                            "amount_total": entry.get("amount_total"),
                            "company_id": company_id,
                        }
                        move_id = self.create(vals)

                        for line in entry.get("line_ids"):
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                        headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            account_id = self.env['account.account'].sudo().search(
                                [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                 ('company_id.name', '=', company)])
                            if not account_id and parent_company:
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                     ('company_id.name', '=', parent_company.name)])
                            invoice_line_vals = {
                                "id": line['id'],
                                "name": line['name'] if 'name' in line else False,
                                "account_id": account_id.id,
                                "move_id": move_id.id,
                                "debit": store_account_move_line_data1[0]["debit"],
                                "credit": store_account_move_line_data1[0]["credit"],

                            }
                            move_line_ids = move_id.line_ids.with_context(check_move_validity=False).create(
                                invoice_line_vals)
                        journal_list = {
                            'nhcl_replication_status': True,

                        }
                        store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                        response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                        response.raise_for_status()
                        response_json = response.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Axis Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                            logging.error(
                                f"Failed to create Axis Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', message)

                        else:
                            _logger.info(
                                f"Successfully created Axis Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            logging.info(
                                f"Successfully created Axis Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'success', f"Successfully created Axis Journal Entry {self.name}")

                        move_id.action_post()

            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_cheque_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "Cheque"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        parent_company  = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])

                        company_id = res_company_ids.id if res_company_ids else False
                        journal = self.env['account.journal'].sudo().search(
                            [('name', '=', 'Cheque'), ('company_id.name', '=', company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','Cheque'),
                                 ('company_id.name', '=', parent_company.name)])
                        vals = {
                            "name": entry.get("name"),
                            "ref": entry.get("ref"),
                            "date": entry.get("date"),
                            "move_type": entry.get("move_type"),
                            "journal_id": journal.id,
                            "amount_total": entry.get("amount_total"),
                            "company_id": company_id,
                        }
                        move_id = self.create(vals)

                        for line in entry.get("line_ids"):
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                        headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            account_id = self.env['account.account'].sudo().search(
                                [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                 ('company_id.name', '=', company)])
                            if not account_id and parent_company:
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                     ('company_id.name', '=', parent_company.name)])
                            invoice_line_vals = {
                                "id": line['id'],
                                "name": line['name'] if 'name' in line else False,
                                "account_id": account_id.id,
                                "move_id": move_id.id,
                                "debit": store_account_move_line_data1[0]["debit"],
                                "credit": store_account_move_line_data1[0]["credit"],

                            }
                            move_line_ids = move_id.line_ids.with_context(check_move_validity=False).create(
                                invoice_line_vals)
                        journal_list = {
                            'nhcl_replication_status': True,

                        }
                        store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                        response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                        response.raise_for_status()
                        response_json = response.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Axis Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                            logging.error(
                                f"Failed to create Axis Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', message)

                        else:
                            _logger.info(
                                f"Successfully created Axis Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            logging.info(
                                f"Successfully created Axis Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'success', f"Successfully created Axis Journal Entry {self.name}")

                        move_id.action_post()

            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_credit_note_settlement_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "Credit Note Settlement"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        parent_company  = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])

                        company_id = res_company_ids.id if res_company_ids else False
                        journal = self.env['account.journal'].sudo().search(
                            [('name', '=', 'Credit Note Settlement'), ('company_id.name', '=', company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','Credit Note Settlement'),
                                 ('company_id.name', '=', parent_company.name)])
                        vals = {
                            "name": entry.get("name"),
                            "ref": entry.get("ref"),
                            "date": entry.get("date"),
                            "move_type": entry.get("move_type"),
                            "journal_id": journal.id,
                            "amount_total": entry.get("amount_total"),
                            "company_id": company_id,
                        }
                        move_id = self.create(vals)

                        for line in entry.get("line_ids"):
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                        headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            account_id = self.env['account.account'].sudo().search(
                                [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                 ('company_id.name', '=', company)])
                            if not account_id and parent_company:
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                     ('company_id.name', '=', parent_company.name)])
                            invoice_line_vals = {
                                "id": line['id'],
                                "name": line['name'] if 'name' in line else False,
                                "account_id": account_id.id,
                                "move_id": move_id.id,
                                "debit": store_account_move_line_data1[0]["debit"],
                                "credit": store_account_move_line_data1[0]["credit"],

                            }
                            move_line_ids = move_id.line_ids.with_context(check_move_validity=False).create(
                                invoice_line_vals)
                        journal_list = {
                            'nhcl_replication_status': True,

                        }
                        store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                        response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                        response.raise_for_status()
                        response_json = response.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Axis Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                            logging.error(
                                f"Failed to create Axis Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', message)

                        else:
                            _logger.info(
                                f"Successfully created Axis Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            logging.info(
                                f"Successfully created Axis Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'success', f"Successfully created Axis Journal Entry {self.name}")

                        move_id.action_post()

            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_gift_voucher_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "Gift Voucher"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])
                        parent_company  = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])

                        company_id = res_company_ids.id if res_company_ids else False
                        journal = self.env['account.journal'].sudo().search(
                            [('name', '=', 'Gift Voucher'), ('company_id.name', '=', company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','Gift Voucher'),
                                 ('company_id.name', '=', parent_company.name)])
                        vals = {
                            "name": entry.get("name"),
                            "ref": entry.get("ref"),
                            "date": entry.get("date"),
                            "move_type": entry.get("move_type"),
                            "journal_id": journal.id,
                            "amount_total": entry.get("amount_total"),
                            "company_id": company_id,
                        }
                        move_id = self.create(vals)

                        for line in entry.get("line_ids"):
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url,
                                                                        headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            account_id = self.env['account.account'].sudo().search(
                                [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                 ('company_id.name', '=', company)])
                            if not account_id and parent_company:
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                     ('company_id.name', '=', parent_company.name)])
                            invoice_line_vals = {
                                "id": line['id'],
                                "name": line['name'] if 'name' in line else False,
                                "account_id": account_id.id,
                                "move_id": move_id.id,
                                "debit": store_account_move_line_data1[0]["debit"],
                                "credit": store_account_move_line_data1[0]["credit"],

                            }
                            move_line_ids = move_id.line_ids.with_context(check_move_validity=False).create(
                                invoice_line_vals)
                        journal_list = {
                            'nhcl_replication_status': True,

                        }
                        store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                        response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                        response.raise_for_status()
                        response_json = response.json()

                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Axis Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                            logging.error(
                                f"Failed to create Axis Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'failure', message)

                        else:
                            _logger.info(
                                f"Successfully created Axis Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            logging.info(
                                f"Successfully created Axis Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                            ho_store_id.create_cmr_store_server_replication_log('success', message)
                            ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                         'add', 'success', f"Successfully created Axis Journal Entry {self.name}")

                        move_id.action_post()

            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_crediet_note_issue_journal_entry(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True),])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                store_journal_entry_search = f"http://{store_ip}:{store_port}/api/account.move/search"
                store_journal_entry_domain = [('journal_id', '=', "Credit Note Issue"), ('nhcl_replication_status', '=', False)]
                store_journal_entry_url = f"{store_journal_entry_search}?domain={store_journal_entry_domain}"
                store_journal_entry_data = requests.get(store_journal_entry_url, headers=headers_source).json()
                store_journal_entry = store_journal_entry_data.get("data")
                if store_journal_entry:
                    for entry in store_journal_entry:
                        store_journal_id = entry.get("id")
                        company = entry.get("company_id")[0]["name"]
                        res_company_ids = self.env['res.company'].search([('name', '=', company)])

                        company_id = res_company_ids.id if res_company_ids else False
                        parent_company = False
                        if res_company_ids.parent_id:
                            parent_company = self.env['res.company'].search([('name', '=', res_company_ids.parent_id.name)])
                        journal = self.env['account.journal'].sudo().search([('name','=','Credit Note Issue'),('company_id.name','=',company)])
                        if not journal and parent_company:
                            journal = self.env['account.journal'].sudo().search(
                                [('name','=','Credit Note Issue'),
                                 ('company_id.name', '=', parent_company.name)])
                        vals = {
                            "name": entry.get("name"),
                            "ref": entry.get("ref"),
                            "date": entry.get("date"),
                            "move_type": entry.get("move_type"),
                            "journal_id": journal.id,
                            "amount_total": entry.get("amount_total"),
                            "company_id": company_id,
                            "partner_id": 1,
                        }
                        move_id = self.create(vals)
                        for line in entry.get("invoice_line_ids"):
                            store_product = f"http://{store_ip}:{store_port}/api/product.product/search"
                            store_product_domain = [('display_name', '=', line.get("name"))]
                            store_product_url = f"{store_product}?domain={store_product_domain}"
                            store_product_data = requests.get(store_product_url,
                                                                        headers=headers_source).json()
                            store_product_data1 = store_product_data.get("data")
                            store_account_move_line = f"http://{store_ip}:{store_port}/api/account.move.line/search"
                            store_account_move_line_domain = [('id', '=', line['id'])]
                            store_account_move_line_url = f"{store_account_move_line}?domain={store_account_move_line_domain}"
                            store_account_move_line_data = requests.get(store_account_move_line_url, headers=headers_source).json()
                            store_account_move_line_data1 = store_account_move_line_data.get("data")
                            product_id = self.env['product.product'].search([('barcode','=',line.get("name"))])
                            account_id = self.env['account.account'].sudo().search(
                                [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                 ('company_id.name', '=', company)])
                            if not account_id and parent_company:
                                account_id = self.env['account.account'].sudo().search(
                                    [('name', '=', store_account_move_line_data1[0]["account_id"][0]["name"]),
                                     ('company_id.name', '=', parent_company.name)])
                            invoice_line_vals = {
                                "id": line['id'],
                                "name": line['name'] if 'name' in line else False,
                                "account_id": account_id.id,
                                "move_id":move_id.id,
                                "price_unit": entry.get("amount_total"),

                            }
                            move_line_ids = move_id.invoice_line_ids.with_context(check_move_validity=False).create(invoice_line_vals)
                            journal_list = {
                                'nhcl_replication_status': True,

                            }
                            store_journal_entry_update = f"http://{store_ip}:{store_port}/api/account.move/{store_journal_id}"
                            response = requests.put(store_journal_entry_update, headers=headers_source, json=journal_list)
                            response.raise_for_status()
                            response_json = response.json()

                            message = response_json.get("message", "No message provided")
                            response_code = response_json.get("responseCode", "No response code provided")
                            if response_json.get("success") == False:
                                _logger.info(
                                    f"Failed to create Credit Note Journal Entry {message} '{store_ip}' with partner '{store_port}'. Error: ")
                                logging.error(
                                    f"Failed to create Credit Note Journal Entry  {message} '{store_ip}' with partner '{store_port}'. Error:")
                                ho_store_id.create_cmr_store_server_replication_log('success', message)
                                ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                             'add', 'failure', message)

                            else:
                                _logger.info(
                                    f"Successfully created Credit Note Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                                logging.info(
                                    f"Successfully created Credit Note Journal Entry {self.name} {message} '{store_ip}' with partner '{store_port}'.")
                                ho_store_id.create_cmr_store_server_replication_log('success', message)
                                ho_store_id.create_cmr_store_replication_log(response_json['object_name'], self.id, 200,
                                                                             'add', 'success', f"Successfully created Credit Note Journal Entry {self.name}")

                        move_id.action_post()
            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)

    def get_pos_exchange_recipts_orders(self):
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True), ])

        for store in ho_store_id:
            try:
                store_ip = store.nhcl_terminal_ip
                store_port = store.nhcl_port_no
                store_api_key = store.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}

                # Fetching delivery orders
                store_pos_exchange_orders_search = f"http://{store_ip}:{store_port}/api/stock.picking/search"
                store_pos_exchange_orders_domain = [('picking_type_id.name', '=', "Product Exchange - POS"),
                                                    ('nhcl_replication_status', '=', False), ('state', '=', 'done')]
                store_pos_exchange_orders_url = f"{store_pos_exchange_orders_search}?domain={store_pos_exchange_orders_domain}"

                store_pos_exchange_orders_data = requests.get(store_pos_exchange_orders_url, headers=headers_source).json()
                store_pos_exchange_orders = store_pos_exchange_orders_data.get("data")
                if store_pos_exchange_orders:
                    for order in store_pos_exchange_orders:
                        if order.get("location_id")[0]["name"] == "Customers":
                            store_picking_id = order.get("id")
                            company = order.get("company_id")[0]["name"]
                            res_company_ids = self.env['res.company'].search([('name', '=', company)])

                            company_id = res_company_ids.id if res_company_ids else False
                            store_stock_picking_type = self.env['stock.picking.type'].search(
                                [('name', '=', "Product Exchange - POS"), ('company_id.name', '=', company)])
                            location = order.get("location_id")[0]["id"]
                            store_location_url = f"http://{store_ip}:{store_port}/api/stock.location/{location}"
                            store_location_data = requests.get(store_location_url,
                                                               headers=headers_source).json()
                            store_location_data1 = store_location_data.get("data")
                            location_data2 = store_location_data1[0]["location_id"][0]["name"]
                            location_id = self.env['stock.location'].sudo().search(
                                [('location_id.name', '=', location_data2), ("active", "!=", False),
                                 ('usage', '=', 'internal'), ('company_id.name', '=', company)])
                            location_dest = order.get("location_dest_id")[0]["id"]
                            store_location_dest_url = f"http://{store_ip}:{store_port}/api/stock.location/{location_dest}"
                            store_location_dest_data = requests.get(store_location_dest_url,
                                                                    headers=headers_source).json()
                            store_location_dest_data1 = store_location_dest_data.get("data")
                            location_dest_data2 = store_location_dest_data1[0]["complete_name"]
                            location_dest_id = self.env['stock.location'].sudo().search(
                                [('complete_name', '=', location_dest_data2), ("active", "!=", False)])
                            partner_id = order.get("partner_id")
                            partner_name = partner_id[0]["name"]
                            existing_partner = self.env['res.partner'].sudo().search([('name', '=', partner_name)], limit=1)

                            if existing_partner:
                                partner = existing_partner
                            else:
                                partner_data = {
                                    'name': partner_name
                                }
                                partner = self.env['res.partner'].create(partner_data)

                            if order.get("name") == 'same':
                                stock_picking_data = {
                                    'partner_id': partner.id,
                                    'picking_type_id': store_stock_picking_type.id,
                                    'origin': order.get("name"),
                                    'location_id': 4,
                                    'location_dest_id': location_dest_id.id,
                                    'company_id': company_id,
                                    'stock_type': "pos_exchange",
                                    'company_type': order.get("company_type"),
                                    'move_type': 'direct',
                                    'state': 'done',
                                }
                            else:
                                stock_picking_data = {
                                    'partner_id': partner.id,
                                    'picking_type_id': store_stock_picking_type.id,
                                    'origin': order.get("name"),
                                    'store_pos_order': order.get("store_pos_order"),
                                    'store_name': 2,
                                    'location_id': 4,
                                    'location_dest_id': location_dest_id.id,
                                    'company_id': company_id,
                                    'stock_type': "pos_exchange",
                                    'company_type': order.get("company_type"),
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
                                     ('usage', '=', 'internal'), ('company_id.name', '=', company)])
                                lot_id = self.env['stock.lot'].sudo().search(
                                    [('name', '=', lot_name), ('company_id.name', '=', company)])
                                main_company = self.env['res.company'].sudo().search([('nhcl_company_bool', '=', True)])
                                cost_price = self.env['stock.lot'].sudo().search(
                                    [('name', '=', lot_name), ('company_id', '=', main_company.id)])
                                rs_price = 0.0
                                if store_account_move_line_data1[0]["rs_price"]:
                                    rs_price = store_account_move_line_data1[0]["rs_price"]
                                mr_price = 0.0
                                if store_account_move_line_data1[0]["mr_price"]:
                                    mr_price = store_account_move_line_data1[0]["mr_price"]
                                internal_ref_lot = False
                                if store_account_move_line_data1[0]["internal_ref_lot"]:
                                    internal_ref_lot = store_account_move_line_data1[0]["internal_ref_lot"]
                                type_product = None
                                if store_account_move_line_data1[0]["type_product"]:
                                    type_product = store_account_move_line_data1[0]["type_product"]
                                product_categ_1 = store_account_move_line_data1[0]["categ_1"]
                                categ_1 = False
                                if product_categ_1:
                                    categ_1 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_categ_1[0]["name"])])

                                product_categ_2 = store_account_move_line_data1[0]["categ_2"]
                                categ_2 = False
                                if product_categ_2:
                                    categ_2 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_categ_2[0]["name"])])

                                product_categ_3 = store_account_move_line_data1[0]["categ_3"]
                                categ_3 = False
                                if product_categ_3:
                                    categ_3 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_categ_3[0]["name"])])

                                product_categ_4 = store_account_move_line_data1[0]["categ_4"]
                                categ_4 = False
                                if product_categ_4:
                                    categ_4 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_categ_4[0]["name"])])

                                product_categ_5 = store_account_move_line_data1[0]["categ_5"]
                                categ_5 = False
                                if product_categ_5:
                                    categ_5 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_categ_5[0]["name"])])

                                product_categ_6 = store_account_move_line_data1[0]["categ_6"]
                                categ_6 = False
                                if product_categ_6:
                                    categ_6 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_categ_6[0]["name"])])

                                product_categ_7 = store_account_move_line_data1[0]["categ_7"]
                                categ_7 = False
                                if product_categ_7:
                                    categ_7 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_categ_7[0]["name"])])

                                product_categ_8 = store_account_move_line_data1[0]["categ_8"]
                                categ_8 = False
                                if product_categ_8:
                                    categ_8 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_categ_8[0]["name"])])

                                product_descrip_1 = store_account_move_line_data1[0]["descrip_1"]
                                descrip_1 = False
                                if product_descrip_1:
                                    descrip_1 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_descrip_1[0]["name"])])

                                product_descrip_2 = store_account_move_line_data1[0]["descrip_2"]
                                descrip_2 = False
                                if product_descrip_1:
                                    descrip_2 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_descrip_2[0]["name"])])

                                product_descrip_3 = store_account_move_line_data1[0]["descrip_3"]
                                descrip_3 = False
                                if product_descrip_3:
                                    descrip_3 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_descrip_3[0]["name"])])

                                product_descrip_4 = store_account_move_line_data1[0]["descrip_4"]
                                descrip_4 = False
                                if product_descrip_4:
                                    descrip_4 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_descrip_4[0]["name"])])

                                product_descrip_5 = store_account_move_line_data1[0]["descrip_5"]
                                descrip_5 = False
                                if product_descrip_5:
                                    descrip_5 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_descrip_5[0]["name"])])

                                product_descrip_6 = store_account_move_line_data1[0]["descrip_6"]
                                descrip_6 = False
                                if product_descrip_6:
                                    descrip_6 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_descrip_6[0]["name"])])

                                product_descrip_7 = store_account_move_line_data1[0]["descrip_7"]
                                descrip_7 = False
                                if product_descrip_7:
                                    descrip_7 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_descrip_7[0]["name"])])

                                product_descrip_8 = store_account_move_line_data1[0]["descrip_8"]
                                descrip_8 = False
                                if product_descrip_8:
                                    descrip_8 = self.env['product.attribute.value'].sudo().search(
                                        [('name', '=', product_descrip_8[0]["name"])])

                                if store_account_move_line_data1 and order.get("company_type") == 'same':
                                    move_line_vals = {
                                        "picking_id": stock_picking.id,
                                        "product_id": ho_product.id,
                                        "product_uom_id": store_account_move_line_data1[0]["product_uom_id"][0]["id"],
                                        "quantity": store_account_move_line_data1[0]["quantity"],
                                        "location_id": 4,
                                        "location_dest_id": location_dest_id.id,
                                        "lot_id": lot_id.id,
                                        "rs_price": rs_price,
                                        "mr_price": mr_price,
                                        "cost_price": cost_price.cost_price,
                                        "internal_ref_lot": internal_ref_lot,
                                        "type_product": type_product,
                                        "categ_1": categ_1.id if categ_1 else False,
                                        "categ_2": categ_2.id if categ_2 else False,
                                        "categ_3": categ_3.id if categ_3 else False,
                                        "categ_4": categ_4.id if categ_4 else False,
                                        "categ_5": categ_5.id if categ_5 else False,
                                        "categ_6": categ_6.id if categ_6 else False,
                                        "categ_7": categ_7.id if categ_7 else False,
                                        "categ_8": categ_8.id if categ_8 else False,
                                        "descrip_1": descrip_1.id if descrip_1 else False,
                                        "descrip_2": descrip_2.id if descrip_2 else False,
                                        "descrip_3": descrip_3.id if descrip_3 else False,
                                        "descrip_4": descrip_4.id if descrip_4 else False,
                                        "descrip_5": descrip_5.id if descrip_5 else False,
                                        "descrip_6": descrip_6.id if descrip_6 else False,
                                        "descrip_7": descrip_7.id if descrip_7 else False,
                                        "descrip_8": descrip_8.id if descrip_8 else False,
                                    }
                                else:
                                    move_line_vals = {
                                        "picking_id": stock_picking.id,
                                        "product_id": ho_product.id,
                                        "product_uom_id": store_account_move_line_data1[0]["product_uom_id"][0]["id"],
                                        "quantity": store_account_move_line_data1[0]["quantity"],
                                        "location_id": 4,
                                        "location_dest_id": location_dest_id.id,
                                        "lot_name": lot_name,
                                        "rs_price": rs_price,
                                        "mr_price": mr_price,
                                        "cost_price": cost_price.cost_price,
                                        "internal_ref_lot": internal_ref_lot,
                                        "type_product": type_product,
                                        "categ_1": categ_1.id if categ_1 else False,
                                        "categ_2": categ_2.id if categ_2 else False,
                                        "categ_3": categ_3.id if categ_3 else False,
                                        "categ_4": categ_4.id if categ_4 else False,
                                        "categ_5": categ_5.id if categ_5 else False,
                                        "categ_6": categ_6.id if categ_6 else False,
                                        "categ_7": categ_7.id if categ_7 else False,
                                        "categ_8": categ_8.id if categ_8 else False,
                                        "descrip_1": descrip_1.id if descrip_1 else False,
                                        "descrip_2": descrip_2.id if descrip_2 else False,
                                        "descrip_3": descrip_3.id if descrip_3 else False,
                                        "descrip_4": descrip_4.id if descrip_4 else False,
                                        "descrip_5": descrip_5.id if descrip_5 else False,
                                        "descrip_6": descrip_6.id if descrip_6 else False,
                                        "descrip_7": descrip_7.id if descrip_7 else False,
                                        "descrip_8": descrip_8.id if descrip_8 else False,
                                    }
                                stock_move_line = self.env['stock.move.line'].create(move_line_vals)

                            stock_picking.button_validate()
                            picking_list = {
                                'nhcl_replication_status': True,

                            }
                            store_pos_delivery_update = f"http://{store_ip}:{store_port}/api/stock.picking/{store_picking_id}"
                            response = requests.put(store_pos_delivery_update, headers=headers_source, json=picking_list)
                            response.raise_for_status()
                            response_json = response.json()

                            message = response_json.get("message", "No message provided")
                            response_code = response_json.get("responseCode", "No response code provided")
                            if response_json.get("success") == False:
                                _logger.info(
                                    f"Failed to create Product Variant {message} '{store_ip}' with partner '{store_port}'. Error: ")
                                logging.error(
                                    f"Failed to create Product Variant  {message} '{store_ip}' with partner '{store_port}'. Error:")


                            else:
                                _logger.info(
                                    f"Successfully created Product Variant {stock_picking.name} {message} '{store_ip}' with partner '{store_port}'.")
                                logging.info(
                                    f"Successfully created Product Variant {stock_picking.name} {message} '{store_ip}' with partner '{store_port}'.")

            except Exception as e:
                store.create_cmr_transaction_server_replication_log("failure", e)







