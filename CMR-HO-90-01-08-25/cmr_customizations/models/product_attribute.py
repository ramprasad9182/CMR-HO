from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


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

