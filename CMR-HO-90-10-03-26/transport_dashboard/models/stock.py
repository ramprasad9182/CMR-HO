from odoo import models, fields

class Picking(models.Model):
    _inherit = "stock.picking"

    is_opened = fields.Boolean(string="Is Opened", help="Tick if the bale/package is opened.")
    is_received = fields.Boolean(string="Is Received", help="Tick if the bale/package is received.")

