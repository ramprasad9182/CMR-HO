from odoo import models, fields, api, _
import logging

from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MultiProductWizard(models.TransientModel):
    _name = 'multi.product.wizard'
    _description = 'Wizard to select multiple products'

    product_name_id = fields.Many2many(
        'product.template',
        string="Product Name",
        domain=[('detailed_type', '!=', 'service'),('attribute_line_ids', '!=', False)],
    )

    barcode_or_code = fields.Char("Barcode or Internal Reference")

    available_attribute_value_ids = fields.Many2many(
        'product.attribute.value',
        compute='_compute_available_attribute_value_ids',
        store=False
    )

    # ⬇️ This field stores actual selected attribute values
    attribute_value_ids = fields.Many2many(
        'product.attribute.value',
        string="Attributes",
        domain="[('id', 'in', available_attribute_value_ids)]"
    )
    product_ids = fields.Many2many('product.product', string="Matching Products")
    request_id = fields.Many2one('approval.request', string="Approval")
    categ_ids = fields.Many2many('product.category', string='Allowed Categories')

    @api.depends('product_name_id')
    def _compute_available_attribute_value_ids(self):
        for wizard in self:
            if wizard.product_name_id:
                wizard.available_attribute_value_ids = wizard.product_name_id.attribute_line_ids.mapped('value_ids')
            else:
                wizard.available_attribute_value_ids = self.env['product.attribute.value']

    def select_attribute_product_ids(self):
        allowed_product_ids = []
        for product_tmpl_id in self.product_name_id:
            for attribute_value_id in self.attribute_value_ids:
                value_id = product_tmpl_id.attribute_line_ids.value_ids.filtered(
                    lambda x: x.id == attribute_value_id.id)
                if value_id:
                    for product_id in product_tmpl_id.product_variant_ids:
                        prod_tmpl_attribute_value_id = product_id.product_template_attribute_value_ids.filtered(
                            lambda x: x.name == attribute_value_id.name)
                        if prod_tmpl_attribute_value_id and prod_tmpl_attribute_value_id.attribute_id.name == attribute_value_id.attribute_id.name:
                            allowed_product_ids.append(product_id.id)
        return {
            'name': 'Select Product variants',
            'type': 'ir.actions.act_window',
            'res_model': 'multi.product.attribute.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_available_product_ids': allowed_product_ids,
                'default_request_id': self.request_id.id,
            }
        }


class MultiProductAttributeWizard(models.TransientModel):
    _name = 'multi.product.attribute.wizard'
    _description = 'Wizard to select multiple Product Variants'

    # available_product_ids = fields.Many2many('product.product', 'product_count', string="Available Products")
    available_product_ids = fields.Many2many(
        'product.product',
        'multi_product_attribute_wizard_product_rel',  # unique relation table name
        'wizard_id',  # column name for this model
        'product_id',  # column name for related model
        string="Available Products"
    )

    product_ids = fields.Many2many('product.product', string="Products", domain="[('id', 'in', available_product_ids)]")
    request_id = fields.Many2one('approval.request', string="Approval")

    def action_add_products(self):
        for product in self.product_ids:
            duplicates = []
            existing_line = self.request_id.product_line_ids.filtered(lambda x: x.product_id == product)
            if existing_line:
                duplicates.append(product.display_name)
            zone = product.categ_id
            if not zone.parent_id.parent_id.parent_id.zone_id:
                raise ValidationError(_(
                    "Product '%s' has missing zone. Please check its category assignment.") % product.display_name)
            if duplicates:
                raise UserError(
                    _("The following products are already in the approval request:\n%s\nPlease update the quantity in the existing lines.")
                    % ("\n".join(duplicates))
                )
            else:
                self.env['approval.product.line'].create({
                    'approval_request_id': self.request_id.id,
                    'product_id': product.id,
                    'description': product.display_name,
                    'quantity': 1.0,
                    'zone_id': product.categ_id.parent_id.parent_id.parent_id.zone_id.id,
                    'family': product.categ_id.parent_id.parent_id.parent_id.id if product.categ_id.parent_id and product.categ_id.parent_id.parent_id and product.categ_id.parent_id.parent_id.parent_id else False,
                    'category': product.categ_id.parent_id.parent_id.id if product.categ_id.parent_id and product.categ_id.parent_id.parent_id else False,
                    'Class': product.categ_id.parent_id.id if product.categ_id.parent_id else False,
                    'brick': product.categ_id.id,
                })

    @api.onchange('product_ids')
    def _onchange_product_ids(self):
        if self.product_ids:
            for product_id in self.product_ids:
                existing_line = self.request_id.product_line_ids.filtered(lambda x: x.product_id.id in product_id.ids)
                if existing_line:
                    return {
                        'warning': {
                            'title': "Duplicate Product",
                            'message': _(
                                "Product %s is already in the approval request. Please update quantity in the existing line.") % (
                                           product_id.display_name),
                        }
                    }

