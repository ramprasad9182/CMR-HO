from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductCategory(models.Model):
    _inherit = 'product.category'

    max_num = fields.Integer(string="Max Number")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    product_category_margin_ids = fields.One2many('product.category.margin.line','product_category_margin_id')
    is_confirm = fields.Boolean(string="Confirm", default=False)
    margin_line_ids = fields.One2many(
        'product.category.margin.line', 'product_category_margin_id',
        string="Margin Lines"
    )
    product_category_mrp_ids = fields.One2many('product.category.mrp.line','product_category_mrp_id')
    user_ids = fields.Many2many('res.users', required=True, string='Users', copy=False)
    zone_id = fields.Many2one('placement.master.data', required=True, string='Zone', copy=False)

    # Function to check level restriction
    @api.constrains('parent_id')
    def _check_category_level(self):
        for category in self:
            if len(category.parent_path.split('/')) > 5:  # 5th level
                raise ValidationError(
                    _("You cannot create more than 4 levels of product categories.")
                )

    def readonly_line(self):
        self.is_confirm = True

    @api.onchange("product_category_margin_ids")
    def onchange_margin_lines(self):
        self.is_confirm = False



    @api.model
    def create(self, vals):
        if 'name' in vals and vals['name']:
            vals['name'] = vals['name'].upper()
        if 'name' in vals and not vals.get('parent_id'):
            existing_category = self.env['product.category'].search([
                ('name', '=', vals['name']),
                ('parent_id', '=', False)
            ], limit=1)
            if existing_category:
                raise ValidationError(_("A product category with the name '%s' already exists.") % vals['name'])
        # HSN Code Validation
        if 'hsn_code' in vals and vals['hsn_code']:
            hsn_exists = self.env['hsn.code.master'].search([('hsn_code', '=', vals['hsn_code'])],
                                                            limit=1)
            if not hsn_exists:
                raise ValidationError(
                    _("The HSN Code '%s' is not found in the HSN Code Master.") % vals['hsn_code'])

        # First, create the record
        category = super(ProductCategory, self).create(vals)

        # Then validate margin lines on the saved record
        category._validate_margin_lines()

        return category

    def write(self, vals):
        for category in self:
            # Check for duplicate name before saving
            if 'name' in vals:
                vals['name'] = vals['name'].upper()
                if self.search([('name', '=', vals['name']), ('id', '!=', category.id), ('parent_id','=', False)]):
                    raise ValidationError(_("A product category with the name '%s' already exists.") % vals['name'])

            # Check if parent_id is being set or changed
            if 'parent_id' in vals and vals['parent_id']:
                # If the category had margin lines, delete them
                category.margin_line_ids.unlink()
            # HSN Code Validation
            if 'hsn_code' in vals and vals['hsn_code']:
                hsn_exists = self.env['hsn.code.master'].search([('hsn_code', '=', vals['hsn_code'])],
                                                                limit=1)
                if not hsn_exists:
                    raise ValidationError(
                        _("The HSN Code '%s' is not found in the HSN Code Master.") % vals['hsn_code'])

        # First, save changes
        result = super(ProductCategory, self).write(vals)

        # Then validate margin lines after updating
        self._validate_margin_lines()

        return result

    def _validate_margin_lines(self):
        for category in self:
            is_parent = not category.parent_id  # Check if it's a parent category
            if is_parent and not category.margin_line_ids:
                raise ValidationError(_("Parent categories must have at least one margin line."))
            if is_parent and category.update_replication==False and not category.product_category_mrp_ids:
                raise ValidationError(_("Parent categories must have at least one margin mrp line."))


class ProductCategoryMarginLine(models.Model):
    _name = 'product.category.margin.line'

    product_category_margin_id = fields.Many2one('product.category', string="Product Category Margin", copy=False)
    margin = fields.Integer(string="Margin %", copy=False)
    from_range = fields.Integer(string="From Range")
    to_range = fields.Integer(string="To Range")

    @api.constrains('from_range', 'to_range', 'product_category_margin_id')
    def _check_range_overlap(self):
        for rec in self:
            if rec.from_range >= rec.to_range:
                raise ValidationError("From Range cannot be greater than To Range.")
            existing_lines = self.search([
                ('product_category_margin_id', '=', rec.product_category_margin_id.id), ('id', '!=', rec.id), ])
            for line in existing_lines:
                if not (rec.to_range < line.from_range or rec.from_range > line.to_range):
                    raise ValidationError(
                        f"Range {rec.from_range} - {rec.to_range} overlaps with existing range "
                        f"{line.from_range} - {line.to_range} in RSP."
                    )


class ProductCategoryMrpLine(models.Model):
    _name = 'product.category.mrp.line'

    product_category_mrp_id = fields.Many2one('product.category', string="Product Category MRP", copy=False)
    margin = fields.Integer(string="Margin %", copy=False)
    from_range = fields.Integer(string="From Range")
    to_range = fields.Integer(string="To Range")

    @api.constrains('from_range', 'to_range', 'product_category_mrp_id')
    def _check_range_overlap(self):
        for rec in self:
            if rec.from_range >= rec.to_range:
                raise ValidationError("From Range cannot be greater than To Range.")
            existing_lines = self.search([
                ('product_category_mrp_id', '=', rec.product_category_mrp_id.id), ('id', '!=', rec.id), ])
            for line in existing_lines:
                if not (rec.to_range < line.from_range or rec.from_range > line.to_range):
                    raise ValidationError(
                        f"Range {rec.from_range} - {rec.to_range} overlaps with existing range "
                        f"{line.from_range} - {line.to_range} in MRP."
                    )


