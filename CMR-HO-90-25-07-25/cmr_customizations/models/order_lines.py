import base64
import csv

import openpyxl
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import io
import re
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    allow_import_order = fields.Boolean('Allow Import', compute='_compute_import_order_lines')


    def _compute_import_order_lines(self):
        if self.env.user and self.env.user.import_sale_order_line == True:
            self.allow_import_order = True
        else:
            self.allow_import_order = False

    @api.onchange('so_type')
    def _onchange_so_type(self):
        self._compute_import_order_lines()


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    allow_import_order = fields.Boolean('Allow Import', compute='_compute_import_order_lines')

    def _compute_import_order_lines(self):
        if self.env.user and self.env.user.import_purchase_order_line == True:
            self.allow_import_order = True
        else:
            self.allow_import_order = False

    @api.onchange('nhcl_po_type')
    def _onchange_fun_import_order(self):
        self._compute_import_order_lines()


class AccountMove(models.Model):
    _inherit = 'account.move'

    allow_import_order = fields.Boolean('Allow Import', compute='_compute_import_order_lines')

    def _compute_import_order_lines(self):
        if self.env.user and self.env.user.import_account_move_line == True:
            self.allow_import_order = True
        else:
            self.allow_import_order = False

    @api.onchange('partner_id')
    def _onchange_fun_import_order(self):
        self._compute_import_order_lines()


class Picking(models.Model):
    _inherit = 'stock.picking'

    allow_import_order = fields.Boolean('Allow Import', compute='_compute_import_move_lines')

    def _compute_import_move_lines(self):
        if self.env.user and self.env.user.import_stock_move_line == True:
            self.allow_import_order = True
        else:
            self.allow_import_order = False

    @api.onchange('partner_id')
    def _onchange_import_partner_id(self):
        self._compute_import_move_lines()


