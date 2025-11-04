from odoo import models, fields, api,_



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
    indent_sum_id = fields.Many2one('internal.purchase.indent', string="Indent", ondelete="cascade")

    s_no = fields.Integer(string="S.No", compute="_compute_s_no")

    @api.depends('indent_sum_id')
    def _compute_s_no(self):
        for rec in self.indent_sum_id:
            for index, line in enumerate(rec.product_summary_ids, start=1):
                line.s_no = index




class PTProductSummary(models.Model):
    _name = 'pt.product.summary'

    select = fields.Boolean(string="Select")
    product_id = fields.Many2one("product.product",string="Product")
    pi_quantity = fields.Float(string="Total PI Qunatity")
    as_of_date = fields.Datetime(string="As of Date")
    pt_indent_sum_id = fields.Many2one('pt.upload.indent', string="Indent")
    icode_barcode = fields.Char(string="ICode Barcode")



