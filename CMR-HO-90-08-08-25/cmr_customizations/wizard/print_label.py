from odoo import models, fields, api
from odoo.exceptions import UserError

class PrintLabel(models.TransientModel):
    _name = 'print.label'
    _description = 'Print Label'

    label_type = fields.Selection([
        ('brand', 'Brand'),
        ('ready_made', 'Ready Made'),
        ('general', 'General')
    ], string="Label Type", required=True)

    picking_id = fields.Many2one('stock.picking', string="Picking", required=True)

    def action_print_label(self):
        if not self.picking_id:
            raise UserError("No Picking record linked.")
        if self.label_type == 'brand':
            return self.picking_id.print_barcodes()
        elif self.label_type == 'ready_made':
            return self.picking_id.print_ready_made_barcodes()
        elif self.label_type == 'general':
            return self.picking_id.print_dymo()
        else:
            raise UserError("Unknown label type.")

    def action_preview_label(self):
        if not self.picking_id:
            raise UserError("No Picking record linked.")
        if self.label_type == 'brand':
            return self.picking_id.zpl_preview_barcodes()
        elif self.label_type == 'ready_made':
            return self.picking_id.zpl_preview_ready_made()
        elif self.label_type == 'general':
            return self.picking_id.zpl_preview_dymo()
        else:
            raise UserError("Unknown label type.")
