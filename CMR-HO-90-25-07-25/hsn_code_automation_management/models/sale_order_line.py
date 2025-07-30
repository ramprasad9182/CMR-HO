# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # @api.onchange("product_id")
    # def _get_hsn_code_tax(self):
    #     order = self.order_id
    #     country_code = order.country_code
    #     gst_treatment = order.l10n_in_gst_treatment
    #     if country_code == "IN" and gst_treatment == "regular":
    #         company_state_id = order.company_id.state_id
    #         partner_state_id = order.partner_shipping_id.state_id
    #         if not partner_state_id:
    #             raise UserError(_("Please select a customer!."))
    #         product_hsn_code = self.product_id.l10n_in_hsn_code
    #         if product_hsn_code:
    #             hsn_master_id = self.env["hsn.code.master"].search(
    #                 [("hsn_code", "=", product_hsn_code)], limit=1
    #             )
    #             if hsn_master_id:
    #                 self.tax_id = (
    #                     hsn_master_id.sale_tax_id
    #                     if company_state_id.id == partner_state_id.id
    #                     else hsn_master_id.igst_sale_tax_id
    #                 )
