from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import os
import logging
_logger = logging.getLogger(__name__)

class GiftVoucher(models.Model):
    _name = 'gift.voucher'
    _description = 'Gift Voucher'
    _rec_name = 'name'

    name = fields.Char("Voucher Number", required=True, copy=False, readonly=True, default=lambda self: _('New'))
    customer_name = fields.Char("Customer Name")
    amount = fields.Monetary("Amount", currency_field='currency_id', required=True, default=0.0)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.company.currency_id)
    issue_date = fields.Date("Issue Date", default=fields.Date.context_today)
    expiry_date = fields.Date("Expiry Date")
    status = fields.Selection([
        ('draft','Draft'),
        ('issued','Issued'),
        ('redeemed','Redeemed'),
        ('expired','Expired')
    ], default='draft')

    @api.model_create_multi
    def create(self, vals_list):
        seq_obj = self.env['ir.sequence']
        default_name = _('New')
        for vals in vals_list:
            if vals.get('name', default_name) == default_name:
                vals['name'] = seq_obj.next_by_code('gift.voucher.seq') or default_name

        return super().create(vals_list)

    def action_set_issued(self):
        self.status = 'issued'

    @api.model
    def _get_voucher_bg(self):
            """Return base64-encoded background image for PDF"""
            module_path = os.path.dirname(os.path.abspath(__file__))
            img_path = os.path.join(module_path, "..", "static", "src", "img", "voucher_bg.jpg")
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode("utf-8")
                return image_data
            return ""



class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    def action_print_loyalty_cards(self):
        # Fetch all loyalty cards linked to this program
        cards = self.env['loyalty.card'].sudo().search([('program_id', '=', self.id)])
        for card in cards:
            try:
                # Attempt to get the card background
                image_data = card._get_card_bg()
                print(f"Card {card.id} background fetched successfully")
            except Exception as e:
                # Handle errors gracefully
                _logger.error("Failed to get card background for card %s: %s", card.id, str(e))
                image_data = None
        if not cards:
            return  # or raise UserError("No loyalty cards found for this program.")


        # Use the correct module and report ID
        return self.env.ref("gift_voucher_custom.action_loyalty_card").report_action(cards)

    card_type = fields.Selection(
        [
            ('textile', 'Textile'),
            ('gold', 'Gold'),
        ],
        string='Card Type',
        required=True
    )

class LoyaltyCard(models.Model):
    _inherit = 'loyalty.card'

    card_type = fields.Selection(
        related='program_id.card_type',
        string='Card Type',
        store=True,
        readonly=False,
    )



