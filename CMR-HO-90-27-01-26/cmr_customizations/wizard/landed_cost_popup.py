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


class LandedCostConfirmWizard(models.TransientModel):
    _name = 'nhcl.landed.cost.wizard'
    _description = 'Landed Cost Wizard'

    nhcl_landed_id = fields.Many2one('stock.landed.cost', string="Landed Cost")
    bypass_landed_wizard = fields.Boolean(string="Flag", default=False)

    def action_confirm(self):
        self.ensure_one()
        if self.nhcl_landed_id:
            self.nhcl_landed_id.with_context(bypass_landed_wizard=True).button_validate()
