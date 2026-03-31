from odoo import models, fields,api


class InternalPurchaseIndentOrderLine(models.Model):
    _name = 'internal.purchase.indent.orderline'
    _description = 'Internal Purchase Indent Line'


    indent_id = fields.Many2one('internal.purchase.indent', string="Indent", ondelete="cascade")
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
    s_no = fields.Integer(string="S.No", compute="_compute_s_no")

    @api.depends('indent_id')
    def _compute_s_no(self):
        for rec in self.indent_id:
            for index, line in enumerate(rec.order_line_ids, start=1):
                line.s_no = index

