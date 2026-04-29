from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        Model = self.env['product.attribute']

        # Step 1: normalize names
        names = []
        normalized_map = {}

        for vals in vals_list:
            name = vals.get('name')
            if isinstance(name, str):
                formatted = name.strip().title()
                vals['name'] = formatted
                names.append(formatted)
                normalized_map[formatted.lower()] = formatted
        # Step 2: check duplicates in DB (case-insensitive exact)
        if names:
            existing = Model.search([
                ('name', 'in', names)
            ])
            existing_lower = {n.lower() for n in existing.mapped('name')}

            for name in names:
                if name.lower() in existing_lower:
                    raise ValidationError(
                        _("A product attribute with name '%s' already exists.") % name
                    )
        # Step 3: check duplicates inside batch
        seen = set()
        for name in names:
            key = name.lower()
            if key in seen:
                raise ValidationError(
                    _("Duplicate attribute '%s' in same request.") % name
                )
            seen.add(key)
        # Step 4: create records
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals and isinstance(vals['name'], str):
            formatted_name = vals['name'].strip().title() # Capitalize first letter of every word
            if self.search([('name', 'ilike', formatted_name), ('id', '!=', self.id)]): # Case-insensitive check
                raise ValidationError("A product attribute with this name already exists.")
        return super().write(vals)


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)
    nhcl_attribute_name = fields.Char(string="Full Name")

    @api.model_create_multi
    def create(self, vals_list):
        # Step 1: normalize name
        for vals in vals_list:
            if vals.get('name'):
                vals['name'] = vals['name'].strip().capitalize()
        # Step 3: get max nhcl_id once
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM product_attribute_value")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        # Step 4: assign sequential ids
        next_id = max_nhcl_id + 1
        for vals in vals_list:
            vals['nhcl_id'] = next_id
            next_id += 1
        # Step 5: create records
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            if rec.attribute_id and vals.get('name'):
                rec.nhcl_attribute_name = f"{rec.attribute_id.name} : {vals['name']}"
        return records

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


class ProductTemplateAttributeValue(models.Model):
    _inherit = "product.template.attribute.value"

    attribute_name = fields.Char(
        related="attribute_line_id.attribute_id.name",
        store=True, translate=True
    )

    _order = "attribute_name"