# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, _


class StockAdjustmentName(models.TransientModel):
    _name = 'stock.adjustment.name'
    _description = 'Inventory Adjustment Reference / Reason'

    quant_ids = fields.Many2many('stock.inventory.line')
    inventory_adjustment_name = fields.Char(default="Quantity Updated", string="Inventory Reason")

    def action_apply(self):
        quants = self.quant_ids.filtered(lambda x:x.difference_qty != 0)
        return quants.with_context(inventory_name=self.inventory_adjustment_name).action_apply_inventory()
