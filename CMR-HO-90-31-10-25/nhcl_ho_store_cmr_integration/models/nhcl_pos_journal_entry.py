
from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    nhcl_store_je = fields.Boolean('Store Payment', default=False, copy=False)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    nhcl_store_delivery = fields.Boolean('Store Delivery', default=False, copy=False)


class AccountMove(models.Model):
    _inherit = "account.move"

    nhcl_store_je = fields.Boolean('Store JE', default=False, copy=False)

    @api.model
    def create(self, vals_list):
        res = super(AccountMove, self).create(vals_list)
        if res and 'line_ids' in vals_list and 'nhcl_store_je' in vals_list and vals_list['nhcl_store_je'] == True:
            res.action_post()
        elif res and 'invoice_line_ids' in vals_list and 'nhcl_store_je' in vals_list and vals_list['nhcl_store_je'] == True:
            res.sudo().action_post()
            journal_id = self.env['account.journal'].sudo().search(
                [('name', '=', 'Cash'), ('company_id', '=', res.company_id.id)])
            payment = self.env['account.payment'].sudo().create({
                'amount': res.amount_total,
                'date': res.invoice_date,
                'journal_id': journal_id.id,
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': res.partner_id.id,
                'ref':res.name,
                'company_id':res.company_id.id,
                'currency_id':res.currency_id.id,
            })
            payment.action_post()
        return res







