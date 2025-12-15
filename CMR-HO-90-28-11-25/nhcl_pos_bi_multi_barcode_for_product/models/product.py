from odoo.exceptions import ValidationError
import re
from odoo import api, fields, models
from odoo.osv import expression
import random


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_barcode = fields.One2many('product.barcode', 'product_tmpl_id', string='Product Multi Barcodes')
    company_barcode_id = fields.Many2one('res.company', 'company', default=lambda self: self.env.user.company_id)
    multi_barcode_for_product = fields.Boolean(related='company_barcode_id.multi_barcode_for_product',
                                               string="Multi Barcode For Product")
    mrp_price = fields.Float(string="MRP", default="1")
    percentage = fields.Integer(string="percentage")

    @api.onchange('mrp_price', 'list_price')
    def _get_percentage(self):
        if self.mrp_price >= 1:
            per = self.mrp_price - self.list_price
            self.percentage = per / self.mrp_price * 100
        else:
            raise ValidationError("MRP Price Should be Greater Than 1.")


class ProductInherit(models.Model):
    _inherit = 'product.product'

    product_barcode = fields.One2many('product.barcode', 'product_id', string='Product Multi Barcodes')
    mrp_price = fields.Float(string="MRP", default="1")
    percentage = fields.Integer(string="percentage")
    product_barcodes = fields.Char(compute="_get_multi_barcode_search_string", string="Barcodes", store=True)

    @api.depends('product_barcode', 'product_tmpl_id.product_barcode')
    def _get_multi_barcode_search_string(self):
        for rec in self:
            barcode_search_string = rec.name or ''
            for r in rec.product_barcode:
                if r.barcode:
                    barcode_search_string += '|' + r.barcode
            for rc in rec.product_tmpl_id.product_barcode:
                if rc.barcode:
                    barcode_search_string += '|' + rc.barcode
            rec.product_barcodes = barcode_search_string

    @api.onchange('mrp_price', 'lst_price')
    def _get_percentage(self):
        if self.mrp_price >= 1:
            per = self.mrp_price - self.lst_price
            self.percentage = per / self.mrp_price * 100
        else:
            raise ValidationError("MRP Price Should be Greater Than 1.")

    def generate_ean(self):
        number_random = str("%0.13d" % random.randint(0, 9999999999999))
        barcode_str = self.env['barcode.nomenclature'].sanitize_ean("%s" % (number_random))
        if self.barcode:
            if len(self.barcode) != 14:
                self.barcode = barcode_str
        else:
            self.barcode = barcode_str

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        company_id = self.env.user.company_id
        if company_id.multi_barcode_for_product == True:
            if not domain:
                domain = []
            if name:
                positive_operators = ['=', 'ilike', '=ilike', 'like', '=like']
                product_ids = []
                if operator in positive_operators:
                    product_ids = list(self._search([('default_code', '=', name)] + domain, limit=limit, order=order))
                    if not product_ids:
                        product_ids = list(self._search([('barcode', '=', name)] + domain, limit=limit, order=order))
                        product_barcode_ids = self.env['product.barcode']._search([
                            ('barcode', operator, name)])
                        if product_barcode_ids:
                            product_ids = list(self._search(
                                ['|', ('barcode', '=', name), ('product_barcode.barcode', '=', name)] + domain,
                                limit=limit, order=order))
                            if product_ids:
                                return product_ids
                if len(name) > 13:
                    if name[0] == '0' and name[1] == '1' and name[16] == '2' and name[17] == '1':
                        product_barcode = ''
                        for i in range(0, len(name)):
                            if i > 1 and i < 16:
                                product_barcode += name[i]
                            else:
                                continue
                        product_ids = list(
                            self._search([('barcode', '=', product_barcode)] + domain, limit=limit, order=order))
                if not product_ids and operator not in expression.NEGATIVE_TERM_OPERATORS:
                    # Do not merge the 2 next lines into one single search, SQL search performance would be abysmal
                    # on a database with thousands of matching products, due to the huge merge+unique needed for the
                    # OR operator (and given the fact that the 'name' lookup results come from the ir.translation table
                    # Performing a quick memory merge of ids in Python will give much better performance
                    product_ids = list(self._search(domain + [('default_code', operator, name)], limit=limit))
                    if not limit or len(product_ids) < limit:
                        # we may underrun the limit because of dupes in the results, that's fine
                        limit2 = (limit - len(product_ids)) if limit else False
                        product2_ids = self._search(domain + [('name', operator, name), ('id', 'not in', product_ids)],
                                                    limit=limit2, order=order)
                        product_ids.extend(product2_ids)

                elif not product_ids and operator in expression.NEGATIVE_TERM_OPERATORS:
                    domain_add = expression.OR([
                        ['&', ('default_code', operator, name), ('name', operator, name)],
                        ['&', ('default_code', '=', False), ('name', operator, name)],
                    ])
                    domain_add = expression.AND([domain, domain_add])
                    product_ids = list(self._search(domain_add, limit=limit, order=order))
                if not product_ids and operator in positive_operators:
                    ptrn = re.compile('(\[(.*?)\])')
                    res = ptrn.search(name)
                    if res:
                        product_ids = list(
                            self._search([('default_code', '=', res.group(2))] + domain, limit=limit, order=order))
                # still no results, partner in context: search on supplier info as last hope to find something
                if not product_ids and self._context.get('partner_id'):
                    suppliers_ids = self.env['product.supplierinfo']._search([
                        ('product_name', '=', self._context.get('partner_id')),
                        '|',
                        ('product_code', operator, name),
                        ('product_name', operator, name)])
                    if suppliers_ids:
                        product_ids = self._search([('product_tmpl_id.seller_ids', 'in', suppliers_ids)], limit=limit,
                                                   order=order)

                # Search Record base on Multi Barcode
                product_barcode_ids = self.env['product.barcode']._search([
                    ('barcode', operator, name)])
                if product_barcode_ids:
                    product_ids = list(self._search([
                        '|',
                        ('product_barcode', 'in', product_barcode_ids),
                        ('product_tmpl_id.product_barcode', 'in', product_barcode_ids)],
                        limit=limit, order=order))
            else:
                product_ids = self._search(domain, limit=limit, order=order)
            product_ids1 = product_ids

            return product_ids1
        else:
            if not domain:
                domain = []
            if name:
                positive_operators = ['=', 'ilike', '=ilike', 'like', '=like']
                product_ids = []
                model_name = []
                if operator in positive_operators:
                    product_ids = list(self._search([('default_code', '=', name)] + domain, limit=limit, order=order))
                    if not product_ids:
                        product_ids = list(
                            self._search(['|', ('barcode', '=', name), ('product_barcode.barcode', '=', name)] + domain,
                                         limit=limit, order=order))
                        if product_ids:
                            return product_ids
                if len(name) > 13:
                    if name[0] == '0' and name[1] == '1' and name[16] == '2' and name[17] == '1':
                        product_barcode = ''
                        for i in range(0, len(name)):
                            if i > 1 and i < 16:
                                product_barcode += name[i]
                            else:
                                continue
                        product_ids = list(
                            self._search([('barcode', '=', product_barcode)] + domain, limit=limit, order=order))
                if not product_ids and operator not in expression.NEGATIVE_TERM_OPERATORS:
                    # Do not merge the 2 next lines into one single search, SQL search performance would be abysmal
                    # on a database with thousands of matching products, due to the huge merge+unique needed for the
                    # OR operator (and given the fact that the 'name' lookup results come from the ir.translation table
                    # Performing a quick memory merge of ids in Python will give much better performance
                    product_ids = list(self._search(domain + [('default_code', operator, name)], limit=limit))
                    if not limit or len(product_ids) < limit:
                        # we may underrun the limit because of dupes in the results, that's fine
                        limit2 = (limit - len(product_ids)) if limit else False
                        product2_ids = self._search(domain + [('name', operator, name), ('id', 'not in', product_ids)],
                                                    limit=limit2, order=order)
                        product_ids.extend(product2_ids)
                elif not product_ids and operator in expression.NEGATIVE_TERM_OPERATORS:
                    domain_add = expression.OR([
                        ['&', ('default_code', operator, name), ('name', operator, name)],
                        ['&', ('default_code', '=', False), ('name', operator, name)],
                    ])
                    domain_add = expression.AND([domain, domain_add])
                    product_ids = list(self._search(domain_add, limit=limit, order=order))

                if not product_ids and operator in positive_operators:
                    ptrn = re.compile('(\[(.*?)\])')
                    res = ptrn.search(name)
                    if res:
                        product_ids = list(
                            self._search([('default_code', '=', res.group(2))] + domain, limit=limit, order=order))
                # still no results, partner in context: search on supplier info as last hope to find something

                if not product_ids and self._context.get('partner_id'):

                    suppliers_ids = self.env['product.supplierinfo']._search([
                        ('product_name', '=', self._context.get('partner_id')),
                        '|',
                        ('product_code', operator, name),
                        ('product_name', operator, name)])
                    if suppliers_ids:
                        product_ids = self._search([('product_tmpl_id.seller_ids', 'in', suppliers_ids)], limit=limit,
                                                   order=order)

                # Search Record base on Multi Barcode

                product_barcode_ids = self.env['product.barcode']._search([
                    ('barcode', operator, name)])
                if product_barcode_ids:
                    product_ids = list(self._search([
                        ('product_tmpl_id.product_barcode', 'in', product_barcode_ids)],
                        limit=limit, order=order))

            else:
                product_ids = self._search(domain, limit=limit, order=order)
            return product_ids


