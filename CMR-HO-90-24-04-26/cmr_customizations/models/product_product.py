import random
from collections import defaultdict
from odoo import api, models,fields
from odoo.tools import get_barcode_check_digit
import logging
_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    """Inherit product_product model for adding EAN13 Standard Barcode"""
    _inherit = 'product.product'

    vendor_qty = fields.Float(string="Received Qty", compute="_compute_vendor_qty", store=False)
    vendor_returned_qty = fields.Float(string="Vendor Returned Qty", compute="_compute_vendor_returned_qty", store=False)
    delivered_qty = fields.Float(string="Delivered Qty", compute="_compute_delivered_qty", store=False)
    customer_returned_qty = fields.Float(string="Customer Returned Qty", compute="_compute_customer_returned_qty",
                                        store=False)
    pos_delv_qty = fields.Float(string="PoS Delivered Qty", compute="_compute_pos_delv_qty", store=False)
    pos_exchange_qty = fields.Float(string="POS Exchange Qty", compute='_compute_pos_exchange_qty', store=False)
    serial_no = fields.Char(string="Serial No")
    family_categ_id = fields.Many2one('product.category', compute="_compute_category_levels", string="Division", store=True)
    class_categ_id = fields.Many2one('product.category', compute="_compute_category_levels", string="Section", store=True)
    brick_categ_id = fields.Many2one('product.category', compute="_compute_category_levels", string="Department", store=True)
    category_name_id = fields.Many2one('product.category', string='Brick', related='categ_id', store=True)
    last_purchase_cost = fields.Float(
        string="Last Purchase Cost",
        compute="_compute_last_purchase_cost",
        store=False
    )

    @api.depends('categ_id')
    def _compute_category_levels(self):
        for rec in self:
            parent1 = rec.categ_id.parent_id
            parent2 = parent1.parent_id if parent1 else False
            parent3 = parent2.parent_id if parent2 else False
            rec.brick_categ_id = parent1
            rec.class_categ_id = parent2
            rec.family_categ_id = parent3

    def _compute_last_purchase_cost(self):
        for product in self:
            # Step 1: latest confirmed PO for this product
            po = self.env['purchase.order'].search([
                ('state', 'in', ['purchase', 'done']),
                ('partner_id.name', 'not ilike', 'CMR%'),
                ('order_line.product_id', '=', product.id),
            ], order='date_approve desc', limit=1)

            if po:
                # Step 2: get that product line price
                line = po.order_line.filtered(
                    lambda l: l.product_id.id == product.id
                )[:1]
                product.last_purchase_cost = line.price_unit if line else 0.0
            else:
                product.last_purchase_cost = 0.0


    @api.depends('categ_id')
    def _compute_category_abbr(self):
        for product in self:
            if product.categ_id:
                product.category_abbr = self._get_category_abbr(product.categ_id.display_name)
                category = product.category_name_id
                print(product.category_name_id)
                if category:
                    if category.parent_id:
                        product.brick_categ_id = category.parent_id
                        print(product.brick_categ_id)
                        if category.parent_id.parent_id:
                            product.class_categ_id = category.parent_id.parent_id
                            print(product.class_categ_id)
                            if category.parent_id.parent_id.parent_id:
                                product.family_categ_id = category.parent_id.parent_id.parent_id
                                print(product.family_categ_id)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Apply EAN generation
        for rec in records:
            rec.generate_ean()
        return records

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        res = super().read_group(domain, fields, groupby, offset, limit, orderby, lazy)

        # Only run custom logic if at least one of the fields is requested
        target_fields = [
            'avg_cost',
            'total_value',
            'qty_available',
            'free_qty',
            'incoming_qty',
            'vendor_qty',
            'delivered_qty',
            'vendor_returned_qty',
            'customer_returned_qty',
            'pos_delv_qty',
            'pos_exchange_qty',
            'outgoing_qty',
        ]
        active_fields = [f for f in target_fields if f in fields]

        if not active_fields:
            return res

        # Search all products in domain
        all_products = self.search(domain)

        # Read groupby fields + all required sum fields
        read_fields = groupby + active_fields
        data = all_products.read(read_fields)

        group_key = groupby[0].split(':')[0]

        # Dictionary: { field_name : { group_value : sum } }
        grouped_map = {f: {} for f in active_fields}

        # Build mapping
        for rec in data:
            key_val = rec[group_key]
            if isinstance(key_val, tuple):
                key_val = key_val[0]

            for field in active_fields:
                val = rec.get(field, 0) or 0
                grouped_map[field].setdefault(key_val, 0)
                grouped_map[field][key_val] += val

        # Fill aggregated values back into result rows
        for row in res:
            key = row.get(group_key)
            if isinstance(key, tuple):
                key = key[0]

            for field in active_fields:
                row[field] = grouped_map[field].get(key, 0)

        return res

    ################################################################################################################################################
    @api.depends_context('warehouse')
    def _compute_vendor_qty(self):
        if not self:
            return

        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']

        # Get warehouse ids from context
        warehouse_ids = self.env.context.get('warehouse')
        if warehouse_ids:
            if not isinstance(warehouse_ids, list):
                warehouse_ids = [warehouse_ids]
        else:
            warehouse_ids = self.env['stock.warehouse'].search([]).ids

        # Get incoming picking types only once
        receipt_type_ids = PickingType.search([
            ('stock_picking_type', '=', 'receipt'),
            ('warehouse_id', 'in', warehouse_ids)
        ]).ids

        # Initialize default value in batch
        self.update({'vendor_qty': 0.0})

        if not receipt_type_ids:
            return

        # Aggregate in ONE query for all 50k products
        grouped_moves = StockMove.read_group(
            domain=[
                ('product_id', 'in', self.ids),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', receipt_type_ids),
            ],
            fields=['product_id', 'product_uom_qty:sum'],
            groupby=['product_id'],
            lazy=False,
        )
        # Convert result to dictionary (O(1) lookup)
        qty_map = {
            data['product_id'][0]: data['product_uom_qty']
            for data in grouped_moves
            if data['product_id']
        }
        # Assign in memory (no extra queries)
        for product in self:
            product.vendor_qty = qty_map.get(product.id, 0.0)

    @api.depends_context('warehouse')
    def _compute_delivered_qty(self):
        if not self:
            return

        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']

        # Get warehouse ids from context
        warehouse_ids = self.env.context.get('warehouse')
        if warehouse_ids:
            if not isinstance(warehouse_ids, list):
                warehouse_ids = [warehouse_ids]
        else:
            warehouse_ids = self.env['stock.warehouse'].search([]).ids

        # Get incoming picking types only once
        delivery_type_ids = PickingType.search([
            ('stock_picking_type', 'in', ['delivery', 'regular']),
            ('warehouse_id', 'in', warehouse_ids)
        ]).ids

        # Initialize default value in batch
        self.update({'delivered_qty': 0.0})
        if not delivery_type_ids:
            return
        # Aggregate in ONE query for all 50k products
        grouped_moves = StockMove.read_group(
            domain=[
                ('product_id', 'in', self.ids),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', delivery_type_ids),
            ],
            fields=['product_id', 'product_uom_qty:sum'],
            groupby=['product_id'],
            lazy=False,
        )
        # Convert result to dictionary (O(1) lookup)
        qty_map = {
            data['product_id'][0]: data['product_uom_qty']
            for data in grouped_moves
            if data['product_id']
        }
        # Assign in memory (no extra queries)
        for product in self:
            product.delivered_qty = qty_map.get(product.id, 0.0)

    @api.depends_context('warehouse')
    def _compute_vendor_returned_qty(self):
        if not self:
            return
        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']
        # Get warehouse ids from context
        warehouse_ids = self.env['stock.warehouse'].search([('company_id.nhcl_company_bool', '=', True)]).ids
        # Get incoming picking types only once
        vendor_return_type_ids = PickingType.search([
            ('stock_picking_type', 'in', ['goods_return']),
            ('warehouse_id', 'in', warehouse_ids)
        ]).ids
        # Initialize default value in batch
        self.update({'vendor_returned_qty': 0.0})
        if not vendor_return_type_ids:
            return
        # Aggregate in ONE query for all 50k products
        grouped_moves = StockMove.read_group(
            domain=[
                ('product_id', 'in', self.ids),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', vendor_return_type_ids),
            ],
            fields=['product_id', 'product_uom_qty:sum'],
            groupby=['product_id'],
            lazy=False,
        )
        # Convert result to dictionary (O(1) lookup)
        qty_map = {
            data['product_id'][0]: data['product_uom_qty']
            for data in grouped_moves
            if data['product_id']
        }
        # Assign in memory (no extra queries)
        for product in self:
            product.vendor_returned_qty = qty_map.get(product.id, 0.0)

    @api.depends_context('warehouse')
    def _compute_customer_returned_qty(self):
        if not self:
            return
        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']
        # Get warehouse ids from context
        warehouse_ids = self.env['stock.warehouse'].search([('company_id.nhcl_company_bool', '=', False)]).ids
        # Get incoming picking types only once
        customer_return_type_ids = PickingType.search([
            ('stock_picking_type', 'in', ['return']),
            ('warehouse_id', 'in', warehouse_ids)
        ]).ids
        # Initialize default value in batch
        self.update({'customer_returned_qty': 0.0})
        if not customer_return_type_ids:
            return
        # Aggregate in ONE query for all 50k products
        grouped_moves = StockMove.read_group(
            domain=[
                ('product_id', 'in', self.ids),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', customer_return_type_ids),
            ],
            fields=['product_id', 'product_uom_qty:sum'],
            groupby=['product_id'],
            lazy=False,
        )
        # Convert result to dictionary (O(1) lookup)
        qty_map = {
            data['product_id'][0]: data['product_uom_qty']
            for data in grouped_moves
            if data['product_id']
        }
        # Assign in memory (no extra queries)
        for product in self:
            product.customer_returned_qty = qty_map.get(product.id, 0.0)

    @api.depends_context('warehouse')
    def _compute_pos_delv_qty(self):
        if not self:
            return
        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']
        # Get warehouse ids from context
        warehouse_ids = self.env.context.get('warehouse')
        if warehouse_ids:
            if not isinstance(warehouse_ids, list):
                warehouse_ids = [warehouse_ids]
        else:
            warehouse_ids = self.env['stock.warehouse'].search([]).ids
        # Get incoming picking types only once
        pos_delivery_type_ids = PickingType.search([
            ('stock_picking_type', 'in', ['return']),
            ('warehouse_id', 'in', warehouse_ids)
        ]).ids
        # Initialize default value in batch
        self.update({'pos_delv_qty': 0.0})
        if not pos_delivery_type_ids:
            return
        # Aggregate in ONE query for all 50k products
        grouped_moves = StockMove.read_group(
            domain=[
                ('product_id', 'in', self.ids),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', pos_delivery_type_ids),
            ],
            fields=['product_id', 'product_uom_qty:sum'],
            groupby=['product_id'],
            lazy=False,
        )
        # Convert result to dictionary (O(1) lookup)
        qty_map = {
            data['product_id'][0]: data['product_uom_qty']
            for data in grouped_moves
            if data['product_id']
        }
        # Assign in memory (no extra queries)
        for product in self:
            product.pos_delv_qty = qty_map.get(product.id, 0.0)

    @api.depends_context('warehouse')
    def _compute_pos_exchange_qty(self):
        if not self:
            return

        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']

        # Get warehouse ids from context
        warehouse_ids = self.env['stock.warehouse'].search([]).ids
        # Get incoming picking types only once
        pos_exchange_type_ids = PickingType.search([
            ('stock_picking_type', '=', 'exchange'),
            ('warehouse_id', 'in', warehouse_ids)
        ]).ids

        # Initialize default value in batch
        self.update({'pos_exchange_qty': 0.0})

        if not pos_exchange_type_ids:
            return

        # Aggregate in ONE query for all 50k products
        grouped_moves = StockMove.read_group(
            domain=[
                ('product_id', 'in', self.ids),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', pos_exchange_type_ids),
            ],
            fields=['product_id', 'product_uom_qty:sum'],
            groupby=['product_id'],
            lazy=False,
        )
        # Convert result to dictionary (O(1) lookup)
        qty_map = {
            data['product_id'][0]: data['product_uom_qty']
            for data in grouped_moves
            if data['product_id']
        }
        # Assign in memory (no extra queries)
        for product in self:
            product.pos_exchange_qty = qty_map.get(product.id, 0.0)

    def get_rsp_price(self, barcode):
        barcode_lst = barcode.split('R')
        if len(barcode_lst) > 1:
            lot_id = self.env['stock.lot'].search([('name', '=', 'R'+barcode_lst[1]), ('company_id','=',self.env.user.company_id.id)],limit=1)
            if lot_id:
                return lot_id.rs_price
            else:
                return 0
        else:
            return 0

    def get_mrp_price(self, barcode):
        barcode_lst = barcode.split('R')
        if len(barcode_lst) > 1:
            lot_id = self.env['stock.lot'].search([('name', '=', 'R'+barcode_lst[1]), ('company_id','=',self.env.user.company_id.id)],limit=1)
            if lot_id:
                return lot_id.mr_price
            else:
                return 0
        else:
            return 0

    def get_color(self, barcode):
        barcode_lst = barcode.split('R')
        if len(barcode_lst) > 1:
            lot_id = self.env['stock.lot'].search([('name', '=', 'R' + barcode_lst[1]), ('company_id','=',self.env.user.company_id.id)],limit=1)
            if lot_id:
                return lot_id.category_1
            else:
                return False
        else:
            return False



    def get_size(self, barcode):
        barcode_lst = barcode.split('R')
        if len(barcode_lst) > 1:
            lot_id = self.env['stock.lot'].search([('name', '=', 'R' + barcode_lst[1]), ('company_id','=',self.env.user.company_id.id)],limit=1)
            if lot_id:
                return lot_id.category_7
            else:
                return False
        else:
            return False

    def get_aging(self, barcode):
        barcode_lst = barcode.split('R')
        if len(barcode_lst) > 1:
            lot_id = self.env['stock.lot'].search([('name', '=', 'R' + barcode_lst[1]), ('company_id','=',self.env.user.company_id.id)],limit=1)
            if lot_id:
                return lot_id.description_1
            else:
                return False
        else:
            return False


    def get_brand(self, barcode):
        barcode_lst = barcode.split('R')
        if len(barcode_lst) > 1:
            lot_id = self.env['stock.lot'].search([('name', '=', 'R' + barcode_lst[1]), ('company_id','=',self.env.user.company_id.id)],limit=1)
            if lot_id:
                return lot_id.category_3
            else:
                return False
        else:
            return False

    def get_fit(self, barcode):
        barcode_lst = barcode.split('R')
        if len(barcode_lst) > 1:
            lot_id = self.env['stock.lot'].search([('name', '=', 'R' + barcode_lst[1]), ('company_id','=',self.env.user.company_id.id)],limit=1)
            if lot_id:
                return lot_id.category_2
            else:
                return False
        else:
            return False

    def get_offer(self, barcode):
        barcode_lst = barcode.split('R')
        if len(barcode_lst) > 1:
            lot_id = self.env['stock.lot'].search([('name', '=', 'R' + barcode_lst[1]), ('company_id','=',self.env.user.company_id.id)],limit=1)
            if lot_id:
                return lot_id.description_8
            else:
                return False
        else:
            return False

    def generate_ean(self):
        number_random = str("%0.13d" % random.randint(0, 9999999999999))
        # barcode_nomenclature = self.env['barcode.nomenclature'].browse(self.env.ref('barcodes_gs1_nomenclature.default_gs1_nomenclature'))
        # res = barcode_nomenclature.gs1_decompose_extanded(number_random)


        # gs1_nomenclature_id = self.env['barcode.nomenclature'].search([('is_gs1_nomenclature','=',True)])
        # barcode_str = gs1_nomenclature_id.rule_ids.filtered(lambda x:x.name == "Global Trade Item Number (GTIN)")
        barcode_str = self.env['barcode.nomenclature'].sanitize_ean("%s" % (number_random))
        if self.barcode:
            if len(self.barcode) != 14:
                self.barcode = barcode_str
        else:
            self.barcode = barcode_str


