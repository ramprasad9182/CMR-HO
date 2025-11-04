# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from datetime import date
from collections import defaultdict
from odoo.exceptions import ValidationError


class VendorReturn(models.Model):
    """ This model represents vendor.return."""
    _name = 'vendor.return'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'VendorReturn'

    name = fields.Char(string='Sequence', required=True, default='New')
    date = fields.Date(string='Date', default=lambda self: date.today())
    state = fields.Selection([('draft', 'Draft'),('done', 'Done'),('cancel', 'Cancel')], string='Status', default='draft')
    un_brand_barcode = fields.Char(string="Un brand Barcode")
    brand_barcode = fields.Char(string="Brand Barcode")
    lot_qty = fields.Float(string='Lot Qty', digits=(16, 2))
    return_type = fields.Selection([
        ('regular', 'Regular'),('direct_debit_note', 'Direct Debit Note')], string='Return Type', default='regular')
    vendor_line_ids = fields.One2many('vendor.return.line','vendor_id')

    def action_confirm(self):
        for rec in self:
            if len(rec.vendor_line_ids) == 0:
                raise ValidationError("No line's are added to confirm.")
            lines_by_grc = {}
            if rec.return_type == 'regular':
                # Step 1: Group lines by grc_id
                for line in rec.vendor_line_ids:
                    if not line.grc_id or not line.lot_id or not line.quantity:
                        raise ValidationError("Each return line must have a GRC, Lot and Quantity.")
                    lines_by_grc.setdefault(line.grc_id, []).append(line)
                # Step 2: Process each grc_id group
                for grc, line_group in lines_by_grc.items():
                    return_wizard = self.env['stock.return.picking'].with_context(
                        active_ids=[grc.id],
                        active_id=grc.id,
                        active_model='stock.picking'
                    ).create({
                        'picking_id': grc.id,
                    })
                    # Step 1: Group lines by product_id
                    product_group = {}
                    for line in line_group:
                        product_id = line.lot_id.product_id.id
                        product_group.setdefault(product_id, []).append(line)
                    for wizard_line in return_wizard.product_return_moves:
                        product_id = wizard_line.product_id.id
                        if product_id in product_group:
                            vendor_lines = product_group[product_id]
                            total_qty = sum(line.quantity for line in vendor_lines)
                            wizard_line.quantity = total_qty
                            wizard_line.to_refund = True
                    # Create the return picking
                    result = return_wizard.create_returns()
                    return_picking = self.env['stock.picking'].browse(result.get('res_id'))
                    return_picking.action_confirm()
                    return_picking.action_assign()
                    # Step 2: Remove auto-created move lines and create manually
                    for move in return_picking.move_ids:
                        move.move_line_ids.unlink()
                        product_lines = product_group.get(move.product_id.id, [])
                        total_qty = sum(line.quantity for line in product_lines)
                        move.product_uom_qty = total_qty
                    return_picking.move_line_ids.unlink()
                    for product_id, vendor_lines in product_group.items():
                        product = self.env['product.product'].browse(product_id)
                        move = return_picking.move_ids.filtered(lambda m: m.product_id.id == product_id)
                        if product.tracking == 'serial':
                            # One move line per lot, qty_done = 1
                            for line in vendor_lines:
                                for i in range(int(line.quantity)):
                                    return_move_line = self.env['stock.move.line'].create({
                                        'picking_id': return_picking.id,
                                        'move_id': move.id,
                                        'product_id': product_id,
                                        'lot_id': line.lot_id.id,
                                        'location_id': return_picking.location_id.id,
                                        'location_dest_id': return_picking.location_dest_id.id,
                                        'qty_done': 1,
                                    })
                                    return_move_line.picking_id.return_id = line.grc_id.id
                        else:
                            # Group by lot for lot-tracked or no tracking
                            lot_groups = {}
                            for line in vendor_lines:
                                lot_groups.setdefault(line.lot_id.id, 0)
                                lot_groups[line.lot_id.id] += line.quantity
                            for lot_id, qty in lot_groups.items():
                                return_new_move_line = self.env['stock.move.line'].create({
                                    'picking_id': return_picking.id,
                                    'move_id': move.id,
                                    'product_id': product_id,
                                    'lot_id': lot_id,
                                    'location_id': return_picking.location_id.id,
                                    'location_dest_id': return_picking.location_dest_id.id,
                                    'qty_done': qty,
                                })
                                matched_line = next((l for l in vendor_lines if l.lot_id.id == lot_id), None)
                                if matched_line:
                                    return_new_move_line.picking_id.return_id = matched_line.grc_id.id
                    return_picking.button_validate()
                    invoice_lines = []
                    vendor = grc.partner_id
                    # Group by product and lot for refund
                    for product_id, vendor_lines in product_group.items():
                        product = self.env['product.product'].browse(product_id)
                        # Group by lot_cp (cost price)
                        lot_price_groups = {}
                        for line in vendor_lines:
                            key = (product.id, line.lot_cp)
                            lot_price_groups.setdefault(key, 0)
                            lot_price_groups[key] += line.quantity
                        for (product_id, unit_price), qty in lot_price_groups.items():
                            taxes = None
                            product = self.env['product.product'].browse(product_id)
                            tax_ids = product.taxes_id._filter_taxes_by_company(self.env.company)
                            for tax in tax_ids:
                                if tax.min_amount <= unit_price <= tax.max_amount:
                                    taxes = tax
                                    break
                            invoice_lines.append((0, 0, {
                                'product_id': product_id,
                                'quantity': qty,
                                'price_unit': unit_price,
                                'tax_ids': taxes,
                                'name': product.display_name,
                                'account_id': product.property_account_expense_id.id or product.categ_id.property_account_expense_categ_id.id,
                            }))
                            # Create refund move (vendor credit note)
                        refund = self.env['account.move'].create({
                            'move_type': 'in_refund',
                            'partner_id': vendor.id,
                            'journal_id': self.env.ref('account.1_purchase').id,
                            'invoice_date': fields.Date.today(),
                            'invoice_origin': grc.name,
                            'invoice_line_ids': invoice_lines,
                        })
                        refund.action_post()
                        for line in line_group:
                            line.refund_id = refund.id
                        return_picking.vendor_refund = refund.id
                rec.write({'state': 'done'})
            elif rec.return_type == 'direct_debit_note':
                grouped_lines = defaultdict(list)
                for line in self.vendor_line_ids:
                    if line.grc_id:
                        grouped_lines[line.grc_id].append(line)
                for grc, lines in grouped_lines.items():
                    invoice_lines = []
                    partner = grc.partner_id
                    for line in lines:
                        product = line.lot_id.product_id
                        tax_ids = product.taxes_id._filter_taxes_by_company(self.env.company)
                        selected_tax = False
                        for tax in tax_ids:
                            if tax.min_amount <= line.promo_cp <= tax.max_amount:
                                selected_tax = tax
                                break
                        invoice_lines.append((0, 0, {
                            'product_id': product.id,
                            'quantity': line.quantity,
                            'price_unit': line.promo_cp,
                            'tax_ids': [(6, 0, [selected_tax.id])] if selected_tax else False,
                            'name': product.display_name,
                            'account_id': product.property_account_expense_id.id or product.categ_id.property_account_expense_categ_id.id,
                        }))
                    refund = self.env['account.move'].create({
                        'move_type': 'in_refund',
                        'partner_id': partner.id,
                        'journal_id': self.env.ref('account.1_purchase').id,
                        'invoice_date': fields.Date.today(),
                        'invoice_origin': grc.name,
                        'invoice_line_ids': invoice_lines,
                    })
                    refund.action_post()
                    for line in lines:
                        line.refund_id = refund.id
                rec.write({'state': 'done'})


    def get_vendor_return_serials(self):
        promotional_serials = self.env['store.pos.order.line'].search([('is_used','=',False),('vendor_return_disc_price','>',0)])
        lines = []
        if promotional_serials:
            for promo in promotional_serials:
                lot = self.env['stock.lot'].sudo().search([
                    ('company_id.nhcl_company_bool', '=', True),
                    ('name', '=', promo.lot_name)])
                if not lot:
                    raise ValidationError(f"{lot.name} is not available to return.")
                lines.append((0, 0, {
                    'store_pos_order_id': promo.id,
                    'lot_id': lot.id,
                    'grc_id': lot.picking_id.id,
                    'partner_id': lot.picking_id.partner_id.id,
                    'lot_cp': lot.cost_price,
                    'lot_mrp': lot.mr_price,
                    'lot_rsp': lot.rs_price,
                    'quantity': promo.quantity,
                    'tracking': lot.product_id.tracking,
                    'promo_cp': promo.vendor_return_disc_price,
                }))
                promo.is_used = True
            self.update({'vendor_line_ids': lines})
        else:
            message = "No Records Fetched"
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'message': message,
                    'type': 'warning',
                    'sticky': False,
                }
            }



    def get_branded_products(self):
        if self.brand_barcode:
            if len(self.brand_barcode) != 13:
                raise ValidationError("Brand barcode must be exactly 13 numbers")
            lots = self.env['stock.lot'].sudo().search([('company_id.nhcl_company_bool','=',True),('product_qty','>',0),('ref','=',self.brand_barcode)])
            total_qty = sum(lots.mapped('product_qty'))
            if lots[0].product_id.tracking == 'lot':
                if self.lot_qty:
                    if self.lot_qty < total_qty:
                        return {
                            'name': _("Brand Serials"),
                            'type': 'ir.actions.act_window',
                            'view_type': 'form',
                            'view_mode': 'form',
                            'res_model': 'brand.lot.product.wizard',
                            'target': 'new',
                            'context': {
                                'default_vendor_id': self.id,
                                'default_brand_barcode': self.brand_barcode,
                                'default_brand_qty': self.lot_qty,
                            },
                        }
                    else:
                        raise ValidationError(f'Given Qty {self.lot_qty} is More than available {total_qty}')
                else:
                    raise ValidationError(f'For lot type of products qty should enter.')
            else:
                return {
                    'name': _("Brand Serials"),
                    'type': 'ir.actions.act_window',
                    'view_type': 'form',
                    'view_mode': 'form',
                    'res_model': 'brand.lot.product.wizard',
                    'target': 'new',
                    'context': {
                        'default_vendor_id': self.id,
                        'default_brand_barcode': self.brand_barcode,
                    },
                }

    def action_cancel(self):
        self.write({'state':'cancel'})

    @api.model
    def create(self, vals):
        """Override the default create method to customize record creation logic."""
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('cmr.vendor.return')
        return super(VendorReturn,self).create(vals)

    @api.onchange('un_brand_barcode')
    def onchange_un_brand_barcode(self):
        if self.un_brand_barcode:
            if len(self.un_brand_barcode) == 13:
                raise ValidationError("You entered a branded barcode. Please scan a non-branded one.")

            barcode = self.un_brand_barcode
            r_index = barcode.find('R')
            if r_index != -1:
                serial_number = barcode[r_index:]
                lot = self.env['stock.lot'].sudo().search([
                    ('company_id.nhcl_company_bool', '=', True),
                    ('product_qty', '>', 0),
                    ('name', '=', serial_number)
                ], limit=1)
                if not lot:
                    raise ValidationError(f"{lot.name} is not available to return.")
                if lot:
                    existing_lot_ids = set(self.vendor_line_ids.mapped('lot_id.id'))
                    if lot.id in existing_lot_ids:
                        raise ValidationError(f"Serial number '{lot.name}' is already added.")
                    used_in_serial_other_returns = self.env['vendor.return.line'].search([
                        ('lot_id', '=', lot.id),
                        ('vendor_id.state', '!=', 'cancel'),
                    ], limit=1)
                    if used_in_serial_other_returns and used_in_serial_other_returns.lot_id.product_id.tracking == 'serial':
                        raise ValidationError(f"Serial number '{lot.name}' is already used in another return '{used_in_serial_other_returns.vendor_id.name}'.")
                    if lot.product_qty == 1.0:
                        if self.lot_qty and self.lot_qty > 0:
                            raise ValidationError("Do not enter quantity for serial-tracked items.")
                        qty = 1.0
                    else:
                        if not self.lot_qty or self.lot_qty <= 0:
                            raise ValidationError("Please enter quantity for lot-tracked item.")
                        if self.lot_qty > lot.product_qty:
                            raise ValidationError(
                                f"Entered quantity exceeds available lot quantity for serial '{lot.name}'")
                        qty = self.lot_qty

                    # Use .new() to create new transient records in onchange context
                    new_line = self.vendor_line_ids.new({
                        'lot_id': lot.id,
                        'grc_id': lot.picking_id.id,
                        'partner_id': lot.picking_id.partner_id.id,
                        'lot_cp': lot.cost_price,
                        'lot_mrp': lot.mr_price,
                        'lot_rsp': lot.rs_price,
                        'quantity': qty,
                        'tracking': lot.product_id.tracking,
                    })
                    self.vendor_line_ids += new_line  # This is valid in onchange context
                    self.un_brand_barcode = False
                    self.lot_qty = 0.0


