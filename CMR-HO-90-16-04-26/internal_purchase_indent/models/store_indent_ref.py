from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import re
from datetime import timedelta

class StoreIndents(models.Model):
    _inherit = "store.indent.refernce"

    divison = fields.Many2one('product.category', string="Divison", compute="_compute_categories", store=True)
    section = fields.Many2one('product.category', string="Section", compute="_compute_categories", store=True)
    department = fields.Many2one('product.category', string="Department", compute="_compute_categories", store=True)
    brick = fields.Many2one('product.category', string="Brick", compute="_compute_categories", store=True)
    indent_id = fields.Many2one('purchase.order', string="Indent No.", compute="_compute_categories", store=True)

    @api.depends('so_order_id','product_id.categ_id')
    def _compute_categories(self):
        for rec in self:
            if rec.so_order_id.nhcl_indent_id:
                rec.indent_id = rec.so_order_id.nhcl_indent_id.id
            categ = rec.product_id.categ_id
            # Default values
            rec.brick = categ.id if categ else False
            rec.department = False
            rec.section = False
            rec.divison = False
            if categ:
                parent = categ.parent_id
                if parent:
                    rec.department = parent.id
                    parent2 = parent.parent_id
                    if parent2:
                        rec.section = parent2.id
                        parent3 = parent2.parent_id
                        if parent3:
                            rec.divison = parent3.id