class BarcodeNomenclature(models.Model):
    _inherit = 'barcode.nomenclature'

    @api.model
    def sanitize_ean(self, ean):
        """ Returns a valid zero padded EAN-13 from an EAN prefix.

        :type ean: str
        """
        ean = ean[0:14].zfill(14)
        return ean[0:-1] + str(get_barcode_check_digit(ean))


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    # naseer
    def _prepare_report_data(self):
        xml_id, data = super()._prepare_report_data()
        if data.get('custom_barcodes'):
            custom_barcodes = defaultdict(list)
            for move in self.move_ids:
                if move.type_product == 'un_brand':
                    for line in move.move_line_ids:
                        if line.lot_id.product_qty >= 1:
                            if not line.lot_id:
                                lot_name = line.lot_name
                            else:
                                lot_name = line.lot_id.name
                            name = "01" + str(line.product_id.barcode) + "21" + lot_name
                            custom_barcodes[move.product_id.id].append((name, int(line.quantity)))
            data['custom_barcodes'] = custom_barcodes
        return xml_id, data

    # def _prepare_report_data(self):
    #     xml_id, data = super()._prepare_report_data()
    #     if data.get('custom_barcodes'):
    #         custom_barcodes = defaultdict(list)
    #         for line in self.move_ids.move_line_ids:
    #             # if line.product_id.barcode != False:
    #             lot_name = line.lot_id.name or line.lot_name
    #             name = "01" + str(line.product_id.barcode) + "21" + lot_name
    #             custom_barcodes[line.product_id.id].append((name, int(line.quantity)))
    #             continue
    #         data['custom_barcodes'] = custom_barcodes
    #     return xml_id, data

    # class Alias(models.Model):
    #     _inherit = 'mail.alias'
    #
    #     display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