class VendorReturnLine(models.Model):
    """ This model represents vendor.return."""
    _name = 'vendor.return.line'
    _description = 'VendorReturnLine'

    vendor_id = fields.Many2one('vendor.return', string='Vendor Return', ondelete="cascade")
    lot_id = fields.Many2one('stock.lot',string='Lot/Serial')
    partner_id = fields.Many2one('res.partner',string='Partner')
    grc_id = fields.Many2one('stock.picking',string='GRC')
    refund_id = fields.Many2one('account.move', string='Refund No.')
    promo_cp = fields.Float(string='Promo S.P')
    lot_cp = fields.Float(string='C.P')
    lot_mrp = fields.Float(string='M.R.P')
    lot_rsp = fields.Float(string='R.S.P')
    quantity = fields.Float(string='Quantity')
    tracking = fields.Selection([
        ('serial', 'By Unique Serial Number'),
        ('lot', 'By Lots'),
        ('none', 'No Tracking')],
        string="Tracking", required=True, default='none')
    store_pos_order_id = fields.Many2one('store.pos.order.line', string='Store POS')


    @api.constrains('quantity')
    def maintain_unique_qty(self):
        for i in self:
            if i.lot_id and i.lot_id.product_id and i.lot_id.product_id.tracking == 'serial' and i.quantity > 1 and i.vendor_id.return_type == 'regular':
                raise ValidationError("you should enter qty for serial tracking products")

    def unlink(self):
        """When vendor return line is deleted, reset is_used = False"""
        for line in self:
            if line.store_pos_order_id and line.vendor_id.state == 'draft':
                line.store_pos_order_id.is_used = False
            if line.vendor_id.state == 'done':
                raise ValidationError("You are not allowed to delete.")
        return super(VendorReturnLine, self).unlink()

