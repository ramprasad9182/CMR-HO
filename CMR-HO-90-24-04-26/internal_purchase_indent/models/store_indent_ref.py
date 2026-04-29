from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
import re
from datetime import timedelta
from odoo.tools.float_utils import float_compare

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


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"


    divison = fields.Many2one('product.category', string="Divison", compute="_compute_categories", store=True)
    section = fields.Many2one('product.category', string="Section", compute="_compute_categories", store=True)
    department = fields.Many2one('product.category', string="Department", compute="_compute_categories", store=True)
    brick = fields.Many2one('product.category', string="Brick", compute="_compute_categories", store=True)
    issued_qty = fields.Float(string="Issued Qty",compute="_compute_issued_qty",store=False)
    diff_qty = fields.Float(string="Balance Qty", compute="_compute_balance_status", store=False)
    status = fields.Selection([('pending', 'Pending'),('partial', 'Partial'),('done', 'Done')],
        string="Status",compute="_compute_balance_status",store=False)
    nhcl_onhand_qty = fields.Float(string="HO Onhand Qty", compute="_compute_nhcl_onhand_qty")
    pending_incoming_qty = fields.Float(string="PO Qty", compute="_compute_pending_incoming_qty")

    def _compute_pending_incoming_qty(self):
        main_company = self.env['res.company'].search([
            ('nhcl_company_bool', '=', True)
        ], limit=1)
        if not main_company:
            for rec in self:
                rec.pending_incoming_qty = 0.0
            return
        products = self.mapped('product_id').ids
        grouped = self.env['purchase.order.line'].read_group(
            [
                ('product_id', 'in', products),
                ('company_id', '=', main_company.id),
                ('order_id.state', 'in', ['purchase', 'done']),
            ],
            ['product_id', 'product_qty', 'qty_received'],
            ['product_id']
        )
        data = {
            g['product_id'][0]: g['product_qty'] - g['qty_received']
            for g in grouped
        }
        for rec in self:
            rec.pending_incoming_qty = data.get(rec.product_id.id, 0.0)

    def _compute_nhcl_onhand_qty(self):
        nhcl_company = self.env['res.company'].sudo().search([
            ('nhcl_company_bool', '=', True)
        ])
        for rec in self:
            if rec.product_id and nhcl_company:
                product = rec.product_id.with_company(nhcl_company)
                rec.nhcl_onhand_qty = product.qty_available
            else:
                rec.nhcl_onhand_qty = 0.0

    @api.depends('product_id')
    def _compute_issued_qty(self):
        StoreIndents = self.env['store.indent.refernce']

        for line in self:
            issued_qty = 0.0

            sale_orders = self.env['sale.order'].search([
                ('nhcl_sale_type', '=', 'store'),
                ('nhcl_indent_id', '=', line.order_id.id),
                ('state', '=', 'sale')
            ])

            if sale_orders:
                sol = StoreIndents.sudo().search([
                    ('so_order_id', 'in', sale_orders.ids),
                    ('product_id', '=', line.product_id.id)
                ])
                issued_qty = sum(sol.mapped('allocated_quantity'))
            line.issued_qty = issued_qty

    @api.depends('product_qty', 'issued_qty')
    def _compute_balance_status(self):
        for line in self:
            issued = line.issued_qty or 0.0
            qty = line.product_qty or 0.0
            diff = qty - issued
            line.diff_qty = diff
            if float_compare(issued, 0.0, precision_rounding=2) == 0:
                line.status = 'pending'
            elif float_compare(issued, qty, precision_rounding=2) < 0:
                line.status = 'partial'
            else:
                line.status = 'done'

    @api.depends('product_id')
    def _compute_categories(self):
        for rec in self:
            categ = rec.product_id.categ_id

            if not categ:
                continue

            if not rec.brick:
                rec.brick = categ.id

            parent = categ.parent_id
            if parent and not rec.department:
                rec.department = parent.id

            parent2 = parent.parent_id if parent else False
            if parent2 and not rec.section:
                rec.section = parent2.id

            parent3 = parent2.parent_id if parent2 else False
            if parent3 and not rec.divison:
                rec.divison = parent3.id

