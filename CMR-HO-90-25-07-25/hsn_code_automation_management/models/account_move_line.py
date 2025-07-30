# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # @api.onchange("product_id")
    # def _get_hsn_code_tax(self):
    #     move = self.move_id
    #     country_code = move.country_code
    #     gst_treatment = move.l10n_in_gst_treatment
    #     if country_code == "IN" and gst_treatment == "regular":
    #         journal_type = move.l10n_in_journal_type
    #         company_state_id = self.company_id.state_id
    #         if journal_type == "sale":
    #             partner_state_id = move.l10n_in_state_id
    #         elif journal_type == "purchase":
    #             partner_state_id = move.partner_id.state_id
    #         if not partner_state_id:
    #             raise UserError(_("Please select a customer!."))
    #         product_hsn_code = self.product_id.l10n_in_hsn_code
    #         if product_hsn_code:
    #             hsn_master_id = self.env["hsn.code.master"].search(
    #                 [("hsn_code", "=", product_hsn_code)], limit=1
    #             )
    #             if hsn_master_id:
    #                 if company_state_id.id == partner_state_id.id:
    #                     self.tax_ids = (
    #                         hsn_master_id.sale_tax_id
    #                         if journal_type == "sale"
    #                         else hsn_master_id.purchase_tax_id
    #                     )
    #                 else:
    #                     self.tax_ids = (
    #                         hsn_master_id.igst_sale_tax_id
    #                         if journal_type == "sale"
    #                         else hsn_master_id.igst_purchase_tax_id
    #                     )
