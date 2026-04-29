from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    """Inherited product.template class to add fields and functions"""
    _inherit = 'product.template'

    nhcl_product_type = fields.Selection([('unbranded', 'Un-Branded'), ('branded', 'Branded'),('others', 'Others')],
                                         string='Brand Type')
    nhcl_type = fields.Selection(
        [('advertisement', 'Advertisement'), ('ho_operation', 'HO Operation'), ('others', 'Others')],
        string='Article Type', default='ho_operation')
    serial_no = fields.Char(string="Serial No")
    product_description = fields.Html(string="Product Description")
    web_product = fields.Char(string="Website  Product Name")
    segment = fields.Selection([('apparel','Apparel'), ('non_apparel','Non Apparel'), ('others','Others')], string="Segment", copy=False, tracking=True)
    item_type = fields.Selection([('inventory', 'Inventory'), ('non_inventory', 'Non Inventory')], string="Item Type",
                                 copy=False, tracking=True)
    allow_negative_stock = fields.Boolean(
        help="If this option is not active on this product nor on its "
             "product category and that this product is a stockable product, "
             "then the validation of the related stock moves will be blocked if "
             "the stock level becomes negative with the stock move.",
    )

    @api.model
    def _create_variant_ids(self):
        res = super(ProductTemplate, self)._create_variant_ids()

        PurchaseLine = self.env['purchase.order.line']
        SaleLine = self.env['sale.order.line']

        for template in self:
            all_variants = template.with_context(active_test=False).product_variant_ids

            po_products = PurchaseLine.search([
                ('product_id', 'in', all_variants.ids)
            ]).mapped('product_id')

            so_products = SaleLine.search([
                ('product_id', 'in', all_variants.ids)
            ]).mapped('product_id')

            protected_variants = all_variants.filtered(lambda v:
                                                       v.qty_available > 0 or
                                                       v.stock_move_ids or
                                                       v in po_products or
                                                       v in so_products
                                                       )

            archived_protected = protected_variants.filtered(lambda v: not v.active)
            if archived_protected:
                archived_protected.write({'active': True})

        return res

    @api.onchange('categ_id')
    def creating_product_name_from_categ(self):
        if self.categ_id and self.nhcl_type == 'ho_operation':
            display_name_modified = self.categ_id.display_name.replace(' / ', '-')
            self.name = display_name_modified

    @api.constrains('product_tag_ids')
    def constrains_product_tags(self):
        for rec in self:
            if len(rec.product_tag_ids) > 1:
                raise ValidationError("You have added more than 1 tags, it is not valid.")

    @api.model_create_multi
    def create(self, vals_list):
        # Step 1: collect names to validate
        names_to_check = [
            vals.get('name')
            for vals in vals_list
            if vals.get('detailed_type') == 'product' and vals.get('name')
        ]
        if names_to_check:
            existing_products = self.env['product.template'].search([
                ('name', 'in', names_to_check),
                ('detailed_type', '=', 'product')
            ])
            existing_names = set(existing_products.mapped('name'))
            for vals in vals_list:
                if (
                        vals.get('detailed_type') == 'product'
                        and vals.get('name') in existing_names
                ):
                    raise ValidationError(_("A storable product called '%s' already exists.") % vals['name'])
        for vals in vals_list:
            vals['available_in_pos'] = True
        return super().create(vals_list)

    @api.constrains('tracking')
    def check_product_tracking(self):
        for temp in self:
            if temp.detailed_type == 'product' and temp.tracking == 'none':
                raise ValidationError('This product is storable but tracking is set to None.')

    def write(self, vals):
        if vals.get('detailed_type') == 'product' and vals.get('name'):
            existing_product = self.env['product.template'].search([
                ('name', '=', vals['name']),
                ('detailed_type', '=', 'product')
            ], limit=1)
            if existing_product:
                raise ValidationError(_("A storable product called '%s' already exists.") % vals['name'])
        if 'attribute_line_ids' in vals and not self.env.user.has_group('cmr_customizations.group_allow_delete_values'):
            for command in vals['attribute_line_ids']:
                if len(command) == 3 and isinstance(command[2], dict):
                    line_vals = command[2]
                    if 'value_ids' in line_vals:
                        for val_command in line_vals['value_ids']:
                            if not isinstance(val_command, list):
                                continue
                            if val_command[0] == 3:  # remove a single value
                                raise ValidationError(_("You are not allowed to remove existing attribute values."))
                            elif val_command[0] == 5:  # clear all values
                                raise ValidationError(_("You are not allowed to remove existing attribute values."))
                            elif val_command[0] == 6:  # replace all values
                                existing_ids = set(
                                    self.env['product.template.attribute.value'].browse(val_command[2]).ids)
                                raise ValidationError(_("You are not allowed to remove existing attribute values."))
        return super(ProductTemplate, self).write(vals)

