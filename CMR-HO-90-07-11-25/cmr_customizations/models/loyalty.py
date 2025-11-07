from odoo import fields, models, _,api
from odoo.exceptions import UserError, ValidationError
import ast
from odoo.osv import expression
import base64
import io
import pandas as pd

class LoyaltyRule(models.Model):
    _inherit = 'loyalty.rule'

    serial_ids = fields.Many2many('stock.lot', string="Serial No's", copy=False, domain=[('product_id.item_type', '=', 'inventory')], delete="cascade")
    category_1_ids = fields.Many2many('product.attribute.value', 'cat_1', string='Color', copy=False,
                                      domain=[('attribute_id.name', '=', 'Color')])
    category_2_ids = fields.Many2many('product.attribute.value', 'cat_2', string='Fit', copy=False,
                                      domain=[('attribute_id.name', '=', 'Fit')])
    category_3_ids = fields.Many2many('product.attribute.value', 'cat_3', string='Brand', copy=False,
                                      domain=[('attribute_id.name', '=', 'Brand')])
    category_4_ids = fields.Many2many('product.attribute.value', 'cat_4', string='Pattern', copy=False,
                                      domain=[('attribute_id.name', '=', 'Pattern')])
    category_5_ids = fields.Many2many('product.attribute.value', 'cat_5', string='Border Type', copy=False,
                                      domain=[('attribute_id.name', '=', 'Border Type')])
    category_6_ids = fields.Many2many('product.attribute.value', 'cat_6', string='Border Size', copy=False,
                                      domain=[('attribute_id.name', '=', 'Border Size')])
    category_7_ids = fields.Many2many('product.attribute.value', 'cat_7', string='Size', copy=False,
                                      domain=[('attribute_id.name', '=', 'Size')])
    category_8_ids = fields.Many2many('product.attribute.value', 'cat_8', string='Design', copy=False,
                                      domain=[('attribute_id.name', '=', 'Design')])

    description_1_ids = fields.Many2many('product.aging.line', string='Product Ageing', copy=False)
    description_2_ids = fields.Many2many('product.attribute.value', 'des_2', string='Range', copy=False,
                                         domain=[('attribute_id.name', '=', 'Range')])
    description_3_ids = fields.Many2many('product.attribute.value', 'des_3', string='Collection', copy=False,
                                         domain=[('attribute_id.name', '=', 'Collection')])
    description_4_ids = fields.Many2many('product.attribute.value', 'des_4', string='Fabric', copy=False,
                                         domain=[('attribute_id.name', '=', 'Fabric')])
    description_5_ids = fields.Many2many('product.attribute.value', 'des_5', string='Exclusive', copy=False,
                                         domain=[('attribute_id.name', '=', 'Exclusive')])
    description_6_ids = fields.Many2many('product.attribute.value', 'des_6', string='Print', copy=False,
                                         domain=[('attribute_id.name', '=', 'Print')])
    description_7_ids = fields.Many2many('product.attribute.value', 'des_7', string='Days Ageing', copy=False,
                                         domain=[('attribute_id.name', '=', 'Days Ageing')])
    description_8_ids = fields.Many2many('product.attribute.value', 'des_8', string='Description 8', copy=False)
    loyalty_line_id = fields.One2many('loyalty.line', 'loyalty_id', string='Loyalty Lines')
    ref_product_ids = fields.Many2many('product.product', 'ref_product_id',string="Products", copy=False, domain=[('item_type','=','inventory')])
    type_filter = fields.Selection([('filter', 'Attribute Filter'), ('serial', 'Serial'),('cart','Cart'),('grc','GRC')], string='Filter Type', copy=False)
    product_category_ids = fields.Many2many('product.category', string='Categories')
    day_ageing_slab = fields.Selection([('1', '0-30'), ('2', '30-60'),
                                        ('3', '60-90'), ('4', '90-120'),
                                        ('5', '120-150'), ('6', '150-180'),
                                        ('7', '180-210'), ('8', '210-240'),
                                        ('9', '240-270'), ('10', '270-300'),
                                        ('11', '300-330'), ('12', '330-360')
                                        ])
    loyalty_grc_id = fields.Many2one('grc.master', string="GRC")
    serial_nos = fields.Text(string="Serials")
    serial_import = fields.Binary(string="Serial Import")

    def _get_valid_product_domain(self):
        self.ensure_one()
        domain = []
        if self.product_ids:
            domain = [('id', 'in', self.product_ids.ids)]
        if self.product_category_ids:
            domain = expression.OR([domain, [('categ_id', 'child_of', self.product_category_ids.ids)]])
        if self.product_tag_id:
            domain = expression.OR([domain, [('all_product_tag_ids', 'in', self.product_category_ids.ids)]])
        if self.product_domain and self.product_domain != '[]':
            domain = expression.AND([domain, ast.literal_eval(self.product_domain)])
        return domain

    def action_import_serials(self):
        for record in self:
            # Decode and read file
            file_data = base64.b64decode(record.serial_import)
            try:
                df = pd.read_excel(io.BytesIO(file_data))  # or pd.read_csv()
            except Exception as e:
                raise UserError("Could not read Excel file.")
            extracted_serials = []
            for full_value in df.iloc[:, 0].dropna():
                val_str = str(full_value)
                if "R" in val_str:
                    serial_part = val_str[val_str.index("R"):]
                    extracted_serials.append(serial_part)
            found_lots = self.env['stock.lot'].sudo().search(
                [('name', 'in', extracted_serials), ('product_qty', '>', 0)])
            record.serial_ids = [(6, 0, found_lots.ids)]


    def reset_to_filters(self):
        self.ensure_one()
        self.loyalty_line_id.unlink()
        self.write({
            'category_1_ids' : False,
            'category_2_ids' : False,
            'category_3_ids' : False,
            'category_4_ids' : False,
            'category_5_ids' : False,
            'category_6_ids' : False,
            'category_7_ids' : False,
            'category_8_ids' : False,
            'description_1_ids' : False,
            'description_2_ids' : False,
            'description_3_ids' : False,
            'description_4_ids' : False,
            'description_5_ids' : False,
            'description_6_ids' : False,
            'description_7_ids' : False,
            'description_8_ids' : False,
            'serial_ids' : False,
            'product_ids' : False,
            'product_tag_id' : False,
            'product_category_ids' : False,
            'ref_product_ids' : False,
            'loyalty_grc_id' : False,
        })
    def apply_loyalty_rule(self):
        self.loyalty_line_id.unlink()
        distinct_product_ids = set()
        loyalty_line_vals = []
        matching_lots = self.env['stock.lot']
        if self.type_filter == 'filter':
            self.serial_ids = [(5, 0, 0)]  # Clear serials
            self.product_ids = [(5, 0, 0)]  # Clear products

            matching_lots = self.env['stock.lot'].search_by_loyalty_rule(self)
            self.serial_ids = matching_lots
            serial_names = matching_lots.mapped('name')
            self.serial_nos = ', '.join(serial_names)

            for lot in matching_lots:
                distinct_product_ids.add(lot.product_id.id)
                loyalty_line_vals.append((0, 0, {
                    'lot_id': lot.id,
                    'product_id': lot.product_id.id
                }))

        elif self.type_filter == 'serial':
            self.serial_ids = [(5, 0, 0)]
            self.product_ids = [(5, 0, 0)]
            self.action_import_serials()
            matching_lots = self.serial_ids
            serial_names = matching_lots.mapped('name')
            self.serial_nos = ', '.join(serial_names)

            for lot in matching_lots:
                distinct_product_ids.add(lot.product_id.id)
                loyalty_line_vals.append((0, 0, {
                    'lot_id': lot.id,
                    'product_id': lot.product_id.id
                }))
        elif self.type_filter == 'grc' and self.loyalty_grc_id.name:
            self.serial_ids = [(5, 0, 0)]
            self.serial_nos = False
            grc = self.env['stock.picking'].sudo().search([
                ('stock_type', '=', 'ho_operation'),
                ('name', '=', self.loyalty_grc_id.name)
            ], limit=1)
            serial_lots = self.env['stock.lot']
            for move in grc.move_ids_without_package:
                for lot in move.lot_ids:
                    company_lots = self.env['stock.lot'].sudo().search([
                        ('name', '=', lot.name),
                        ('product_qty', '>', 0),
                        ('product_id.item_type', '=', 'inventory'),
                        ('company_id.nhcl_company_bool', '=', False)
                    ])
                    if company_lots:
                        serial_lots |= company_lots
                        for cl in company_lots:
                            distinct_product_ids.add(cl.product_id.id)
                            loyalty_line_vals.append((0, 0, {
                                'lot_id': cl.id,
                                'product_id': cl.product_id.id
                            }))
            self.serial_ids = [(6, 0, serial_lots.ids)]
            self.serial_nos = ', '.join(serial_lots.mapped('name'))
        self.update({
            'loyalty_line_id': loyalty_line_vals,
            'product_ids': [(6, 0, list(distinct_product_ids))]
        })
        return matching_lots

    @api.model
    def create(self, vals):
        if 'program_id' in vals:
            if vals['program_id'] == False:
                raise UserError(_('Please Save the Promotion,before Get Serial Numbers'))
        res = super(LoyaltyRule, self).create(vals)
        res.apply_loyalty_rule()
        return res



