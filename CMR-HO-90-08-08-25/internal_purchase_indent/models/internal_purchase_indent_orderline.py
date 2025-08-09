from odoo import models, fields


class InternalPurchaseIndentOrderLine(models.Model):
    _name = 'internal.purchase.indent.orderline'
    _description = 'Internal Purchase Indent Line'


    indent_id = fields.Many2one('internal.purchase.indent', string="Indent")
    purchase_indent_id = fields.Many2one('purchase.order',string="Source Purchase Indent",related="po_line_id.order_id")
    po_line_id = fields.Many2one('purchase.order.line', string="PO Line")
    product_id = fields.Many2one('product.product', string="Product",related="po_line_id.product_id")
    quantity = fields.Float(string="PI Quantity",related="po_line_id.product_qty")
    store_id = fields.Many2one('res.company', string="Company",related='po_line_id.order_id.company_id')

    state = fields.Selection(
        related="po_line_id.state",
        string="State",
        readonly=True
    )


