# -*- coding: utf-8 -*-
from odoo import models, _,api
from odoo.exceptions import UserError


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    # def _compute_tax_id(self):
    #     super(PurchaseOrderLine, self)._compute_tax_id()
    #
    #     product_hsn_code = self.product_id.l10n_in_hsn_code
    #     if product_hsn_code:
    #         self._get_hsn_code_tax(product_hsn_code)
    #
    # def _get_hsn_code_tax(self, product_hsn_code):
    #     order = self.order_id
    #     country_code = order.country_code
    #     gst_treatment = order.l10n_in_gst_treatment
    #     if country_code == "IN" and gst_treatment == "regular":
    #         company_state_id = order.company_id.state_id
    #         partner_state_id = order.partner_id.state_id
    #         if not partner_state_id:
    #             raise UserError(_("Please select a Vendor."))
    #         hsn_master_id = self.env["hsn.code.master"].search(
    #             [("hsn_code", "=", product_hsn_code)], limit=1
    #         )
    #         if hsn_master_id:
    #             self.taxes_id = (
    #                 hsn_master_id.purchase_tax_id
    #                 if company_state_id.id == partner_state_id.id
    #                 else hsn_master_id.igst_purchase_tax_id
    #             )


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