class ApprovalRequest(models.Model):
    _inherit = 'approval.request'

    allow_import_order = fields.Boolean('Allow Import', compute='_compute_import_approval_lines')
    terms_conditions = fields.Text(string="Terms and Conditions")

    def _compute_import_approval_lines(self):
        if self.env.user and self.env.user.import_approval_line == True:
            self.allow_import_order = True
        else:
            self.allow_import_order = False

    @api.onchange('pi_type')
    def _onchange_fun_import_approvals(self):
        self._compute_import_approval_lines()


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

    # def action_import_excel(self):
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Import Excel',
    #         'res_model': 'manafacturing.import.wizard',
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'context': {'default_manafacturing_id': self.id},
    #     }

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

        # Ensure nhcl_last_serial_number is not modified unexpectedly
        # if 'nhcl_last_serial_number' not in vals:
        #     vals['nhcl_last_serial_number'] = self.nhcl_last_serial_number

        # Check if state is changing to 'done' before calling super
        update_final_product = 'state' in vals and vals['state'] == 'done'

        res = super(MrpProduction, self).write(vals)

        # After write, update final product CP & RSP if state changed to 'done'
        if update_final_product:
            for mo in self:
                mo._update_final_product_cp_rsp()

        return res

    def _update_final_product_cp_rsp(self):
        """ Calculate total CP and RSP from all components across backorders. """
        total_cp = sum(lot.cost_price or 0 for move in self.move_raw_ids for lot in move.lot_ids)
        total_rsp = sum(lot.rs_price or 0 for move in self.move_raw_ids for lot in move.lot_ids)

        # Get all serial numbers linked to this MO (including backorders)
        final_product_lots = self.env['stock.lot'].search([
            ('product_id', '=', self.product_id.id),
            ('company_id', '=', self.company_id.id),
            ('id', 'in', self.move_finished_ids.mapped('move_line_ids.lot_id.id'))
        ])

        if final_product_lots:
            final_product_lots.write({
                'cost_price': total_cp / len(final_product_lots) if len(final_product_lots) else 0,
                'rs_price': total_rsp / len(final_product_lots) if len(final_product_lots) else 0
            })

    def action_serial_mass_produce_wizard(self, mark_as_done=False):
        print("called")
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

    @api.onchange('stock_barcode')
    def _onchange_stock_barcode(self):
        if not self.stock_barcode:
            return

        barcode = self.stock_barcode
        gs1_pattern = r'01(\d{14})21([A-Za-z0-9]+)'
        ean13_pattern = r'(\d{13})'
        custom_serial_pattern = r'^(R\d+)'

        gs1_match = re.match(gs1_pattern, barcode)
        ean13_match = re.match(ean13_pattern, barcode)
        custom_serial_match = re.match(custom_serial_pattern, barcode)

        def search_product(barcode_field, barcode_value):
            """Helper function to find product in product.product or product.template"""
            product = self.env['product.product'].search([(barcode_field, '=', barcode_value)], limit=1)
            if not product:
                template = self.env['product.template'].search([(barcode_field, '=', barcode_value)], limit=1)
                if template:
                    product = template.product_variant_id
            return product

        if gs1_match:
            product_barcode = gs1_match.group(1)
            serial_number = gs1_match.group(2)
            product = search_product('barcode', product_barcode)
            if not product:
                raise UserError(f'No product found with barcode {product_barcode}.')

        elif ean13_match:
            product_barcode = ean13_match.group(1)
            lots = self.env['stock.lot'].search([('ref', '=', product_barcode), ('product_qty', '>', 0)])
            if not lots:
                raise UserError(f'No lots found for barcode {product_barcode}.')
            product = lots[0].product_id
            serial_number = lots[0].name  # Use the first available lot

        elif custom_serial_match:
            serial_number = barcode
            lot = self.env['stock.lot'].search([('name', '=', serial_number)], limit=1)

            if not lot:
                # Fallback to internal_ref_lot
                lots = self.env['stock.lot'].search([('internal_ref_lot', '=', serial_number), ('product_qty', '>', 0)])
                if not lots:
                    raise UserError(f'No lots found for internal reference {serial_number}.')

                lot = lots[0]
                product = lot.product_id
                component_line = self.move_raw_ids.filtered(lambda l: l.product_id == product)
                if not component_line:
                    raise UserError(f'Product {product.display_name} is not part of this production order.')

                required_qty = component_line.product_uom_qty
                current_assigned_qty = sum(component_line.move_line_ids.mapped('qty_done'))

                if current_assigned_qty >= required_qty:
                    raise UserError(
                        f'Cannot assign more than required quantity ({required_qty}) for {product.display_name}.')

                assign_qty = min(lot.product_qty, required_qty - current_assigned_qty)
                if assign_qty <= 0:
                    raise UserError(f'No available quantity in lot {serial_number}.')

                move_line_vals = {
                    'lot_id': lot.id,
                    'company_id': self.env['res.company'].sudo().search([('nhcl_company_bool', '=', True)]).id,
                    'product_uom_id': product.uom_po_id.id,
                    'product_id': product.id,
                    'location_id': self.env.ref('stock.stock_location_stock').id,
                    'location_dest_id': self.env['stock.location'].search(
                        [('usage', '=', 'production'), ('company_id.nhcl_company_bool', '=', True)]).id,
                    'qty_done': assign_qty,
                    'move_id': component_line._origin.id,
                    'production_id': self.id,
                }
                self.env['stock.move.line'].create(move_line_vals)
                self.stock_barcode = False
                return
            else:
                product = lot.product_id

        else:
            raise UserError('Invalid barcode format.')

        # Ensure product is in the production order's component list
        component_line = self.move_raw_ids.filtered(lambda l: l.product_id == product)
        if not component_line:
            raise UserError(f'Scanned product {product.display_name} is not a component of this production order.')

        # Search for the corresponding lot/serial
        lot = self.env['stock.lot'].search([('product_id', '=', product.id), ('name', '=', serial_number)], limit=1)
        if not lot:
            raise UserError(f'No serial number found for {serial_number}.')

        # Validation & Assigning Logic
        if product.tracking == 'serial':
            assigned_serials_count = len(component_line.lot_ids)
            max_allowed_serials = component_line.product_uom_qty

            if assigned_serials_count >= max_allowed_serials:
                raise UserError(f'Cannot assign more serial numbers than required quantity ({max_allowed_serials}).')

            if lot in component_line.lot_ids:
                raise UserError(f'Serial number {serial_number} is already assigned.')

            component_line.lot_ids = [(4, lot.id)]

        elif product.tracking == 'lot':
            required_qty = component_line.product_uom_qty
            current_assigned_qty = sum(component_line.move_line_ids.mapped('qty_done'))

            if current_assigned_qty >= required_qty:
                component_line.picked = False
                raise UserError(f'Cannot assign more lot quantities than required ({required_qty}).')

            available_qty = lot.product_qty
            assign_qty = min(available_qty, required_qty - current_assigned_qty)

            if assign_qty <= 0:
                raise UserError(f'No available quantity in lot {serial_number}.')

            move_line_vals = {
                'lot_id': lot.id,
                'company_id': self.env['res.company'].sudo().search([('nhcl_company_bool', '=', True)]).id,
                'product_uom_id': product.uom_po_id.id,
                'product_id': product.id,
                'location_id': self.env.ref('stock.stock_location_stock').id,
                'location_dest_id': self.env['stock.location'].search(
                    [('usage', '=', 'production'), ('company_id.nhcl_company_bool', '=', True)]).id,
                'qty_done': assign_qty,
                'move_id': component_line._origin.id,
                'production_id': self.id,
            }
            self.env['stock.move.line'].create(move_line_vals)

        self.stock_barcode = False


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    prod_barcode = fields.Char('Barcode', copy=False)
    # lot_ids = fields.Many2many('stock.lot', string='Lot/Serial No', copy=False)



class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    prod_serial_no = fields.Many2many('stock.lot', string='Lot/Serial No', copy=False)
    prod_barcode = fields.Char('Barcode', copy=False)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    prod_serial_no = fields.Many2many('stock.lot', string='Lot/Serial No', copy=False)
    prod_barcode = fields.Char('Barcode', copy=False)


class StockMove(models.Model):
    _inherit = 'stock.move'

    prod_barcode = fields.Char('Barcode', copy=False)
    # dummy_lot_ids = fields.Many2many('stock.lot', string='Lot/Serial No', copy=False)


class ApprovalProductLine(models.Model):
    _inherit = 'approval.product.line'

    prod_serial_no = fields.Many2many('stock.lot', string='Lot/Serial No', copy=False)
    prod_barcode = fields.Char('Barcode', copy=False)


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    prod_serial_no = fields.Many2many('stock.lot', string='Lot/Serial No', copy=False)
    prod_barcode = fields.Char('Barcode', copy=False)



