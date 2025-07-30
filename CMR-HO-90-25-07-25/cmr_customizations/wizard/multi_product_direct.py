from odoo import models, fields, api


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
