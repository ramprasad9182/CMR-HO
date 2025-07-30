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
    category_abbr = fields.Char(string='Prefix', compute='_compute_category_abbr', store=True)
    product_suffix = fields.Char(string="Suffix", copy=False, tracking=True)
    max_number = fields.Integer(string='Max')
    serial_no = fields.Char(string="Serial No")
    product_description = fields.Html(string="Product Description")
    web_product = fields.Char(string="Website  Product Name")
    segment = fields.Selection([('apparel','Apparel'), ('non_apparel','Non Apparel'), ('others','Others')], string="Segment", copy=False, tracking=True)
    item_type = fields.Selection([('inventory', 'Inventory'), ('non_inventory', 'Non Inventory')], string="Item Type",
                                 copy=False, tracking=True)

    @api.depends('categ_id')
    def _compute_category_abbr(self):
        for product in self:
            if product.categ_id:
                product.category_abbr = self._get_category_abbr(product.categ_id.display_name)
            else:
                product.category_abbr = False

    def _get_category_abbr(self, phrase):
        # Split the phrase by '/' and take the first part
        first_segment = phrase.split('/')[0].strip()
        first_segment = first_segment.replace('-', ' ')
        words = first_segment.split()
        if len(words) == 1:
            return words[0][0]
        # Otherwise, get the first letter of each word and combine them
        initials = ''.join(word[0] for word in words if word)
        return initials

    @api.onchange('categ_id')
    def creating_product_name_from_categ(self):
        if self.categ_id and self.nhcl_type == 'ho_operation':
            display_name_modified = self.categ_id.display_name.replace(' / ', '-')
            self.name = display_name_modified

    @api.model
    def create(self, vals):
        if 'name' in vals:
            existing_product = self.env['product.template'].search([('name', '=', vals['name']),('detailed_type','!=','service')])
            if existing_product:
                raise ValidationError(_("A product called '%s' already exists.") % vals['name'])
        vals['available_in_pos'] = True
        product = super(ProductTemplate, self).create(vals)
        return product

    def write(self, vals):
        if 'name' in vals:
            for product in self:
                existing_product = self.env['product.template'].search(
                    [('name', '=', vals['name']), ('id', '!=', product.id),('detailed_type','!=','service')])
                if existing_product:
                    raise ValidationError(_(" A product called '%s' already exists.") % vals['name'])
        return super(ProductTemplate, self).write(vals)


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

class ProductProduct(models.Model):
    _inherit = "product.product"

    category_abbr = fields.Char(string='Prefix', compute='_compute_category_abbr', store=True)
    product_suffix = fields.Char(string="Suffix", copy=False, tracking=True)
    max_number = fields.Integer(string='Max')
    serial_no = fields.Char(string="Serial No")


    @api.depends('categ_id')
    def _compute_category_abbr(self):
        for product in self:
            if product.categ_id:
                product.category_abbr = self._get_category_abbr(product.categ_id.display_name)

    def _get_category_abbr(self, phrase):
        # Split the phrase by '/' and take the first part
        first_segment = phrase.split('/')[0].strip()
        first_segment = first_segment.replace('-', ' ')
        words = first_segment.split()
        if len(words) == 1:
            return words[0][0]
        # Otherwise, get the first letter of each word and combine them
        initials = ''.join(word[0] for word in words if word)
        return initials


    @api.model
    def create(self, vals):
        res = super(ProductProduct, self).create(vals)
        res.generate_ean()
        return res


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    nhcl_attribute_name = fields.Char(string="Full Name")

    @api.model
    def create(self, vals):
        if 'name' in vals:
            vals['name'] = vals['name'].capitalize()
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM product_attribute_value")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        res = super(ProductAttributeValue, self).create(vals)
        res.nhcl_attribute_name = res.attribute_id.name + ' : ' + vals['name']
        return res

    def write(self, vals):
        if 'name' in vals:
            vals['name'] = vals['name'].capitalize()
            vals['nhcl_attribute_name'] = self.attribute_id.name + ' : ' + vals['name']
        return super(ProductAttributeValue, self).write(vals)

    @api.depends("name")
    def _compute_display_name(self):
        super()._compute_display_name()
        for i in self:
            i.display_name = f"{i.name}"


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)

    @api.model
    def create(self, vals):
        if 'name' in vals and isinstance(vals['name'], str):
            formatted_name = vals['name'].strip().title() # Capitalize first letter of every word
            if self.search([('name', 'ilike', formatted_name)]): # Case-insensitive check
                raise ValidationError("A product attribute with this name already exists.")
        return super().create(vals)

    def write(self, vals):
        if 'name' in vals and isinstance(vals['name'], str):
            formatted_name = vals['name'].strip().title() # Capitalize first letter of every word
            if self.search([('name', 'ilike', formatted_name), ('id', '!=', self.id)]): # Case-insensitive check
                raise ValidationError("A product attribute with this name already exists.")
        return super().write(vals)