class Barcode(models.Model):
    _name = 'product.barcode'
    _description = "Product Barcode"

    product_id = fields.Many2one('product.product')
    barcode = fields.Char(string='Barcode')
    product_tmpl_id = fields.Many2one('product.template')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id)
    multi_barcode_for_product = fields.Boolean(related='company_id.multi_barcode_for_product',
                                               string="Multi Barcode For Product")
    nhcl_inward_qty = fields.Float('Inward Qty')
    nhcl_inward_date = fields.Date('Inward Date')
    nhcl_outward_qty = fields.Float('OutWard Qty')
    nhcl_supplier_name = fields.Char('Supplier')

    model_ids = fields.Many2one('ir.model', string='Used For')

    _sql_constraints = [
        ('uniq_barcode', 'unique(barcode)', "A barcode can only be assigned to one product !"),
    ]


class POSOrderLoad(models.Model):
    _inherit = 'pos.session'

    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        result['search_params']['fields'].extend(['product_barcodes'])
        return result

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        new_model = 'product.barcode'
        if new_model not in result:
            result.append(new_model)
        return result

    def _loader_params_product_barcode(self):
        return {
            'search_params': {
                'domain': [],
                'fields': [
                    'barcode', 'product_tmpl_id', 'product_id', 'model_ids',
                ],
            }
        }

    def _get_pos_ui_product_barcode(self, params):
        return self.env['product.barcode'].search_read(**params['search_params'])
