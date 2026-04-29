
from odoo import models, fields, api
import logging

from odoo.exceptions import ValidationError

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

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)

        for move, vals in zip(moves, vals_list):

            if not vals.get('nhcl_store_je'):
                continue

            # ---- POST MOVE ----
            move.sudo().action_post()

            # ---- CREDIT NOTE CASE ----
            if (
                    move.move_type in ['out_refund', 'in_refund']
                    and move.journal_id.name == 'Credit Note Issue'
            ):
                journal = self.env['account.journal'].sudo().search([
                    ('name', '=', 'Cash'),
                    ('company_id', '=', move.company_id.id)
                ], limit=1)

                if not journal:
                    raise ValidationError("Cash journal not found.")
                payment = self.env['account.payment'].sudo().create({
                    'amount': move.amount_total,
                    'date': move.invoice_date,
                    'journal_id': journal.id,
                    'payment_type': 'inbound',
                    'partner_type': 'customer',
                    'partner_id': move.partner_id.id,
                    'ref': move.name,
                    'company_id': move.company_id.id,
                    'currency_id': move.currency_id.id,
                })

                payment.action_post()
                move.merge_credit_note_to_customer()
        return moves







