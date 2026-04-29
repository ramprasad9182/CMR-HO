from odoo import models,fields,api,_
import requests
from datetime import datetime, time
import pytz

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict


class NhclDailySaleDetailedReport(models.Model):
    _name = 'nhcl.daily.sale.detailed.report'
    _description = "Article Wise Sale Detailed Report"
    _rec_name = 'name'

    def _default_from_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(3, 30, 0))
        )


    def _default_to_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(18, 30, 0))
        )


    from_date = fields.Datetime(
        string='From Date',
        default=_default_from_date
    )
    to_date = fields.Datetime(
        string='To Date',
        default=_default_to_date
    )
    nhcl_daily_sale_detailed_report_ids = fields.One2many('nhcl.daily.sale.detailed.report.line', 'nhcl_daily_sale_detailed_report_id')
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company')
    name = fields.Char('Name',default="Article Wise Detailed Sale Report")
    config_id = fields.Many2one('pos.config', string='Terminal')
    cashier_id = fields.Many2one('hr.employee', string='Cashier')
    family = fields.Many2one(
        'product.category',
        string='Family',
        domain=[('parent_id', '=', False)]
    )

    category = fields.Many2one(
        'product.category',
        string='Category',
        domain="[('parent_id', '=', family)]"
    )

    nhcl_class = fields.Many2one(
        'product.category',
        string='Class',
        domain="[('parent_id', '=', category)]"
    )

    brick = fields.Many2one(
        'product.category',
        string='Brick',
        domain="[('parent_id', '=', nhcl_class)]"
    )
    aging = fields.Many2one('product.aging.line', string='Aging Code')
    brand = fields.Many2one('product.attribute.value', string='Brand', copy=False,
                            domain=[('attribute_id.name', '=', 'Brand')])
    product_id = fields.Many2one('product.product', string='Product')
    price_point = fields.Float(string="Price Point")

    total_order_quantity = fields.Float(compute="_compute_nhcl_show_totals", string='Total Bill Qty')
    total_mrp = fields.Float(compute="_compute_nhcl_show_totals", string='Total MRP')
    total_rsp_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total RSP')
    total_tax_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Tax')
    total_sale_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Sale')
    total_net_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Net')
    total_discount_amount = fields.Float(compute="_compute_nhcl_show_totals", string='Total Discount')


    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.nhcl_daily_sale_detailed_report_ids
            rec.total_order_quantity = sum(lines.mapped('bill_qty'))
            rec.total_mrp = sum(lines.mapped('mrp'))
            rec.total_rsp_amount = sum(lines.mapped('rsp_amount'))
            rec.total_tax_amount = sum(lines.mapped('tax_amount'))
            rec.total_sale_amount = sum(lines.mapped('sale_amount'))
            rec.total_net_amount = sum(lines.mapped('net_amount'))
            rec.total_discount_amount = sum(lines.mapped('discount'))

    # ----------------------------
    # Onchange methods
    # ----------------------------
    @api.onchange('family')
    def _onchange_family(self):
        self.category = False
        self.nhcl_class = False
        self.brick = False

    @api.onchange('category')
    def _onchange_category(self):
        self.nhcl_class = False
        self.brick = False

    @api.onchange('nhcl_class')
    def _onchange_nhcl_class(self):
        self.brick = False

    @api.model
    def _default_nhcl_stores(self):
        stores = self.env['nhcl.ho.store.master'].search([
            ('nhcl_store_type', '!=', 'ho'),
            ('nhcl_active', '=', True)
        ])
        return stores.mapped('nhcl_store_name').ids

    # def default_get(self, fields_list):
    #     res = super(NhclDailySaleDetailedReport, self).default_get(fields_list)
    #     replication_data = []
    #     ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
    #     for i in ho_store_id:
    #         vals = {
    #             'nhcl_store_id': i.nhcl_store_name.id,
    #         }
    #         replication_data.append((0, 0, vals))
    #     res.update({'nhcl_store_id': replication_data})
    #     return res

    def daily_sale_detailed_report(self):
        self.nhcl_daily_sale_detailed_report_ids.unlink()

        user_tz = self.env.user.tz or 'UTC'
        local = pytz.timezone(user_tz)

        from_date = fields.Datetime.to_datetime(self.from_date)
        to_date = fields.Datetime.to_datetime(self.to_date)

        for store in self.nhcl_store_id:

            # Base domain
            domain = [
                ('order_id.date_order', '>=', from_date),
                ('order_id.date_order', '<=', to_date),
                ('order_id.company_id.name', '=', store.nhcl_store_name.name),
                ('order_id.state', '=', 'invoiced'),
                ('product_id.detailed_type', '=', 'product'),
                ('order_id.refunded_orders_count', '=', 0)
            ]

            # Terminal filter
            if self.config_id:
                domain.append(
                    ('order_id.config_id', '=', self.config_id.id)
                )

            # Cashier filter
            if self.cashier_id:
                domain.append(
                    ('order_id.employee_id', '=', self.cashier_id.id)
                )

            # Product filter
            if self.product_id:
                domain.append(
                    ('product_id', '=', self.product_id.id)
                )

            # Brick filter
            elif self.brick:
                domain.append(
                    ('product_id.categ_id', '=', self.brick.id)
                )

            # Class filter
            elif self.nhcl_class:
                domain.append(
                    ('product_id.categ_id.parent_id', '=', self.nhcl_class.id)
                )

            # Category filter
            elif self.category:
                domain.append(
                    ('product_id.categ_id.parent_id.parent_id', '=', self.category.id)
                )

            # Family filter
            elif self.family:
                domain.append(
                    ('product_id.categ_id.parent_id.parent_id.parent_id', '=', self.family.id)
                )

            # Aging filter
            if self.aging:
                domain.append(
                    ('lot_ids.description_1', '=', self.aging.id)
                )

            # Brand filter
            if self.brand:
                domain.append(
                    ('product_id.product_template_attribute_value_ids.product_attribute_value_id', '=', self.brand.id)
                )

            # Price Point filter


            pos_lines = self.env['pos.order.line'].search(domain)

            report_vals = []
            lot_cache = {}

            for line in pos_lines:
                product = line.product_id
                categ = product.categ_id
                if self.price_point and line.price_unit != self.price_point:
                    continue
                serial_id = False
                if line.lot_ids:
                    lot_name = line.lot_ids.name
                    if lot_name:
                        if lot_name not in lot_cache:
                            lot_cache[lot_name] = self.env['stock.lot'].search(
                                [
                                    ('name', '=', lot_name),
                                    ('company_id.name', '=', store.nhcl_store_name.name)
                                ],
                                limit=1
                            )
                        serial_id = lot_cache[lot_name]

                family = ''
                category = ''
                class_name = ''
                brick = ''

                if categ:
                    brick = categ.complete_name or ''

                    if categ.parent_id:
                        class_name = categ.parent_id.complete_name or ''

                        if categ.parent_id.parent_id:
                            category = categ.parent_id.parent_id.complete_name or ''

                            if categ.parent_id.parent_id.parent_id:
                                family = categ.parent_id.parent_id.parent_id.complete_name or ''

                store_master = self.env['nhcl.ho.store.master'].browse(store.id)

                report_vals.append({
                    'family_name': family,
                    'category_name': category,
                    'class_name': class_name,
                    'brick_name': brick,
                    'product_name': product.name,
                    'hsn': product.l10n_in_hsn_code or '',
                    'uom': product.uom_id.name or '',
                    'promo': line.nhcl_reward_id,
                    'customer_note': line.order_id.note,

                    'colour': serial_id.category_1.name if serial_id and serial_id.category_1 else '',
                    'aging': serial_id.description_1.name if serial_id and serial_id.description_1 else '',
                    'fit': serial_id.category_2.name if serial_id and serial_id.category_2 else '',
                    'design': serial_id.category_8.name if serial_id and serial_id.category_8 else '',
                    'size': serial_id.category_7.name if serial_id and serial_id.category_7 else '',
                    'brand': serial_id.category_3.name if serial_id and serial_id.category_3 else '',
                    'barcode': serial_id.ref if serial_id else '',

                    'bill_qty': line.qty,
                    'mrp': line.nhcl_mr_price,
                    'rsp_amount': line.price_unit,

                    'tax_persent': ', '.join(
                        line.tax_ids_after_fiscal_position.mapped('name')
                    ) if line.tax_ids_after_fiscal_position else '',

                    'tax_amount': line.price_subtotal_incl - line.price_subtotal,
                    'sale_amount': line.price_subtotal_incl,
                    'net_amount': line.price_subtotal_incl,
                    'discount': line.order_id.amount_discount,

                    'config_id': line.order_id.config_id.id,
                    'cashier_id': line.order_id.user_id.id,
                    'nhcl_bill_receipt': line.order_id.pos_reference,
                    'nhcl_date_order': line.order_id.date_order,

                    'nhcl_store_id': store_master.id,
                    'nhcl_daily_sale_detailed_report_id': self.id
                })

            if report_vals:
                self.env['nhcl.daily.sale.detailed.report.line'].create(report_vals)

    def action_view_detailed_report(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Daily Sale Detailed Report',
            'res_model': 'nhcl.daily.sale.detailed.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_daily_sale_detailed_report_id', '=', self.id)],
            'context': {
                'default_nhcl_daily_sale_detailed_report_id': self.id
            }
        }


    def action_to_reset(self):
        self.write({
            'nhcl_store_id': False,
            'from_date': False,
            'to_date': False,
            'family': False,
            'category': False,
            'nhcl_class': False,
            'brick': False,
            'product_id': False,
            'price_point': False,
            'config_id': False,
            'cashier_id': False,
            'aging': False,
            'brand': False,
        })
        self.nhcl_daily_sale_detailed_report_ids.unlink()

