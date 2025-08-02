from odoo import models, fields, api
from odoo.exceptions import ValidationError

class MultiProductWizardDirect(models.TransientModel):
    _name = 'multi.product.wizard.direct'
    _description = 'Wizard to select multiple products'

    product_ids = fields.Many2many('product.product', string="Select Products")
    request_id = fields.Many2one('approval.request', string="Approval")  # Adapt this for your use case
    categ_ids = fields.Many2many('product.category', string='Categories')

    def action_add_products(self):
        for product in self.product_ids:
            self.env['approval.product.line'].create({
                'approval_request_id': self.request_id.id,
                'product_id': product.id,
                'description': product.display_name,
                'quantity': 1.0,
                'family': product.categ_id.parent_id.parent_id.parent_id.id,
                'category': product.categ_id.parent_id.parent_id.id,
                'Class': product.categ_id.parent_id.id,
                'brick': product.categ_id.id,
            })


class BrandLotProducts(models.TransientModel):
    _name = 'brand.lot.product.wizard'
    _description = 'Brand Lot Product'

    vendor_id = fields.Many2one('vendor.return')
    brand_barcode = fields.Char(string="Brand Barcode")
    brand_qty = fields.Float(string="Brand Qty")
    brand_serials = fields.Many2many('stock.lot')

    def action_add_serials(self):
        if self.brand_serials:
            existing_lot_ids = set(self.vendor_id.vendor_line_ids.mapped('lot_id.id'))
            new_lines = []

            for serials in self.brand_serials:
                if serials.id in existing_lot_ids:
                    raise ValidationError(f"Serial number '{serials.name}' is already added.")
                used_in_other_returns = self.env['vendor.return.line'].search([
                    ('lot_id', '=', serials.id),
                    ('vendor_id.state', '!=', 'cancel'),
                ], limit=1)
                if used_in_other_returns:
                    raise ValidationError(f"Serial number '{serials.name}' is already used in another return '{used_in_other_returns.vendor_id.name}'.")
                # Serial-tracked
                if serials.product_qty == 1.0:
                    if self.brand_qty and self.brand_qty > 0:
                        raise ValidationError("Do not enter quantity for serial-tracked items.")
                    qty = 1.0
                else:
                    if not self.brand_qty or self.brand_qty <= 0:
                        raise ValidationError("Please enter quantity for lot-tracked item.")
                    if self.brand_qty > serials.product_qty:
                        raise ValidationError(
                            f"Entered quantity exceeds available lot quantity for serial '{serials.name}'")
                    qty = self.brand_qty

                new_lines.append((0, 0, {
                    'lot_id': serials.id,
                    'grc_id': serials.picking_id.id,
                    'partner_id': serials.picking_id.partner_id.id,
                    'lot_cp': serials.cost_price,
                    'lot_mrp': serials.mr_price,
                    'lot_rsp': serials.rs_price,
                    'quantity': qty,
                }))
            # Add all new lines in one call
            self.vendor_id.write({'vendor_line_ids': new_lines})
            # Reset the wizard fields
            self.vendor_id.brand_barcode = False
            self.vendor_id.lot_qty = 0.0
