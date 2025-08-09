# -*- coding: utf-8 -*-
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from markupsafe import Markup


class SetuSalesIncentiveStructureLine(models.Model):
    _name = 'setu.sales.incentive.structure.line'
    _description = 'Sales Incentive Structure Lines'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'incentive_structure_id'

    sequence = fields.Integer(string='Sequence', required=False,
                              help='Sales incentive calculation based sequence.')
    role = fields.Many2one('hr.job',string='Role Of Employee',

                            required=True, help="Role of employee.")
    calculate_based_on = fields.Selection(string='Calculate Based On',
                                          selection=[('sales_order', 'Sales Order'),
                                                     ('product', 'Product'),
                                                     ('category', 'Category'),
                                                     ('pos_order', 'POS Order')],
                                          required=True, default='pos_order',
                                          help="Select the criteria for Sales Incentives Calculation : Sales Order, Product, or Category.")
    target_based_on = fields.Selection(string='Target Based On',
                                       selection=[('quantity', 'Quantity'),
                                                  ('amount', 'Amount'),
                                                  ('gross_margin', 'Gross Margin')],
                                       required=True, default='amount',
                                       help="Select the target for calculating Sales Incentives: Quantity, Amount, or Gross Margin.")
    calculation_method = fields.Selection(string='Calculation Method',
                                          selection=[('fixed_value', 'Fixed value'),
                                                     ('percentage', 'Percentage')],
                                          required=True, default='percentage',
                                          help="Select the calculation method of Sales Incentive : Fixed Value or Percentage.")
    incentive_value = fields.Float(string='Value', required=True, default=0)
    target_value_min = fields.Float(string='Min Target', required=True, default=0)
    target_value_max = fields.Float(string='Max Target', required=True, default=0)
    product_ids = fields.Many2many('product.product', 'product_product_incentive_structure_line_rel',
                                   'structure_line_id', 'product_id', string="Products")
    category_ids = fields.Many2many('product.category', 'product_category_incentive_structure_line_rel',
                                    'structure_line_id', 'category_id', string='Categories')
    sales_team_ids = fields.Many2many(comodel_name='crm.team', string='Sales Team')
    # sales_agent_group_ids = fields.Many2many(comodel_name='setu.agent.group', string='Agent Group')
    incentive_structure_id = fields.Many2one(comodel_name='setu.sales.incentive.structure',
                                             string='Sales Incentive Structure',
                                             required=True)
    company_id = fields.Many2one(comodel_name='res.company', string='Company',
                                 related='incentive_structure_id.company_id', help="Sales incentive apply on company")
    aging_type = fields.Selection(string='Select Aging',
                                  selection=[('product_aging', 'Product Ageing'),
                                             ('day_aging', 'Days Ageing')], default='product_aging',
                                  help="Select the aging type")
    aging_id = fields.Many2one('product.aging.line', string='Product Ageing')
    day_ageing_incentive = fields.Selection([('1', '0-30'), ('2', '30-60'),
                                             ('3', '60-90'), ('4', '90-120'),
                                             ('5', '120-150'), ('6', '150-180'),
                                             ('7', '180-210'), ('8', '210-240'),
                                             ('9', '240-270'), ('10', '270-300'),
                                             ('11', '300-330'), ('12', '330-360')
                                             ])
    # @api.onchange('target_based_on', 'calculate_based_on')
    # def onchange_target_based_on_and_calculate_based_on(self):
    #     """
    #     Author: Gaurav Vipani | Date: 6th Oct, 2023
    #     Purpose: Added restriction incentive does not apply for sales order quantity.
    #
    #     """
    #     if self.target_based_on == 'quantity' and self.calculate_based_on == 'sales_order':
    #         raise UserError(_(" Does not use a sales incentive target based on the quantity of sales orders."))
    #
    # @api.onchange('incentive_value', 'target_value_min', 'target_value_max')
    # def on_change_incentive_value_target_value_min_and_max(self):
    #     """
    #     Author: Gaurav Vipani | Date: 12th Oct, 2023
    #     Purpose: This method will use for set user restriction with negative value.
    #     """
    #     if self.incentive_value < 0 or self.target_value_min < 0 or self.target_value_max < 0:
    #         raise UserError(_("The incentive, target minimum, and target maximum should all be positive."))
    #
    # @api.constrains('target_value_min', 'target_value_max')
    # def constrains_target_value_min_and_max(self):
    #     """
    #     Author: Gaurav Vipani | Date: 12th Oct, 2023
    #     Purpose: This method will use for set user restriction minimum value is not > target maximum value.
    #     """
    #     for rec in self:
    #         if rec.target_value_min > rec.target_value_max or rec.target_value_min == rec.target_value_max:
    #             raise UserError(_("The Minimum Target Value should always be less than the Maximum Target Value."))
    #
    # @api.onchange('calculation_method', 'incentive_value')
    # def onchange_calculation_method_and_incentive_value(self):
    #     """
    #     Author: Gaurav Vipani | Date: 12th Oct, 2023
    #     Purpose: This method will use for set user restriction if calculation method is percentage and incentive value
    #     enter max 100.
    #     """
    #     if self.calculation_method == 'percentage' and self.incentive_value > 100:
    #         raise UserError(_("The Sales Incentive Percentage should always be less than 100."))
    #
    # @api.constrains('role', 'calculate_based_on', 'target_based_on', 'calculation_method', 'incentive_value',
    #                 'target_value_min', 'target_value_max', 'product_ids', 'category_ids', 'sales_person_ids',
    #                 'manager_ids', 'agent_ids')
    # def _check_duplication_sales_incentive_structure_line_rules(self):
    #     """
    #     Author: Gaurav Vipani | Date: 06th Oct, 2023
    #     Purpose: Remove duplication of sales incentive structure rules.
    #     """
    #     for rec in self:
    #         if rec.target_based_on != 'gross_margin':
    #             is_sales_incentive_exists = rec.find_existing_sales_incentive_structure_line() - rec
    #             if is_sales_incentive_exists:
    #                 msg = _("Incentive Line is already exist with below details, Please update "
    #                         "configuration. \n\n Role - {}\n Calculate Based On - {}\n Target Based On - {} \n "
    #                         "Calculation Method - {} \n Incentive Value - {} \n Min. Target Value - {} "
    #                         "\n Max. Target Value - {}".format(dict(rec._fields['role'].selection).get(rec.role),
    #                                                            dict(rec._fields['calculate_based_on'].selection).get(
    #                                                                rec.calculate_based_on),
    #                                                            dict(rec._fields['target_based_on'].selection).get(
    #                                                                rec.target_based_on),
    #                                                            dict(rec._fields['calculation_method'].selection).get(
    #                                                                rec.calculation_method),
    #                                                            rec.incentive_value, rec.target_value_min,
    #                                                            rec.target_value_max))
    #                 if rec.product_ids:
    #                     msg += _(" \nProducts - {}".format(" , ".join(rec.mapped("product_ids").mapped("name"))))
    #                 elif rec.category_ids:
    #                     msg += _(" \nCategories - {}".format(" , ".join(rec.mapped("category_ids").mapped("name"))))
    #                 if rec.sales_team_ids:
    #                     msg += _("\n Sales Teams - {}".format(" , ".join(rec.mapped("sales_team_ids").mapped("name"))))
    #                 # if rec.sales_agent_group_ids:
    #                 #     msg += _("\n Sales Agent Groups - {}".format(
    #                 #         " , ".format(rec.mapped("sales_agent_group_ids").mapped("name"))))
    #                 raise UserError(msg)
    #         if rec.target_based_on == 'gross_margin':
    #             existing_lines = (self.search([('role', '=', rec.role),
    #                                            ('target_based_on', '=', 'gross_margin'),
    #                                            ('calculation_method', '=', rec.calculation_method),
    #                                            '&', '|', ('target_value_min', '<=', rec.target_value_min),
    #                                            ('target_value_min', '>=', rec.target_value_min),
    #                                            '|', ('target_value_max', '<=', rec.target_value_max),
    #                                            ('target_value_max', '>=', rec.target_value_max),
    #                                            ('company_id', '=', rec.company_id.id),
    #                                            ('calculate_based_on', '=', rec.calculate_based_on),
    #                                            ('incentive_structure_id', '=', rec.incentive_structure_id.id)]) -
    #                               self.search([('role', '=', rec.role),
    #                                            ('target_based_on', '=', 'gross_margin'),
    #                                            ('calculation_method', '=', rec.calculation_method),
    #                                            '|', '&', ('target_value_min', '<=', rec.target_value_min),
    #                                            ('target_value_max', '<=', rec.target_value_min),
    #                                            '&', ('target_value_min', '>=', rec.target_value_max),
    #                                            ('target_value_max', '>=', rec.target_value_max),
    #                                            ('company_id', '=', rec.company_id.id),
    #                                            ('calculate_based_on', '=', rec.calculate_based_on),
    #                                            ('incentive_structure_id', '=', rec.incentive_structure_id.id)]))
    #             is_existing_lines = existing_lines - rec
    #             if is_existing_lines:
    #                 msg = _(
    #                     "You Can Not Configure Gross Margin Having Percentage with Similar Target Limit.")
    #                 raise UserError(msg)
    #
    # def find_existing_sales_incentive_structure_line(self):
    #     """
    #     Author: Gaurav Vipani | Date: 06th Oct, 2023
    #     Purpose: This method will use for apply constrains find existing sales incentive
    #     """
    #     self.ensure_one()
    #     domain = [('role', '=', self.role),
    #               ('calculate_based_on', '=', self.calculate_based_on),
    #               ('target_based_on', '=', self.target_based_on),
    #               ('calculation_method', '=', self.calculation_method),
    #               ('company_id', '=', self.company_id.id),
    #               ('incentive_structure_id', '=', self.incentive_structure_id.id),
    #               '|',
    #               '&', ('target_value_min', '<=', self.target_value_min),
    #               ('target_value_max', '>=', self.target_value_min),
    #               '&', ('target_value_min', '<=', self.target_value_max),
    #               ('target_value_max', '>=', self.target_value_max),
    #               ]
    #     # for calculation based on
    #     if self.calculate_based_on == 'product' and self.product_ids:
    #         domain.append(('product_ids', 'in', self.product_ids.ids))
    #     elif self.calculate_based_on == 'category' and self.category_ids:
    #         domain.append(('category_ids', 'in', self.category_ids.ids))
    #     # for role
    #     if self.role in ['sales_person', 'sales_manager']:
    #         domain.append(('sales_team_ids', 'in', self.sales_team_ids.ids))
    #     # else:
    #     #     domain.append(('sales_agent_group_ids', 'in', self.sales_agent_group_ids.ids))
    #     return self.search(domain, limit=1)
    #
    # def write(self, vals):
    #     """
    #     Author: Gaurav Vipani | Date: 17th Oct,2023
    #     Purpose: This method will use for if user update some fields value then field value message post to its parent model.
    #     """
    #     sales_incentive_structure_id = self.incentive_structure_id
    #     msg = Markup("<b>Rule has been updated.</b><ul><br/>")
    #     for rec in self:
    #         if 'role' in vals:
    #             role = dict(rec._fields['role'].selection)
    #             msg += Markup(
    #                 _("<b>Role :</b> {} <b>-></b> {}<br/>".format(role.get(rec.role), role.get(vals.get("role")))))
    #
    #         if 'sales_team_ids' in vals:
    #             new_team = rec.env["crm.team"].browse(vals.get("sales_team_ids")[0][1])
    #             new_team = " , ".join(new_team.mapped("name"))
    #             msg += Markup(_("<b>Teams : </b> {} <b>-></b> {}<br/>".format(
    #                 " , ".join(rec.mapped("sales_team_ids").mapped("name")),
    #                 new_team)))
    #
    #         # if 'sales_agent_group_ids' in vals:
    #         #     new_agent = rec.env["setu.agent.group"].browse(vals.get("sales_agent_group_ids")[0][1])
    #         #     new_agent = " , ".join(new_agent.mapped("name"))
    #         #     msg += Markup(_("<b>Agent Group : </b> {} <b>-></b> {}<br/>".format(
    #         #         " , ".join(rec.mapped("sales_agent_group_ids").mapped("name")),
    #         #         new_agent)))
    #
    #         if 'calculate_based_on' in vals:
    #             calculate_based = dict(rec._fields['calculate_based_on'].selection)
    #             msg += Markup(_("<b>Calculate Based On :</b> {} <b>-></b> {}<br/>".format(
    #                 calculate_based.get(rec.calculate_based_on),
    #                 calculate_based.get(
    #                     vals.get('calculate_based_on')))))
    #         if 'target_based_on' in vals:
    #             target_based = dict(rec._fields['target_based_on'].selection)
    #             msg += Markup(
    #                 _("<b>Target Based On :</b> {} <b>-></b> {}<br/>".format(target_based.get(rec.target_based_on),
    #                                                                          target_based.get(
    #                                                                              vals.get('target_based_on')))))
    #         if 'calculation_method' in vals:
    #             calculation_method = dict(rec._fields['calculation_method'].selection)
    #             msg += Markup(_("<b>Calculation Method :</b> {} <b>-></b> {}<br/>".format(
    #                 calculation_method.get(rec.calculation_method),
    #                 calculation_method.get(
    #                     vals.get('calculation_method')))))
    #
    #         if 'incentive_value' in vals:
    #             msg += Markup(_("<b>Incentive Value :</b> {} <b>-></b> {}<br/>".format(rec.incentive_value,
    #                                                                                    vals.get('incentive_value'))))
    #
    #         if 'target_value_min' in vals:
    #             msg += Markup(_("<b>Minimum Target Value :</b> {} <b>-></b> {}<br/>".format(rec.target_value_min,
    #                                                                                         vals.get(
    #                                                                                             'target_value_min'))))
    #
    #         if 'target_value_max' in vals:
    #             msg += Markup(_("<b>Maximum Target Value :</b> {} <b>-></b> {}<br/>".format(rec.target_value_max,
    #                                                                                         vals.get(
    #                                                                                             'target_value_max'))))
    #
    #         if 'product_ids' in vals:
    #             new_products = rec.env["product.product"].browse(vals.get("product_ids")[0][1])
    #             new_products = " , ".join(new_products.mapped("name"))
    #             msg += Markup(_("<b>Products :</b> {} <b>-></b> {}<br/>".format(
    #                 " , ".join(rec.mapped("product_ids").mapped("name")),
    #                 new_products)))
    #         if 'category_ids' in vals:
    #             new_category = rec.env["product.category"].browse(vals.get("category_ids")[0][1])
    #             new_category = " , ".join(new_category.mapped("name"))
    #             msg += Markup(_("<b>Categories :</b> {} <b>-></b> {}<br/>".format(
    #                 " , ".join(rec.mapped("category_ids").mapped("name")),
    #                 new_category)))
    #     # message post to sales incentive structure
    #     sales_incentive_structure_id.message_post(body=msg)
    #     return super(SetuSalesIncentiveStructureLine, self).write(vals)
    #
    # @api.onchange('target_based_on', 'calculation_method', 'target_value_max', 'target_value_min')
    # def on_change_target_based_on_to_gross_margin(self):
    #     if self.calculation_method == 'percentage' and self.target_based_on == 'gross_margin' and (
    #             self.target_value_max > 100 or self.target_value_min > 100):
    #         raise UserError(
    #             _("For rules with a percentage gross margin, the minimum and maximum target values must be in percentages and not exceed 100."))
