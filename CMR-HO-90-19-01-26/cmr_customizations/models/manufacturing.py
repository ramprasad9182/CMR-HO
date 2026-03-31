import base64
import csv

import openpyxl
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import io
import re
import logging

_logger = logging.getLogger(__name__)


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    allow_import_order = fields.Boolean('Allow Import', compute='_compute_import_bom_lines')

    def _compute_import_bom_lines(self):
        if self.env.user and self.env.user.import_bom_line == True:
            self.allow_import_order = True
        else:
            self.allow_import_order = False

    @api.onchange('product_tmpl_id')
    def _onchange_fun_import_bom_lines(self):
        self._compute_import_bom_lines()


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    allow_import_order = fields.Boolean('Allow Import', compute='_compute_import_prod_lines')
    nhcl_last_serial_number = fields.Char('Last Serial Number', compute='_compute_last_serial_number_mrp', store=True)
    scan_or_import = fields.Selection([
        ('scan', 'Scan'),
        ('import', 'Import')
    ], string="Scan or Import", default='scan')
    stock_barcode = fields.Char(string='Barcode Scan')
    entered_qty = fields.Float("Entered Quantity")

    def action_confirm(self):
        """Override action_confirm to prevent automatic serial number assignment for components."""
        res = super().action_confirm()

        for production in self:
            for move in production.move_raw_ids:
                # Remove any automatically assigned serial numbers
                move.move_line_ids.filtered(lambda ml: ml.lot_id).unlink()

        return res


    def _compute_last_serial_number_mrp(self):
        for record in self:
            # If we already have the serial number, do not overwrite
            if not record.nhcl_last_serial_number:
                last_lot = self.env['nhcl.master.sequence'].search([
                    ('nhcl_code', '=', 'Auto Serial Number'),
                    ('nhcl_active', '=', True)
                ], limit=1)
                if last_lot:
                    record.nhcl_last_serial_number = f"R{last_lot.nhcl_next_number - 1}"
                else:
                    record.nhcl_last_serial_number = 'R'

    @api.model
    def create(self, vals):
        """ Override the create method to set the initial nhcl_last_serial_number when creating a new manufacturing order """
        res = super(MrpProduction, self).create(vals)

        # Fetch the current nhcl_last_serial_number from sequence master only if not set
        master_seq = self.env['nhcl.master.sequence'].search([
            ('nhcl_code', '=', 'Auto Serial Number'),
            ('nhcl_active', '=', True)
        ], limit=1)

        if master_seq:
            res.nhcl_last_serial_number = f"R{master_seq.nhcl_next_number - 1}"

        return res

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """ Update the last serial number when product is changed. """
        for record in self:
            master_seq = self.env['nhcl.master.sequence'].search([
                ('nhcl_code', '=', 'Auto Serial Number'),
                ('nhcl_active', '=', True)
            ], limit=1)

            if master_seq:
                record.nhcl_last_serial_number = f"R{master_seq.nhcl_next_number - 1}"


    def write(self, vals):
        """
        1. Prevent updating nhcl_last_serial_number directly when other fields are updated.
        2. Update final product CP & RSP when MO is marked as 'done'.
        """
        update_final_product = 'state' in vals and vals['state'] == 'done'
        res = super(MrpProduction, self).write(vals)
        # After write, update final product CP & RSP if state changed to 'done'
        if update_final_product:
            for mo in self:
                mo._update_final_product_cp_rsp()
        return res

    # def _update_final_product_cp_rsp(self):
    #     """ Calculate total CP and RSP from all components across backorders. """
    #     total_cp = sum(lot.cost_price or 0 for move in self.move_raw_ids for lot in move.lot_ids)
    #     total_rsp = sum(lot.rs_price or 0 for move in self.move_raw_ids for lot in move.lot_ids)
    #
    #     # Get all serial numbers linked to this MO (including backorders)
    #     final_product_lots = self.env['stock.lot'].search([
    #         ('product_id', '=', self.product_id.id),
    #         ('company_id', '=', self.company_id.id),
    #         ('id', 'in', self.move_finished_ids.mapped('move_line_ids.lot_id.id'))
    #     ])
    #     ptype = final_product_lots.product_id.nhcl_product_type
    #     if final_product_lots:
    #         final_product_lots.write({
    #             'cost_price': total_cp / len(final_product_lots) if len(final_product_lots) else 0,
    #             'rs_price': total_rsp / len(final_product_lots) if len(final_product_lots) else 0,
    #             'type_product': ('brand' if ptype == 'branded'
    #                              else 'un_brand' if ptype == 'unbranded'
    #             else False),
    #             'ref': final_product_lots.product_id.barcode,
    #         })

    def _prepare_attribute_values(self, product):
        """Map product attributes to lot category/description fields"""
        res = {}

        for ptav in product.product_template_attribute_value_ids:
            attr_name = ptav.attribute_id.name or ''
            val_id = ptav.product_attribute_value_id.id

            if attr_name.startswith('Color'):
                res['category_1'] = val_id
            elif attr_name.startswith('Fit'):
                res['category_2'] = val_id
            elif attr_name.startswith('Brand'):
                res['category_3'] = val_id
            elif attr_name.startswith('Pattern'):
                res['category_4'] = val_id
            elif attr_name.startswith('Border Type'):
                res['category_5'] = val_id
            elif attr_name.startswith('Border Size'):
                res['category_6'] = val_id
            elif attr_name.startswith('Size'):
                res['category_7'] = val_id
            elif attr_name.startswith('Range'):
                res['description_2'] = val_id
            elif attr_name.startswith('Collection'):
                res['description_3'] = val_id
            elif attr_name.startswith('Fabric'):
                res['description_4'] = val_id
            elif attr_name.startswith('Exclusive'):
                res['description_5'] = val_id
            elif attr_name.startswith('Print'):
                res['description_6'] = val_id
            elif attr_name.startswith('Days Ageing'):
                res['description_7'] = val_id

        return res

    def _update_final_product_cp_rsp(self):
        """ Calculate total CP and RSP from all components across backorders. """

        total_cp = sum(
            lot.cost_price or 0
            for move in self.move_raw_ids
            for lot in move.lot_ids
        )
        total_rsp = sum(
            lot.rs_price or 0
            for move in self.move_raw_ids
            for lot in move.lot_ids
        )

        final_product_lots = self.env['stock.lot'].search([
            ('product_id', '=', self.product_id.id),
            ('company_id', '=', self.company_id.id),
            ('id', 'in', self.move_finished_ids.mapped('move_line_ids.lot_id.id'))
        ])

        if not final_product_lots:
            return

        ptype = self.product_id.nhcl_product_type

        # 🔹 Get attribute values from product
        attribute_vals = self._prepare_attribute_values(self.product_id)
        values = {
            'cost_price': total_cp / len(final_product_lots),
            'rs_price': total_rsp / len(final_product_lots),
            'type_product': (
                'brand' if ptype == 'branded'
                else 'un_brand' if ptype == 'unbranded'
                else False
            ),
            'ref': self.product_id.barcode,
        }
        values.update(attribute_vals)
        final_product_lots.write(values)

    def get_production_ids(self):
        active_ids = self.env.context.get('active_ids', [])
        return {
            'name': 'Manf Bulk Update',
            'type': 'ir.actions.act_window',
            'res_model': 'nhcl.bom.lot.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_production_ids': [(6, 0,active_ids)],
            },
        }

    def action_serial_mass_produce_wizard(self, mark_as_done=False):
        """ Override to pass 'nhcl_last_serial_number' to the wizard via context. """
        self.ensure_one()
        self._check_company()

        if self.state not in ['confirmed', 'progress', 'to_close']:
            return
        if self.product_id.tracking != 'serial':
            return

        master_seq = self.env['nhcl.master.sequence'].search([
            ('nhcl_code', '=', 'Auto Serial Number'),
            ('nhcl_active', '=', True)
        ], limit=1)

        if master_seq:
            last_serial_number = 'R' + str(master_seq.nhcl_next_number - 1)
        else:
            last_serial_number = '0'  # Default if no active sequence found

        action = super().action_serial_mass_produce_wizard(mark_as_done)

        # Pass 'nhcl_last_serial_number' to the wizard view context
        action['context'].update({
            'default_nhcl_last_serial_number': last_serial_number
        })

        return action


    def _compute_import_prod_lines(self):
        if self.env.user and self.env.user.import_mrp_prod_line == True:
            self.allow_import_order = True
        else:
            self.allow_import_order = False

    @api.onchange('product_id')
    def _onchange_fun_import_prod_lines(self):
        self._compute_import_prod_lines()

    def _get_quant_by_lot(self, serial_or_ref):
        """
        Fast quant-based lookup for lot/serial.
        """
        stock_location = self.env.ref('stock.stock_location_stock').id
        quant = self.env['stock.quant'].search([
            ('quantity', '>', 0),
            ('location_id', '=', stock_location),
            ('company_id.nhcl_company_bool', '=', True),
            '|',
            ('lot_id.name', '=', serial_or_ref),
            ('lot_id.ref', '=', serial_or_ref),
        ], limit=1)
        return quant

    @api.onchange('stock_barcode')
    def _onchange_stock_barcode(self):
        if not self.stock_barcode:
            return
        if self.state not in ['confirmed', 'progress']:
            raise ValidationError("Scanning is allowed only in Confirmed or In Progress state.")
        barcode = self.stock_barcode.strip()
        location = self.env.ref('stock.stock_location_stock').id
        prod_location = self.env['stock.location'].search([('usage', '=', 'production'),('company_id.nhcl_company_bool', '=', True)],limit=1).id
        product = False
        lot_name = False
        # --------------------------------
        # LOT / SERIAL (GS1 or CUSTOM)
        # --------------------------------
        if 'R' in barcode:
            # Split from first occurrence of R
            lot_name = barcode[barcode.index('R'):]
            quants = self.env['stock.quant'].search([('quantity', '>', 0),('company_id.nhcl_company_bool', '=', True),('location_id', '=', location),
                        '|',('lot_id.name', '=', lot_name),('lot_id.ref', '=', lot_name),])
            if not quants:
                raise ValidationError(f"Lot / Serial {lot_name} not found")
            for quant in quants:
                product = quant.product_id
                component_line = self.move_raw_ids
                if product.tracking == 'serial':
                    if self.entered_qty > 0:
                        raise ValidationError(f"For serial tracking products, you should not enter Qty.")
                    assigned_serials = component_line.mapped('lot_id.name')
                    if quant.lot_id.name in assigned_serials:
                        raise ValidationError("This serial number is already added in this MO.")
                    else:
                        # Create new move line
                        move_line_vals = {
                            'lot_id': quant.lot_id.name.id,
                            'company_id': quant.company_id.id,
                            'product_uom_id': product.uom_po_id.id,
                            'product_id': product.id,
                            'location_id': location,
                            'location_dest_id': prod_location,
                            'quantity': quant.quantity,
                            'move_id': component_line._origin.id,
                            'production_id': self.id,
                        }
                        self.env['stock.move.line'].create(move_line_vals)
                if product.tracking == 'lot':
                    entered_qty = self.entered_qty
                    if entered_qty < 1:
                        raise ValidationError(f"For lot tracking products, you should enter Qty.")
                    if quant.quantity < entered_qty:
                        raise ValidationError(f"You have entered more than available Qty.")
                    component_line = self.move_raw_ids.filtered(lambda l: l.product_id == product)
                    if not component_line:
                        raise UserError(f'Product {product.display_name} is not part of this production order.')
                    existing_move_line = component_line.move_line_ids.filtered(
                        lambda ml: ml.lot_id.name == quant.lot_id.name)
                    if (sum(existing_move_line.mapped('quantity')) + self.entered_qty) > component_line.product_uom_qty:
                        # Increase quantity
                        raise ValidationError(f"Qty is given more for product {product.display_name}.")
                    else:
                        # Create new move line
                        move_line_vals = {
                            'lot_id': quant.lot_id.id,
                            'company_id': quant.company_id.id,
                            'product_uom_id': product.uom_po_id.id,
                            'product_id': product.id,
                            'location_id': location,
                            'location_dest_id': prod_location,
                            'quantity': entered_qty,
                            'move_id': component_line._origin.id,
                            'production_id': self.id,
                        }
                        self.env['stock.move.line'].create(move_line_vals)
        # --------------------------------
        # EAN-13 PRODUCT BARCODE
        # --------------------------------
        elif len(barcode) == 13:
            quants = self.env['stock.quant'].search([('lot_id.ref', '=', barcode), ('quantity', '>', 0),('company_id.nhcl_company_bool', '=', True)])
            if not quants:
                raise ValidationError(f"No product found for barcode {barcode}")

        else:
            raise ValidationError("Invalid barcode format")

        self.stock_barcode = False
        self.entered_qty = False

class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    prod_serial_no = fields.Many2many('stock.lot', string='Lot/Serial No', copy=False)
    prod_barcode = fields.Char('Barcode', copy=False)



