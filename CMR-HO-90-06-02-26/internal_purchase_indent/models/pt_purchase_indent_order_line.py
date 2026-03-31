from odoo import models, fields, api


class PTInternalPurchaseIndentOrderLine(models.Model):
    _name = 'pt.upload.indent.orderline'
    _description = 'PT Upload Purchase Indent Line'


    pt_indent_id = fields.Many2one('pt.upload.indent', string="Indent")
    pt_purchase_indent_id = fields.Many2one('purchase.order',string="Source Purchase Indent",related="pt_po_line_id.order_id")
    pt_po_line_id = fields.Many2one('purchase.order.line', string="PO Line")
    product_id = fields.Many2one('product.product', string="Product",related="pt_po_line_id.product_id")
    quantity = fields.Float(string="PI Quantity",related="pt_po_line_id.product_qty")
    # icode_barcode = fields.Char(
    #     string="ICode Barcode",
    #     related="pt_po_line_id.product_id.icode_barcode",
    #     store=True,
    #     readonly=True
    # )
    icode_barcode = fields.Char(string="Barcode")

    store_id = fields.Many2one('res.company', string="Company",related='pt_po_line_id.order_id.company_id')

    state = fields.Selection(
        related="pt_po_line_id.state",
        string="State",
        readonly=True
    )
    brand = fields.Char(string="Brand")
    size = fields.Char(string="Size")
    design = fields.Char(string="Design")
    fit = fields.Char(string="Fit")
    colour = fields.Char(string="Colour")
    mrp = fields.Char(string="MRP")
    rsp = fields.Char(string="RSP")
    des5 = fields.Char(string="Des5")
    des6 = fields.Char(string="Des6")


