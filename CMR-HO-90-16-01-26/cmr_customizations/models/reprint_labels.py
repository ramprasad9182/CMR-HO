import base64
import socket
import textwrap

import requests

from odoo import models, fields, api, _
from collections import defaultdict

from odoo.exceptions import UserError
from odoo.tools import float_compare, float_is_zero


class ReprintLabels(models.Model):
    _name = 'reprint.labels'

    serial_numbers = fields.Char('Serial Number')
    name = fields.Char('Name',default='New')
    serial_number_lines = fields.One2many('serial.number.lines', 'serial_number_id')




    def cmr_reprint_labels(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reprint Dynamic Label',
            'res_model': 'reprint.dynamic.label',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_serial_number_lines': self.serial_number_lines.ids
            }
        }

    @api.onchange('serial_numbers')
    def _onchange_serial_number_lines(self):
        lot = self.env['stock.lot'].search([('name', '=', self.serial_numbers)], limit=1)
        if lot:
            vals = {
                'name': lot.name,
                'product_id': lot.product_id.id,
                'lot_id': lot.id,
                'internal_ref': lot.ref,
                'qty': 1,

                # Categories
                'category_1': lot.category_1.id if lot.category_1 else False,
                'category_2': lot.category_2.id if lot.category_2 else False,
                'category_3': lot.category_3.id if lot.category_3 else False,
                'category_4': lot.category_4.id if lot.category_4 else False,
                'category_5': lot.category_5.id if lot.category_5 else False,
                'category_6': lot.category_6.id if lot.category_6 else False,
                'category_7': lot.category_7.id if lot.category_7 else False,
                'category_8': lot.category_8.id if lot.category_8 else False,

                # Descriptions
                'description_1': lot.description_1.id if lot.description_1 else False,
                'description_2': lot.description_2.id if lot.description_2 else False,
                'description_3': lot.description_3.id if lot.description_3 else False,
                'description_4': lot.description_4.id if lot.description_4 else False,
                'description_5': lot.description_5.id if lot.description_5 else False,
                'description_6': lot.description_6.id if lot.description_6 else False,
                'description_7': lot.description_7.id if lot.description_7 else False,
                'description_8': lot.description_8.id if lot.description_8 else False,
                'description_9': lot.description_9.id if lot.description_9 else False,

                # Other fields
                'product_description': lot.product_description or '',
                'web_product': lot.web_product or '',
                'cost_price': lot.cost_price or 0.0,
                'actual_cp': lot.actual_cp or 0.0,
                'mr_price': lot.mr_price or 0.0,
                'rs_price': lot.rs_price or 0.0,
            }

            self.serial_number_lines = [(0, 0, vals)]
        self.serial_numbers = False




class SerialNumberLines(models.Model):
    _name = 'serial.number.lines'

    name = fields.Char('Lot')
    lot_id = fields.Many2one('stock.lot', string='Lot ID')
    product_id = fields.Many2one('product.product', 'Product')
    internal_ref = fields.Char('Internal Reference')
    serial_number_id = fields.Many2one('reprint.labels', 'Reprint')
    qty = fields.Float('Quantity')
    move_line = fields.Many2one('stock.move.line', string='Move Line')

    # Categories
    category_1 = fields.Many2one('product.attribute.value', string='Color')
    category_2 = fields.Many2one('product.attribute.value', string='Fit')
    category_3 = fields.Many2one('product.attribute.value', string='Brand')
    category_4 = fields.Many2one('product.attribute.value', string='Pattern')
    category_5 = fields.Many2one('product.attribute.value', string='Border Type')
    category_6 = fields.Many2one('product.attribute.value', string='Border Size')
    category_7 = fields.Many2one('product.attribute.value', string='Size')
    category_8 = fields.Many2one('product.attribute.value', string='Design')

    # Descriptions
    description_1 = fields.Many2one('product.aging.line', string="Product Aging")
    description_2 = fields.Many2one('product.attribute.value', string='Range')
    description_3 = fields.Many2one('product.attribute.value', string='Collection')
    description_4 = fields.Many2one('product.attribute.value', string='Fabric')
    description_5 = fields.Many2one('product.attribute.value', string='Exclusive')
    description_6 = fields.Many2one('product.attribute.value', string='Print')
    description_7 = fields.Many2one('product.attribute.value', string='Days Ageing')
    description_8 = fields.Many2one('product.attribute.value', string='Offer')
    description_9 = fields.Many2one('product.attribute.value', string='Discount')

    # Pricing / Additional fields
    product_description = fields.Html(string="Product Description")
    web_product = fields.Char(string="Website Product Name")
    cost_price = fields.Float(string='CP')
    actual_cp = fields.Float(string='Actual CP')
    mr_price = fields.Float(string='MRP')
    rs_price = fields.Float(string='RSP')


class ProductLabelLayout(models.TransientModel):
    _inherit = 'picking.label.type'

    reprint_label_ids = fields.Many2many('reprint.labels', string='Reprint Labels')

    def process(self):
        if self.reprint_label_ids:
            return self.reprint_label_ids.action_open_label_layout()
        if not self.picking_ids:
            return
        if self.label_type == 'products':
            return self.picking_ids.action_open_label_layout()
        view = self.env.ref('stock.lot_label_layout_form_picking')
        return {
            'name': _('Choose Labels Layout'),
            'type': 'ir.actions.act_window',
            'res_model': 'lot.label.layout',
            'views': [(view.id, 'form')],
            'target': 'new',
            'context': {'default_move_line_ids': self.picking_ids.move_line_ids.ids},
        }


class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    serial_number_lines = fields.Many2many('serial.number.lines', string='Serial No Labels')

    # naseer
    def _prepare_report_data(self):
        xml_id, data = super()._prepare_report_data()

        if 'zpl' in self.print_format:
            xml_id = 'stock.label_product_product'

        quantities = defaultdict(int)
        uom_unit = self.env.ref('uom.product_uom_categ_unit', raise_if_not_found=False)
        if self.move_quantity == 'move' and self.move_ids and all(float_is_zero(ml.quantity, precision_rounding=ml.product_uom_id.rounding) for ml in self.move_ids.move_line_ids):
            for move in self.move_ids:
                if move.product_uom.category_id == uom_unit:
                    use_reserved = float_compare(move.quantity, 0, precision_rounding=move.product_uom.rounding) > 0
                    useable_qty = move.quantity if use_reserved else move.product_uom_qty
                    if not float_is_zero(useable_qty, precision_rounding=move.product_uom.rounding):
                        quantities[move.product_id.id] += useable_qty
            data['quantity_by_product'] = {p: int(q) for p, q in quantities.items()}
        elif self.move_quantity == 'move' and self.move_ids.move_line_ids:
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
        elif self.serial_number_lines:
            custom_barcodes = defaultdict(list)
            for line in self.serial_number_lines.move_line:
                if line.product_uom_id.category_id == uom_unit:
                    if (line.lot_id or line.lot_name) and int(line.quantity):
                        name = "01" + str(line.product_id.barcode) + "21" + line.lot_name
                        custom_barcodes[line.product_id.id].append(
                            (name, int(line.quantity)))
                        continue
                    quantities[line.product_id.id] += line.quantity
                else:
                    quantities[line.product_id.id] = 1
            # Pass only products with some quantity done to the report
            data['quantity_by_product'] = {p: int(q) for p, q in quantities.items() if q}
            data['custom_barcodes'] = custom_barcodes
        return xml_id, data
