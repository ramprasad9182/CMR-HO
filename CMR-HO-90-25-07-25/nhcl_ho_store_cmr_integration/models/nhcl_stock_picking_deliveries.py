import requests
from odoo import models, fields, api, _
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class Picking(models.Model):
    _inherit = 'stock.picking'

    is_replicated = fields.Boolean('Is Replicated', copy=False)

    @api.depends('move_ids_without_package.nhcl_tax_ids', 'move_ids_without_package.nhcl_price_total',
                 'nhcl_amount_total', 'nhcl_amount_untaxed')
    def _compute_nhcl_tax_totals_json(self):
        for order in self:
            order.nhcl_tax_totals_json = self.env['account.tax']._prepare_tax_totals(
                [x._convert_to_tax_base_line_dict() for x in order.move_ids_without_package],
                order.currency_id or order.company_id.currency_id,
            )

    @api.depends('move_ids_without_package.nhcl_price_total')
    def _amount_all(self):
        for order in self:
            order_lines = order.move_ids_without_package
            amount_untaxed = amount_tax = 0.00
            if order_lines:
                tax_results = self.env['account.tax']._compute_taxes([
                    line._convert_to_tax_base_line_dict()
                    for line in order_lines
                ])
                totals = tax_results['totals']
                amount_untaxed = totals.get(order.currency_id, {}).get('nhcl_amount_untaxed', 0.0)
                amount_tax = totals.get(order.currency_id, {}).get('nhcl_amount_tax', 0.0)
            order.nhcl_amount_untaxed = amount_untaxed
            order.nhcl_amount_tax = amount_tax
            order.nhcl_amount_total = order.nhcl_amount_untaxed + order.nhcl_amount_tax

    nhcl_delivery_status = fields.Boolean(string="Status")
    nhcl_pos_order = fields.Many2one('pos.order', string="POS Order", copy=False)
    nhcl_purchased_store = fields.Char(string="Purchased Store", copy=False)
    nhcl_invoice_date = fields.Date(string="Bill Date", copy=False)
    currency_id = fields.Many2one('res.currency', 'Currency', required=True, readonly=True,
                                  default=lambda self: self.env.company.currency_id.id, copy=False)
    nhcl_tax_totals_json = fields.Binary(compute='_compute_nhcl_tax_totals_json', copy=False)
    nhcl_amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all',
                                          tracking=True, copy=False)
    nhcl_amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all', copy=False)
    nhcl_amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all', copy=False)
    company_type = fields.Selection([('same', 'Same'), ('other', 'Other')], string="Company Type", copy=False)
    store_pos_order = fields.Char('Pos Order', copy=False)
    store_name = fields.Many2one('nhcl.ho.store.master', string='Store Name', copy=False)
    nhcl_credit_note_count = fields.Integer(string='CN Count')

    def get_delivery_orders(self):
        if self.partner_id:
            ho_store_id = self.env['nhcl.ho.store.master'].search(
                [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True),
                 ('nhcl_store_name', '=', self.partner_id.name)
                 ]
            )
            partner = self.partner_id.name.split('-')
            partners_id = partner[-1]
            dest = partners_id[0]
            if not ho_store_id:
                return

            store_ip = ho_store_id.nhcl_terminal_ip
            store_port = ho_store_id.nhcl_port_no
            store_api_key = ho_store_id.nhcl_api_key
            headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
            location_data = f"http://{store_ip}:{store_port}/api/stock.location/search"
            location_data_domain = [('usage', '=', "supplier")]
            location_data_dest_domain = [('name', '=', partners_id)]
            location_data_url = f"{location_data}?domain={location_data_domain}"
            location_dest_data_url = f"{location_data}?domain={location_data_dest_domain}"
            location = requests.get(location_data_url, headers=headers_source).json()
            location_dest = requests.get(location_dest_data_url, headers=headers_source).json()
            location_id = location.get("data")[0]["id"]
            location_dest_id = location_dest.get("data")[0]["id"]
            stock_picking = f"http://{store_ip}:{store_port}/api/stock.picking.type/search"
            stock_picking_domain = [('name', '=', "Receipts")]
            stock_picking_url = f"{stock_picking}?domain={stock_picking_domain}"
            stock_picking_data = requests.get(stock_picking_url, headers=headers_source).json()
            stock_picking_type = stock_picking_data.get("data")[0]["id"]
            stock_detail_lines = []
            transporter_url = f"http://{store_ip}:{store_port}/api/dev.transport.details/search"
            transporter_domain = [('nhcl_id', '=', self.transpoter_id.nhcl_id)]
            transporter_data_url = f"{transporter_url}?domain={transporter_domain}"
            transporter_data = requests.get(transporter_data_url, headers=headers_source).json()
            transporter_ids = transporter_data.get("data")
            if transporter_ids:
                transporter_id = transporter_ids[0]["id"]
            else:
                ho_store_id.create_cmr_transaction_replication_log('stock.picking', self.id, 200,
                                                                   'add', 'failure',
                                                                   f"{self.name, self.transpoter_id.name}Transporter Not found")
            transporter_route_id = False
            transporter_route_url = f"http://{store_ip}:{store_port}/api/dev.routes.details/search"
            transporter_route_domain = [('nhcl_id', '=', self.transpoter_route_id.nhcl_id)]
            transporter_route_data_url = f"{transporter_route_url}?domain={transporter_route_domain}"
            transporter_route_data = requests.get(transporter_route_data_url, headers=headers_source).json()
            transporter_route_ids = transporter_route_data.get("data")
            if transporter_route_ids:
                transporter_route_id = transporter_route_ids[0]["id"]
            else:
                ho_store_id.create_cmr_transaction_replication_log('stock.picking', self.id, 200,
                                                                   'add', 'failure',
                                                                   f"{self.name, self.transpoter_route_id.name}Transporter Routes Not found")
            for move_line in self.move_line_ids_without_package:
                product_search_url = f"http://{store_ip}:{store_port}/api/product.product/search"
                product_domain = [('barcode', '=', move_line.product_id.barcode)]
                product_store_url = f"{product_search_url}?domain={product_domain}"
                product_data = requests.get(product_store_url, headers=headers_source).json()
                product_attribute_value_search_url = f"http://{store_ip}:{store_port}/api/product.attribute.value/search"
                product_aging_line_search_url = f"http://{store_ip}:{store_port}/api/product.aging.line/search"
                product_categ_1_domain = [('nhcl_id', '=', move_line.categ_1.nhcl_id)]
                product_categ_1_store_url = f"{product_attribute_value_search_url}?domain={product_categ_1_domain}"
                product_categ_1_data = requests.get(product_categ_1_store_url, headers=headers_source).json()
                product_categ_2_domain = [('nhcl_id', '=', move_line.categ_2.nhcl_id)]
                product_categ_2_store_url = f"{product_attribute_value_search_url}?domain={product_categ_2_domain}"
                product_categ_2_data = requests.get(product_categ_2_store_url, headers=headers_source).json()
                product_categ_3_domain = [('nhcl_id', '=', move_line.categ_3.nhcl_id)]
                product_categ_3_store_url = f"{product_attribute_value_search_url}?domain={product_categ_3_domain}"
                product_categ_3_data = requests.get(product_categ_3_store_url, headers=headers_source).json()
                product_categ_4_domain = [('nhcl_id', '=', move_line.categ_4.nhcl_id)]
                product_categ_4_store_url = f"{product_attribute_value_search_url}?domain={product_categ_4_domain}"
                product_categ_4_data = requests.get(product_categ_4_store_url, headers=headers_source).json()
                product_categ_5_domain = [('nhcl_id', '=', move_line.categ_5.nhcl_id)]
                product_categ_5_store_url = f"{product_attribute_value_search_url}?domain={product_categ_5_domain}"
                product_categ_5_data = requests.get(product_categ_5_store_url, headers=headers_source).json()
                product_categ_6_domain = [('nhcl_id', '=', move_line.categ_6.nhcl_id)]
                product_categ_6_store_url = f"{product_attribute_value_search_url}?domain={product_categ_6_domain}"
                product_categ_6_data = requests.get(product_categ_6_store_url, headers=headers_source).json()
                product_categ_7_domain = [('nhcl_id', '=', move_line.categ_7.nhcl_id)]
                product_categ_7_store_url = f"{product_attribute_value_search_url}?domain={product_categ_7_domain}"
                product_categ_7_data = requests.get(product_categ_7_store_url, headers=headers_source).json()

                product_categ_8_domain = [('nhcl_id', '=', move_line.categ_8.nhcl_id)]
                product_categ_8_store_url = f"{product_attribute_value_search_url}?domain={product_categ_8_domain}"
                product_categ_8_data = requests.get(product_categ_8_store_url, headers=headers_source).json()

                product_descrip_1_domain = [('name', '=', move_line.descrip_1.name)]
                product_descrip_1_store_url = f"{product_aging_line_search_url}?domain={product_descrip_1_domain}"
                product_descrip_1_data = requests.get(product_descrip_1_store_url, headers=headers_source).json()
                product_descrip_2_domain = [('nhcl_id', '=', move_line.descrip_2.nhcl_id)]
                product_descrip_2_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_2_domain}"
                product_descrip_2_data = requests.get(product_descrip_2_store_url, headers=headers_source).json()
                product_descrip_3_domain = [('nhcl_id', '=', move_line.descrip_3.nhcl_id)]
                product_descrip_3_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_3_domain}"
                product_descrip_3_data = requests.get(product_descrip_3_store_url, headers=headers_source).json()
                product_descrip_4_domain = [('nhcl_id', '=', move_line.descrip_4.nhcl_id)]
                product_descrip_4_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_4_domain}"
                product_descrip_4_data = requests.get(product_descrip_4_store_url, headers=headers_source).json()
                product_descrip_5_domain = [('nhcl_id', '=', move_line.descrip_5.nhcl_id)]
                product_descrip_5_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_5_domain}"
                product_descrip_5_data = requests.get(product_descrip_5_store_url, headers=headers_source).json()
                product_descrip_6_domain = [('nhcl_id', '=', move_line.descrip_6.nhcl_id)]
                product_descrip_6_store_url = f"{product_attribute_value_search_url}?domain={product_descrip_6_domain}"
                product_descrip_6_data = requests.get(product_descrip_6_store_url, headers=headers_source).json()
                if not product_data.get("data"):
                    ho_store_id.create_cmr_transaction_replication_log('stock.picking', self.id, 200,
                                                                       'add', 'failure',
                                                                       f"{self.name, move_line.product_id.name}Product Not found")
                    continue
                product_name = product_data.get("data")[0]
                product_id = product_name["id"]
                product_categ_1_ids = product_categ_1_data.get("data")
                if product_categ_1_ids:
                    product_categ_1_id = product_categ_1_ids[0]["id"]
                product_categ_2_ids = product_categ_2_data.get("data")
                if product_categ_2_ids:
                    product_categ_2_id = product_categ_2_ids[0]["id"]
                product_categ_3_ids = product_categ_3_data.get("data")
                if product_categ_3_ids:
                    product_categ_3_id = product_categ_3_ids[0]["id"]
                product_categ_4_ids = product_categ_4_data.get("data")
                if product_categ_4_ids:
                    product_categ_4_id = product_categ_4_ids[0]["id"]
                product_categ_5_ids = product_categ_5_data.get("data")
                if product_categ_5_ids:
                    product_categ_5_id = product_categ_5_ids[0]["id"]
                product_categ_6_ids = product_categ_6_data.get("data")
                if product_categ_6_ids:
                    product_categ_6_id = product_categ_6_ids[0]["id"]
                product_categ_7_ids = product_categ_7_data.get("data")
                if product_categ_7_ids:
                    product_categ_7_id = product_categ_7_ids[0]["id"]
                product_categ_8_ids = product_categ_8_data.get("data")
                if product_categ_8_ids:
                    product_categ_8_id = product_categ_8_ids[0]["id"]
                product_descrip_1_id = False
                product_descrip_1_ids = product_descrip_1_data.get("data")
                if product_descrip_1_ids:
                    product_descrip_1_id = product_descrip_1_ids[0]["id"]
                else:
                    ho_store_id.create_cmr_transaction_replication_log('stock.picking', self.id, 200,
                                                                       'add', 'failure',
                                                                       f"{self.name, self.move_line_ids_without_package.descrip_1.name}Aging Not found")
                product_descrip_2_ids = product_descrip_2_data.get("data")
                if product_descrip_2_ids:
                    product_descrip_2_id = product_descrip_2_ids[0]["id"]
                product_descrip_3_ids = product_descrip_3_data.get("data")
                if product_descrip_3_ids:
                    product_descrip_3_id = product_descrip_3_ids[0]["id"]
                product_descrip_4_ids = product_descrip_4_data.get("data")
                if product_descrip_4_ids:
                    product_descrip_4_id = product_descrip_4_ids[0]["id"]
                product_descrip_5_ids = product_descrip_5_data.get("data")
                if product_descrip_5_ids:
                    product_descrip_5_id = product_descrip_5_ids[0]["id"]
                product_descrip_6_ids = product_descrip_6_data.get("data")
                if product_descrip_6_ids:
                    product_descrip_6_id = product_descrip_6_ids[0]["id"]
                mr_price = 0.0
                if move_line.mr_price:
                    mr_price = move_line.mr_price
                if move_line:
                    detail_line = {
                        'product_id': product_id,
                        'internal_ref_lot': move_line.internal_ref_lot,
                        'mr_price': mr_price,
                        'rs_price': move_line.rs_price if move_line.rs_price else 0,
                        'cost_price': move_line.cost_price if move_line.cost_price else 0,
                        'type_product': move_line.type_product,
                        'lot_name': move_line.lot_id.name,
                        'quantity': move_line.quantity,
                        'segment': move_line.segment,
                        'categ_1': product_categ_1_id if move_line.categ_1 else False,
                        'categ_2': product_categ_2_id if move_line.categ_2 else False,
                        'categ_3': product_categ_3_id if move_line.categ_3 else False,
                        'categ_4': product_categ_4_id if move_line.categ_4 else False,
                        'categ_5': product_categ_5_id if move_line.categ_5 else False,
                        'categ_6': product_categ_6_id if move_line.categ_6 else False,
                        'categ_7': product_categ_7_id if move_line.categ_7 else False,
                        'categ_8': product_categ_8_id if move_line.categ_8 else False,
                        'descrip_1': product_descrip_1_id if move_line.descrip_1 else False,
                        'descrip_2': product_descrip_2_id if move_line.descrip_2 else False,
                        'descrip_3': product_descrip_3_id if move_line.descrip_3 else False,
                        'descrip_4': product_descrip_4_id if move_line.descrip_4 else False,
                        'descrip_5': product_descrip_5_id if move_line.descrip_5 else False,
                        'descrip_6': product_descrip_6_id if move_line.descrip_6 else False,
                    }
                    stock_detail_lines.append((0, 0, detail_line))
            if stock_detail_lines:
                stock_picking_data = {
                    'partner_id': 3,
                    'picking_type_id': stock_picking_type,
                    'origin': self.name,
                    'stock_type': self.stock_type,
                    'lr_number': self.lr_number if self.lr_number else None,
                    'vehicle_number': self.vehicle_number if self.vehicle_number else None,
                    'driver_name': self.driver_name if self.driver_name else None,
                    'no_of_parcel': self.no_of_parcel if self.no_of_parcel else None,
                    'nhcl_tracking_number': self.tracking_number,
                    'transpoter_id': transporter_id if self.transpoter_id else False,
                    'transpoter_route_id': transporter_route_id if self.transpoter_route_id else False,
                    'location_id': location_id,
                    'location_dest_id': location_dest_id,
                    'move_line_ids_without_package': stock_detail_lines,
                }
                store_url_data = f"http://{store_ip}:{store_port}/api/stock.picking/create"
                try:
                    stores_data = requests.post(store_url_data, headers=headers_source, json=[stock_picking_data])
                    stores_data.raise_for_status()
                    response_json = stores_data.json()

                    message = response_json.get("message", "No message provided")
                    response_code = response_json.get("responseCode", "No response code provided")
                    if not response_json.get("success", True):
                        _logger.info(f"Failed to create stock picking: {message} from {store_ip}")
                        logging.error(f"Failed to create stock picking: {message}")
                        ho_store_id.create_cmr_transaction_server_replication_log('success', message)
                        ho_store_id.create_cmr_transaction_replication_log(response_json['object_name'], self.id, 200,
                                                                           'add', 'failure', message)
                    else:
                        self.nhcl_delivery_status = True
                        _logger.info(f"Successfully created stock picking: {message} from {store_ip}")
                        logging.info(f"Successfully created stock picking: {message}")
                        ho_store_id.create_cmr_transaction_server_replication_log('success', message)
                        ho_store_id.create_cmr_transaction_replication_log(response_json['object_name'], self.id, 200,
                                                                           'add', 'success',
                                                                           f"Successfully created stock picking: {message}")

                except requests.exceptions.RequestException as e:
                    _logger.error(
                        f"Failed to create stock picking for '{self.name}' with partner '{self.partner_id.name}'. Error: {e}")
                    logging.error(
                        f"Failed to create stock picking for '{self.name}' with partner '{self.partner_id.name}'. Error: {e}")
                    self.nhcl_delivery_status = False
                    ho_store_id.create_cmr_transaction_server_replication_log('failure', e)


