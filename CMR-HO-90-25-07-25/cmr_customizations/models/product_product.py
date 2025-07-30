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


################################################################################################################################################
    @api.depends_context('warehouse')
    def _compute_vendor_qty(self):
        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']
        PartnerCategory = self.env['res.partner.category']

        # Get 'Vendor' category record
        vendor_category = PartnerCategory.search([('name', '=', 'Vendor')], limit=1)

        # Get selected warehouses from context (checkbox or left filter)
        warehouse_ids = self.env.context.get('warehouse')
        if warehouse_ids:
            if not isinstance(warehouse_ids, list):
                warehouse_ids = [warehouse_ids]
        else:
            warehouse_ids = self.env['stock.warehouse'].search([]).ids

        # Get 'Receipts' picking types for selected warehouses
        receipts_types = PickingType.search([
            ('name', '=', 'Receipts'),
            ('warehouse_id', 'in', warehouse_ids)
        ])

        for product in self:
            domain = [
                ('product_id', '=', product.id),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', receipts_types.ids),
                '|',
                ('picking_id.partner_id.group_contact', '=', False),
                ('picking_id.partner_id.group_contact', '=', vendor_category.id),
            ]
            moves = StockMove.search(domain)
            product.vendor_qty = sum(moves.mapped('product_uom_qty'))


    @api.depends_context('warehouse')
    def _compute_delivered_qty(self):
        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']

        # Get selected warehouse(s) from context filter or all if not set
        warehouse_ids = self.env.context.get('warehouse')
        if warehouse_ids:
            if not isinstance(warehouse_ids, list):
                warehouse_ids = [warehouse_ids]
        else:
            warehouse_ids = self.env['stock.warehouse'].search([]).ids

        # Get 'Delivery Orders' picking types for selected warehouses
        delivery_types = PickingType.search([
            ('name', 'ilike', 'Delivery Orders'),
            ('warehouse_id', 'in', warehouse_ids)
        ])

        for product in self:
            domain = [
                ('product_id', '=', product.id),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', delivery_types.ids),
            ]
            moves = StockMove.search(domain)
            product.delivered_qty = sum(moves.mapped('product_uom_qty'))


    @api.depends_context('warehouse')
    def _compute_vendor_returned_qty(self):
        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']

        # Get warehouse IDs from context or all warehouses
        warehouse_ids = self.env.context.get('warehouse')
        if warehouse_ids:
            if not isinstance(warehouse_ids, list):
                warehouse_ids = [warehouse_ids]
        else:
            warehouse_ids = self.env['stock.warehouse'].search([]).ids

        # Get picking types like 'Goods Return' for selected warehouses
        return_types = PickingType.search([
            ('name', 'ilike', 'Goods Return'),
            ('warehouse_id', 'in', warehouse_ids)
        ])

        for product in self:
            domain = [
                ('product_id', '=', product.id),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', return_types.ids),
            ]
            moves = StockMove.search(domain)
            product.vendor_returned_qty = sum(moves.mapped('product_uom_qty'))


    @api.depends_context('warehouse')
    def _compute_customer_returned_qty(self):
        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']
        PartnerCategory = self.env['res.partner.category']

        # Get 'Customer' partner tag
        customer_category = PartnerCategory.search([('name', '=', 'Customer')], limit=1)

        # Get warehouse(s) from context or fallback to all
        warehouse_ids = self.env.context.get('warehouse')
        if warehouse_ids:
            if not isinstance(warehouse_ids, list):
                warehouse_ids = [warehouse_ids]
        else:
            warehouse_ids = self.env['stock.warehouse'].search([]).ids

        # Fetch 'Receipts' picking types linked to filtered warehouses
        receipts_types = PickingType.search([
            ('name', 'ilike', 'Receipts'),
            ('warehouse_id', 'in', warehouse_ids)
        ])

        for product in self:
            domain = [
                ('product_id', '=', product.id),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', receipts_types.ids),
                ('picking_id.partner_id.category_id', 'in', customer_category.ids),
            ]
            moves = StockMove.search(domain)
            product.customer_returned_qty = sum(moves.mapped('product_uom_qty'))


    @api.depends_context('warehouse')
    def _compute_pos_delv_qty(self):
        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']

        # Get warehouse(s) from context (left-side filter) or all
        warehouse_ids = self.env.context.get('warehouse')
        if warehouse_ids:
            if not isinstance(warehouse_ids, list):
                warehouse_ids = [warehouse_ids]
        else:
            warehouse_ids = self.env['stock.warehouse'].search([]).ids

        # Fetch picking types for PoS Orders related to those warehouses
        pos_picking_types = PickingType.search([
            ('name', 'ilike', 'PoS Orders'),
            ('warehouse_id', 'in', warehouse_ids)
        ])

        for product in self:
            domain = [
                ('product_id', '=', product.id),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', pos_picking_types.ids),
            ]
            moves = StockMove.search(domain)
            product.pos_delv_qty = sum(moves.mapped('quantity'))


    @api.depends_context('warehouse')
    def _compute_pos_exchange_qty(self):
        StockMove = self.env['stock.move']
        PickingType = self.env['stock.picking.type']

        # Get warehouse ID from context (from filter)
        warehouse_ids = self.env.context.get('warehouse')
        if warehouse_ids:
            if not isinstance(warehouse_ids, list):
                warehouse_ids = [warehouse_ids]
        else:
            warehouse_ids = self.env['stock.warehouse'].search([]).ids

        # Get picking types with name like 'Product Exchange - POS' and warehouse match
        exchange_picking_types = PickingType.search([
            ('name', 'ilike', 'Product Exchange - POS'),
            ('warehouse_id', 'in', warehouse_ids)
        ])

        for product in self:
            domain = [
                ('product_id', '=', product.id),
                ('state', '=', 'done'),
                ('picking_id.picking_type_id', 'in', exchange_picking_types.ids),
            ]
            moves = StockMove.search(domain)
            product.pos_exchange_qty = sum(moves.mapped('quantity'))

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
        print("get color called")
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
            print("data",data.get('custom_barcodes'))
            custom_barcodes = defaultdict(list)
            print("custom_barcodes",custom_barcodes)
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
