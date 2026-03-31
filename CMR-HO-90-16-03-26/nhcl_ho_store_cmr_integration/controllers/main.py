from odoo import http
from odoo.http import request
import logging


_logger = logging.getLogger(__name__)

class StockPickingController(http.Controller):
    @http.route('/api/stock.picking/call_action', type='json', auth='public', methods=['POST'],csrf=False)
    def validate_picking(self,**kwargs):
        ho_store_id = request.env['nhcl.ho.store.master'].sudo().search(
                    [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        store_pos_delivery_orders = request.env['stock.picking'].sudo().search([('nhcl_store_delivery', '=', True),
                                                                                ('state', '=', 'assigned'),
                                                                                ('stock_picking_type', '=', 'pos_order'),])

        if store_pos_delivery_orders:
            for order in store_pos_delivery_orders:
                try:
                    order.with_context(skip_sanity_check=True).sudo().button_validate()
                except Exception as e:
                    ho_store_id.create_cmr_transaction_server_replication_log("failure", e)

    @http.route('/api/stock.picking/main_damage_action', type='json', auth='public', methods=['POST'], csrf=False)
    def validate_main_damage_picking(self, **kwargs):
        ho_store_id = request.env['nhcl.ho.store.master'].sudo().search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        store_main_damage_delivery_orders = request.env['stock.picking'].sudo().search(
            [('nhcl_store_delivery', '=', True), ('state', '=', 'assigned'),
             ('stock_picking_type', '=', 'main_damage'), ])

        if store_main_damage_delivery_orders:
            for order in store_main_damage_delivery_orders:
                try:
                    order.with_context(skip_sanity_check=True).sudo().button_validate()
                except Exception as e:
                    ho_store_id.create_cmr_transaction_server_replication_log("failure", e)


    @http.route('/api/stock.picking/damage_main_action', type='json', auth='public', methods=['POST'], csrf=False)
    def validate_damage_main_picking(self, **kwargs):
        ho_store_id = request.env['nhcl.ho.store.master'].sudo().search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        store_damage_main_delivery_orders = request.env['stock.picking'].sudo().search(
            [('nhcl_store_delivery', '=', True), ('state', '=', 'assigned'),
             ('stock_picking_type', '=', 'damage_main'), ])


        if store_damage_main_delivery_orders:
            for order in store_damage_main_delivery_orders:
                try:
                    order.with_context(skip_sanity_check=True).sudo().button_validate()
                except Exception as e:
                    ho_store_id.create_cmr_transaction_server_replication_log("failure", e)


    @http.route('/api/stock.picking/return_main_action', type='json', auth='public', methods=['POST'], csrf=False)
    def validate_return_main_picking(self, **kwargs):
        ho_store_id = request.env['nhcl.ho.store.master'].sudo().search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])

        store_return_main_delivery_orders = request.env['stock.picking'].sudo().search(
            [('nhcl_store_delivery', '=', True), ('state', '=', 'assigned'),
             ('stock_picking_type', '=', 'return_main'), ])


        if store_return_main_delivery_orders:
            for order in store_return_main_delivery_orders:
                try:
                    order.with_context(skip_sanity_check=True).sudo().button_validate()
                except Exception as e:
                    ho_store_id.create_cmr_transaction_server_replication_log("failure", e)


    # @http.route('/api/stock.picking/return_exchange_action', type='json', auth='public', methods=['POST'], csrf=False)
    # def validate_exchange_picking(self, **kwargs):
    #     ho_store_id = request.env['nhcl.ho.store.master'].sudo().search(
    #         [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
    #
    #     store_customer_return_orders = request.env['stock.picking'].sudo().search(
    #         [('nhcl_store_delivery', '=', True), ('state', 'in', ['draft','assigned']), ('stock_picking_type', '=', 'exchange'),])
    #
    #     if store_customer_return_orders:
    #         for order in store_customer_return_orders:
    #             try:
    #                 order.with_user(2).with_context(skip_sanity_check=True).sudo().button_validate()
    #             except Exception as e:
    #                 ho_store_id.create_cmr_transaction_server_replication_log("failure", e)

    @http.route('/api/stock.picking/return_action', type='json', auth='public', methods=['POST'], csrf=False)
    def validate_return_picking(self, **kwargs):
        ho_store_id = request.env['nhcl.ho.store.master'].sudo().search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])

        store_customer_return_orders = request.env['stock.picking'].sudo().search(
            [('nhcl_store_delivery', '=', True), ('state', '=', 'assigned'), ('stock_picking_type', '=', 'return'), ])

        if store_customer_return_orders:
            for order in store_customer_return_orders:
                try:
                    order.with_context(skip_sanity_check=True).sudo().button_validate()
                except Exception as e:
                    ho_store_id.create_cmr_transaction_server_replication_log("failure", e)


class SaleOrderController(http.Controller):
    @http.route('/api/sale.order/call_action', type='json', auth='public', methods=['POST'],csrf=False)
    def confirm_sale_order(self,**kwargs):
        ho_store_id = request.env['nhcl.ho.store.master'].sudo().search(
            [('nhcl_store_type', '=', 'ho'), ('nhcl_active', '=', True), ])
        store_sale_orders = request.env['sale.order'].sudo().search([('nhcl_store_delivery', '=', True),
                                                                     ('state','=','draft')])
        if store_sale_orders:
            for order in store_sale_orders:
                try:
                    if order.state == 'draft':
                        order.sudo().action_confirm()
                except Exception as e:
                    ho_store_id.create_cmr_transaction_server_replication_log("failure", e)