class LoyaltyReward(models.Model):
    _inherit = 'loyalty.reward'

    reward_type = fields.Selection(selection_add=[
        ('discount_on_product', 'Discounted Product')], ondelete={'discount_on_product': 'cascade'})
    discount_product_id = fields.Many2one('product.product', string="Discount On Product")
    product_price = fields.Float('Price')

    @api.depends('reward_type', 'reward_product_id', 'discount_mode', 'reward_product_tag_id',
                 'discount', 'currency_id', 'discount_applicability', 'all_discount_product_ids')
    def _compute_description(self):
        for reward in self:
            reward_string = ""
            if reward.reward_type == 'discount_on_product':
                products = reward.discount_product_id
                if len(products) == 0:
                    reward_string = _('Discount Product')
                elif len(products) == 1:
                    reward_string = _('Discount Product - %s',
                                      reward.discount_product_id.with_context(display_default_code=False).display_name)
                reward.description = reward_string
            else:
                super(LoyaltyReward, reward)._compute_description()

    @api.onchange("discount_applicability")
    def _onchange_discounted_products(self):
        if self.discount_applicability == 'specific':
            for (i, j) in zip(range(0, len(self.program_id.rule_ids)), range(0, len(self.program_id.reward_ids))):
                self.program_id.reward_ids[j].discount_product_ids = self.program_id.rule_ids[i].product_ids


class LoyaltyLine(models.Model):
    _name = 'loyalty.line'

    loyalty_id = fields.Many2one('loyalty.rule',string='Loyalty', copy=False)
    lot_id = fields.Many2one('stock.lot',string='Lot/Serial', copy=False)
    product_id = fields.Many2one('product.product',string='Product', copy=False)


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    is_vendor_return = fields.Boolean(string='Vendor Return', copy=False)

    def button_import_promotion_action(self):
        return {
            "name": _("Import Promotions"),
            "type": "ir.actions.act_window",
            "res_model": "import.promotions.wizard",
            "target": "new",
            "views": [[False, "form"]],
        }


