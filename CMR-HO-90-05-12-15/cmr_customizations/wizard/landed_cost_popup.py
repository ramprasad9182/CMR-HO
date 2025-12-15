from odoo import models,fields


class LandedCostPopup(models.TransientModel):
    """Created nhcl.serial.no.popup class to add fields and functions"""
    _name = 'nhcl.landed.cost.confirmation.popup'
    _description = " landed Cost PopUp"

    nhcl_picking_id = fields.Many2one('stock.picking', string='Ref Picking')

    def button_confirm(self):
        if self.nhcl_picking_id:
            self.nhcl_picking_id.is_landed_cost_confirm = True
            return self.nhcl_picking_id.with_context(
                        skip_sanity_check=True).button_validate()
