from odoo import models, fields, api,_



class StorePosOrderLine(models.Model):
    _name = 'store.pos.order.line'
    _description = 'Store Pos Order Line'

    store_pos_ref = fields.Char(string="Ref")
    product_name = fields.Char(string="Product Name")
    lot_name = fields.Char(string="Lot Name")
    quantity = fields.Integer(string="Quantity")
    amount = fields.Float(string="Amount")
    reward_name = fields.Char(string="Reward Name")
    company_name = fields.Char(string="Company")
    is_used = fields.Boolean(string="Is Used")
    vendor_return_disc_price = fields.Float(string="Discount Price")
