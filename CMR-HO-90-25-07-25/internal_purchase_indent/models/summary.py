from odoo import models, fields, api,_
from odoo.exceptions import ValidationError, UserError



class ProductSummary(models.Model):
    _name = 'product.summary'

    select = fields.Boolean(string="Select")

    product_id = fields.Many2one("product.product",string="Product")
    pi_quantity = fields.Float(string="Total PI Qunatity")
    quantity_to_raise = fields.Float(string="Quantity To Raise")
    on_hand = fields.Float(string ="ON Hand Quantity",)
    forecast_quantity = fields.Float(string="Forecast Quantity",)
    incoming_quantity = fields.Float(string="Incoming Quantity",)
    outgoing_quantity = fields.Float(string="Outgoing Quantity",)
    as_of_date = fields.Datetime(string="As of Date")
    indent_sum_id = fields.Many2one('internal.purchase.indent', string="Indent")