class NhclDailySaleDetailedReportLine(models.Model):
    _name = 'nhcl.daily.sale.detailed.report.line'
    _description = "nhcl daily sale detailed report line"

    nhcl_daily_sale_detailed_report_id = fields.Many2one('nhcl.daily.sale.detailed.report', string="Daily Sale Report")
    nhcl_store_id = fields.Many2one('nhcl.ho.store.master', string='Company')
    config_id = fields.Many2one('pos.config', string='Terminal')
    cashier_id = fields.Many2one('hr.employee', string='Cashier')
    nhcl_bill_receipt = fields.Char(string="Bill Receipt")
    family_name = fields.Char(string="Family")
    category_name = fields.Char(string="Category")
    class_name = fields.Char(string="Class")
    brick_name = fields.Char(string="Brick")
    product_name = fields.Char(string="Product")
    hsn = fields.Char(string="HSN")
    colour = fields.Char(string="Colour")
    aging = fields.Char(string="Aging")
    fit = fields.Char(string="Fit")
    design = fields.Char(string="Design")
    size = fields.Char(string="Size")
    brand = fields.Char(string="Brand")
    barcode = fields.Char(string="Barcode")
    bill_qty = fields.Float(string="BillQty")
    mrp = fields.Float(string="MRP")
    tax_persent = fields.Char(string="Tax Persent")
    tax_amount = fields.Float(string="Tax Amount")
    sale_amount = fields.Float(string="Sale Value")
    rsp_amount = fields.Float(string="RSP")
    net_amount = fields.Float(string="Net Amt")
    nhcl_date_order = fields.Datetime(string="Date")
    uom = fields.Char(string="UOM")
    discount = fields.Float(string="Discount")
    promo = fields.Char(string="Promo")
    customer_note = fields.Char(string="Customer Note")