class StockMove(models.Model):
    """Inherited stock.move class to add fields and functions"""
    _inherit = "stock.move"


    pos_order_lines = fields.Many2one('pos.order.line', string='pos order lines', copy=False)
    nhcl_tax_ids = fields.Many2many('account.tax', 'exng_tax', domain=[('type_tax_use', '=', 'sale'), ('active', '=', True)],
                                    string="Tax")
    nhcl_total = fields.Float(string="Total", copy=False)
    nhcl_rsp = fields.Float(string="RSP", copy=False)
    nhcl_exchange = fields.Boolean(string="Exchange", copy=False)
    nhcl_discount = fields.Float(string="Discount (%)", copy=False)
    nhcl_price_total = fields.Monetary(compute='_compute_amount', string='Total', store=True)
    nhcl_price_subtotal = fields.Monetary(compute='_compute_amount', string='Subtotal', store=True)
    nhcl_price_tax = fields.Float(compute='_compute_amount', string='Tax', store=True)
    currency_id = fields.Many2one("res.currency", string="Currency", required=True,
                                  related='picking_id.currency_id')
    ref_pos_order_line_id = fields.Integer('Pos Order Line Id', default="0", copy=False)

    @api.model
    def _prepare_merge_moves_distinct_fields(self):
        distinct_fields = super(StockMove, self)._prepare_merge_moves_distinct_fields()
        distinct_fields.append('pos_order_lines')
        distinct_fields.append('ref_pos_order_line_id')
        return distinct_fields

    @api.depends('quantity', 'nhcl_rsp', 'nhcl_tax_ids')
    def _compute_amount(self):
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes([line._convert_to_tax_base_line_dict()])
            totals = next(iter(tax_results['totals'].values()))
            amount_untaxed = totals['amount_untaxed']
            amount_tax = totals['amount_tax']
            line.update({
                'nhcl_price_subtotal': amount_untaxed,
                'nhcl_price_tax': amount_tax,
                'nhcl_price_total': amount_untaxed + amount_tax,
            })

    # updating the price unit,currency,req qty,product,partner
    def _convert_to_tax_base_line_dict(self):
        # Hook method to returns the different argument values for the
        # compute_all method, due to the fact that discounts mechanism
        # is not implemented yet on the purchase orders.
        # This method should disappear as soon as this feature is
        # also introduced like in the sales module.
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            price_unit=self.nhcl_rsp * (1 - (self.nhcl_discount or 0.0) / 100.0),
            currency=self.picking_id.currency_id,
            quantity=self.quantity,
            product=self.product_id,
            taxes=self.nhcl_tax_ids,
            partner=self.picking_id.partner_id,
            price_subtotal=self.nhcl_price_subtotal,
        )


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    nhcl_batch_status = fields.Boolean(string="Status")
    nhcl_company = fields.Many2one('nhcl.ho.store.master', string="To Store")

    def nhcl_checking_store_enabled(self):
        for rec in self:
            allowed_company_ids = self.env.context.get('allowed_company_ids', [])
            for i in rec.picking_ids:
                if i.partner_id and allowed_company_ids and self.env.user.id != 1:
                    company_exists = self.env['res.company'].sudo().search([('id', 'in', allowed_company_ids),
                                                                            ('partner_id', '=', i.partner_id.id)])
                    if not company_exists:
                        raise ValidationError(_("Please enable the related company '%s'.") % i.partner_id.name)

    def action_confirm(self):
        for i in self:
            i.nhcl_checking_store_enabled()
        res = super().action_confirm()
        for rec in self:
            company = self.env['res.company'].sudo().search([('nhcl_company_bool', '=', True)])
            if rec.picking_type_id.company_id.name == company.name:
                for line in rec.picking_ids:
                    print("fszfzsdfdzsgdg",line)
                    line.get_delivery_orders()
        return res

    def action_done(self):
        for rec in self:
            rec.nhcl_checking_store_enabled()
            res = super().action_done()
            if len(rec.picking_ids.filtered(lambda x: x.is_replicated == True)) == len(rec.picking_ids):
                rec.state = 'done'
            else:
                for line in rec.picking_ids:
                    if line.is_replicated == False:
                        line.get_delivery_orders()
                rec.get_batch_orders()
            return res

    def get_batch_orders(self):
        for each in self:
            # Extract store information
            store_ip = each.nhcl_company.nhcl_terminal_ip
            store_port = each.nhcl_company.nhcl_port_no
            store_api_key = each.nhcl_company.nhcl_api_key

            # Set up headers and endpoints
            headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
            try:
                batch = []
                stock_picking_type = False
                store_batch_url_data = f"http://{store_ip}:{store_port}/api/stock.picking.batch/search"
                store_batch_data_domain = [('name', '=', each.name)]
                response = requests.get(store_batch_url_data, headers=headers_source,
                                        params={'domain': str(store_batch_data_domain)})
                response.raise_for_status()  # Raise an exception for HTTP errors
                store_batch_data = response.json()
                # Validate batch_dest structure
                for line in each.picking_ids:
                    batch_data_url = f"http://{store_ip}:{store_port}/api/stock.picking/search"
                    batch_data_domain = [('origin', '=', line.name)]

                    # Fetch batch data
                    response = requests.get(batch_data_url, headers=headers_source,
                                            params={'domain': str(batch_data_domain)})
                    response.raise_for_status()  # Raise an exception for HTTP errors
                    batch_dest = response.json()

                    # Validate batch_dest structure
                    if not batch_dest or "data" not in batch_dest or not batch_dest.get("data"):
                        _logger.error(
                            f"No data found in API response for domain {batch_data_domain}. Response: {batch_dest}")
                        continue
                    if batch_dest.get('data'):
                        batch_id = batch_dest["data"][0]["id"]
                    else:
                        batch_id = False
                    if store_batch_data.get('data') and batch_id:
                        update_batch_data = {
                            'batch_id': store_batch_data.get('data')[0].get('id')
                        }
                        update_batch_url = f"http://{store_ip}:{store_port}/api/stock.picking/{batch_id}"
                        try:
                            response = requests.put(update_batch_url, headers=headers_source, json=update_batch_data)
                            response.raise_for_status()
                            line.is_replicated = True
                        except requests.RequestException as e:
                            print("Failed to update Batch Transfer:", e)
                            if e.response:
                                print("Response content:", e.response.content.decode())
                    else:
                        # Fetch stock picking type
                        stock_picking_url = f"http://{store_ip}:{store_port}/api/stock.picking.type/search"
                        stock_picking_domain = [('name', '=', "Receipts")]
                        stock_picking_response = requests.get(stock_picking_url, headers=headers_source,
                                                              params={'domain': str(stock_picking_domain)})
                        stock_picking_response.raise_for_status()
                        stock_picking_data = stock_picking_response.json()

                        if not stock_picking_data or "data" not in stock_picking_data or not stock_picking_data.get("data"):
                            _logger.error(
                                f"No stock picking type data found for domain {stock_picking_domain}. Response: {stock_picking_data}")
                            continue

                        stock_picking_type = stock_picking_data["data"][0]["id"]
                        if batch_id:
                            line.is_replicated =True
                        batch.append(batch_id)

                    # Prepare batch data
                if not store_batch_data.get('data'):
                    batch_data = {
                        "user_id": 2,
                        'picking_type_id': stock_picking_type,
                        'name': each.name,
                        'picking_ids': batch,
                        'delivery_count': len(each.picking_ids)
                    }
                    # Create batch
                    store_url_data = f"http://{store_ip}:{store_port}/api/stock.picking.batch/create"
                    batch_response = requests.post(store_url_data, headers=headers_source, json=[batch_data])
                    batch_response.raise_for_status()
                    response_json = batch_response.json()

                    # Log success or failure
                    message = response_json.get("message", "No message provided")
                    response_code = response_json.get("responseCode", "No response code provided")

                    if not response_json.get("success", True):
                        _logger.info(f"Failed to create stock picking: {message} from {store_ip}")
                        each.nhcl_company.create_cmr_transaction_server_replication_log('failure', message)
                        each.nhcl_company.create_cmr_transaction_replication_log(response_json.get('object_name', ''),self.id,
                                                                                 200, 'add', 'failure', message)
                    else:
                        self.nhcl_batch_status = True
                        _logger.info(f"Successfully created stock picking: {message} from {store_ip}")
                        each.nhcl_company.create_cmr_transaction_replication_log(response_json.get('object_name', ''),self.id,
                                                                                 200, 'add', 'success', message)

            except requests.exceptions.RequestException as e:
                _logger.error(
                    f"Request failed for '{each.name}' with partner '{getattr(each.name, 'name', 'Unknown')}'. Error: {e}")
                each.nhcl_company.create_cmr_transaction_server_replication_log('failure', str(e))
            except Exception as ex:
                _logger.error(f"Unexpected error occurred: {ex}")





