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

    @api.model
    def create(self, vals):
        if 'name' in vals:
            existing_product = self.env['product.template'].search([('name', '=', vals['name']),('detailed_type','!=','service')])
            if existing_product:
                raise ValidationError(_("A product called '%s' already exists.") % vals['name'])
        vals['available_in_pos'] = True
        product = super(ProductTemplate, self).create(vals)
        # product._onchange_tracking_warning()
        return product

    @api.constrains('tracking')
    def check_product_tracking(self):
        if self.detailed_type == 'product' and self.tracking == 'none':
            raise ValidationError('This product is storable but tracking is set to None.')

    def write(self, vals):
        if 'name' in vals:
            for product in self:
                existing_product = self.env['product.template'].search(
                    [('name', '=', vals['name']), ('id', '!=', product.id),('detailed_type','!=','service')])
                if existing_product:
                    raise ValidationError(_(" A product called '%s' already exists.") % vals['name'])
        return super(ProductTemplate, self).write(vals)

