from odoo import models, fields, api, _
from collections import defaultdict
from odoo.tools import float_compare, float_is_zero


class ReprintLabels(models.Model):
    _name = 'reprint.labels'

    serial_numbers = fields.Char('Serial Number')
    name = fields.Char('Name',default='New')
    serial_number_lines = fields.One2many('serial.number.lines', 'serial_number_id')

    def action_print_labels(self):
        if self.user_has_groups('stock.group_production_lot'):
            view = self.env.ref('stock.picking_label_type_form')
            return {
                'name': _('Choose Type of Labels To Print'),
                'type': 'ir.actions.act_window',
                'res_model': 'picking.label.type',
                'views': [(view.id, 'form')],
                'target': 'new',
                'context': {'default_reprint_label_ids': self.ids},
            }
        return self.action_open_label_layout()

    @api.onchange('serial_numbers')
    def _onchange_serial_number_lines(self):
        lot = self.env['stock.lot'].search([('name', '=', self.serial_numbers)])
        move_line = self.env['stock.move.line'].search([('lot_name', '=', self.serial_numbers)])
        if lot:
            line_data = []
            vals = {
                'name': lot.name,
                'product_id': lot.product_id.id,
                'lot_id': lot.id,
                'internal_ref': lot.ref,
                'qty': 1,
                'move_line': move_line.id
            }
            line_data.append((0, 0, vals))

            self.serial_number_lines = line_data
        self.serial_numbers = False

    def action_open_label_layout(self):
        view = self.env.ref('stock.product_label_layout_form_picking')
        return {
            'name': _('Choose Labels Layout'),
            'type': 'ir.actions.act_window',
            'res_model': 'product.label.layout',
            'views': [(view.id, 'form')],
            'target': 'new',
            'context': {
                'default_product_ids': self.serial_number_lines.product_id.ids,
                'default_move_line_ids': self.serial_number_lines.move_line.ids,
                'default_serial_number_lines': self.serial_number_lines.ids,
                'default_move_quantity': 'move'
            },
        }


class SerialNumberLines(models.Model):
    _name = 'serial.number.lines'

    name = fields.Char('Lot')
    lot_id = fields.Many2one('stock.lot', string='Lot ID')
    product_id = fields.Many2one('product.product', 'Product')
    internal_ref = fields.Char('Internal Reference')
    serial_number_id = fields.Many2one('reprint.labels', 'Reprint')
    qty = fields.Float('Quantity')
    move_line = fields.Many2one('stock.move.line', string='Move Line')


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
