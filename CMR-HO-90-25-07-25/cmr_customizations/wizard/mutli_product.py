from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)

class MultiProductWizard(models.TransientModel):
    _name = 'multi.product.wizard'
    _description = 'Wizard to select multiple products'

    product_name_id = fields.Many2one(
        'product.template',
        string="Product Name",
        domain=[('detailed_type', '!=', 'service')],
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


    def action_search_products(self):
        domain = [('detailed_type', '!=', 'service')]

        if self.product_name_id:
            domain.append(('id', '=', self.product_name_id.id))
        if self.barcode_or_code:
            domain += ['|', ('barcode', 'ilike', self.barcode_or_code), ('default_code', 'ilike', self.barcode_or_code)]
        if self.categ_ids:
            domain.append(('categ_id', 'in', self.categ_ids.ids))

        templates = self.env['product.template'].search(domain)
        _logger.warning(f'Templates found: {templates.ids} | Total: {len(templates)}')

        matched_products = self.env['product.product']

        for tmpl in templates:
            for variant in tmpl.product_variant_ids:
                variant_values = variant.product_template_attribute_value_ids.mapped('product_attribute_value_id')
                if not self.attribute_value_ids or all(val in variant_values for val in self.attribute_value_ids):
                    matched_products |= variant

        _logger.warning(f'Final matched products: {matched_products.ids}')
        self.product_ids = matched_products

        for product in matched_products:
            self.env['approval.product.line'].create({
                'approval_request_id': self.request_id.id,
                'product_id': product.id,
                'description': product.display_name,
                'quantity': 1.0,
                'family': product.categ_id.parent_id.parent_id.parent_id.id if product.categ_id.parent_id and product.categ_id.parent_id.parent_id and product.categ_id.parent_id.parent_id.parent_id else False,
                'category': product.categ_id.parent_id.parent_id.id if product.categ_id.parent_id and product.categ_id.parent_id.parent_id else False,
                'Class': product.categ_id.parent_id.id if product.categ_id.parent_id else False,
                'brick': product.categ_id.id,
            })


