# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class SetuSalesIncentiveStructure(models.Model):
    _name = 'setu.sales.incentive.structure'
    _description = 'Sales Incentive Structure'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date'

    name = fields.Char(string="Name Of Sales Incentive Structure", tracking=True, required=True,
                       help="Name of sales incentive structure.")
    start_date = fields.Date(string="Start Date", required=True, tracking=True,
                             help="Start date of sales incentive structure.")
    end_date = fields.Date(string="End Date", required=True, tracking=True,
                           help="End date of sales incentive structure.")
    incentive_calculation_based_on = fields.Selection(
        selection=[('sale_order', 'Incentive based on confirmed orders'),
                   ('invoice', 'Incentive based on validated orders'),
                   ('payment', 'Incentive based on paid orders'),
                   ('pos_order', 'Incentive based on POS orders')],
        string="Calculation Strategy", default="pos_order", tracking=True, required=True,
        help="Choose a Sales Incentive Calculation strategy, which can be based on either 'Confirmation Sales Orders',"
             " or 'Generated Invoices from Sales Orders', or 'Payments of Sales Orders'.")
    incentive_account_id = fields.Many2one(comodel_name="account.account", domain=[('account_type', '=', 'expense')],
                                           string="Incentive Account", tracking=True,
                                           help="Select the account for Sales Incentive Invoice Entry.")
    company_id = fields.Many2one(comodel_name="res.company", string="Company", tracking=True, required=True,
                                 default=lambda self: self.env.company,
                                 help="Sales incentives is applicable to this company.")
    warehouse_ids = fields.Many2many(comodel_name='stock.warehouse', string='Warehouse',
                                     help="Sales incentive calculation rules apply based on warehouse selection.")
    incentive_structure_line_ids = fields.One2many(comodel_name='setu.sales.incentive.structure.line',
                                                   inverse_name='incentive_structure_id',
                                                   string='Sales Incentive Structure Lines', required=False,
                                                   help='Sales incentive rules to be apply.', copy=True)
    sequence = fields.Integer(string="Sequence", default=10)
    incentive_state = fields.Selection(selection=[('draft', 'Draft'), ('confirmed', 'Confirmed'), ('closed', 'Closed')],
                                       default='draft', string="Incentive State", copy=False)
    incentive_structure_type = fields.Selection(selection=[('flat', 'Flat'), ('tiered', 'Tiered')], default="tiered",
                                                string="Incentive Structure Type")

    def find_incentive_structure(self, company_id, date, warehouse_id):
        """
        Author: Gaurav Vipani | Date: 26th Oct, 2023
        Purpose: This method will use for find incentive based on start date, end date & calculation based on.
        """
        domain = [('company_id', '=', company_id.id), ("start_date", "<=", date), ("end_date", ">=", date),
                  "|", ("warehouse_ids", "=", False), ("warehouse_ids", "in", warehouse_id.ids),
                  ("incentive_state", "=", "confirmed")]
        sales_incentive_structure_ids = self.search(domain, order='sequence asc')
        return sales_incentive_structure_ids and sales_incentive_structure_ids[0] or sales_incentive_structure_ids

    def recompute_incentive(self):
        """
        Author: Gaurav Vipani | Date: 26th Oct, 2023
        Purpose: This method will be used for recompute incentive based on structure.
        """
        order_ids = self.env["sale.order"].search(
            [('date_order', '>=', self.start_date), ('date_order', '<=', self.end_date)])
        if order_ids:
            self.env["setu.sales.incentive"].with_context(calculate_from_cron=True).recompute_incentive(
                order_ids=order_ids)

    def action_confirm_incentive_structure(self):
        self.incentive_state = 'confirmed'

    def action_close_incentive_structure(self):
        self.incentive_state = 'closed'
