# -*- coding: utf-8 -*-
from odoo import models, _,api
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    """Inherited product.template class to add fields and functions"""
    _inherit = 'product.template'

    @api.onchange('l10n_in_hsn_code')
    def get_hsn_code_from_master(self):
        for i in self:
            if i.l10n_in_hsn_code:
                hsn_master = self.env['hsn.code.master'].search([('hsn_code', '=', i.l10n_in_hsn_code)], limit=1)
                i.taxes_id = hsn_master.sale_tax_id.ids
                i.supplier_taxes_id = hsn_master.purchase_tax_id.ids
            else:
                i.taxes_id = False
                i.supplier_taxes_id = False
