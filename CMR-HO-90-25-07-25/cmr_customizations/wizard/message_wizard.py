from odoo import models, fields, api
from odoo.exceptions import ValidationError



class MessageWizard(models.TransientModel):
    _name = 'message.wizard'

    def get_default(self):
        if self.env.context.get("message", False):
            return self.env.context.get("message")
        return False

    message = fields.Text('Message', required=True, default=get_default)


class AccountMoveDiscountWizard(models.TransientModel):
    _name = 'account.move.discount.wizard'
    _description = 'Apply Discount Wizard'

    move_id = fields.Many2one('account.move', required=True)
    discount_amount = fields.Float('Discount Amount', required=True)

    def apply_discount(self):
        self.ensure_one()
        move = self.move_id
        if self.discount_amount <= 0:
            raise ValidationError("Discount must be greater than zero.")
        existing_discount = any(
            line.product_id.name == 'Discount' and line.price_unit < 0
            for line in move.invoice_line_ids)
        if existing_discount:
            raise ValidationError("Discount already added to this vendor bill.")

        # Find the product with purchase_ok = True (you may want to add an internal reference instead)
        discount_product = self.env['product.product'].search([('name','=','Discount'),('purchase_ok', '=', True),('type', '=', 'consu'),], limit=1)
        if not discount_product:
            raise ValidationError("No suitable product found with 'purchase_ok = True' and with Discount name.")
        # Choose an income account
        income_account = discount_product.categ_id.property_account_expense_categ_id
        if not income_account:
            raise ValidationError("No Expense account set on the category.")
        move.write({
            'invoice_line_ids': [(0, 0, {
                'name': 'Discount',
                'quantity': 1,
                'price_unit': -abs(self.discount_amount),
                'product_id': discount_product.id,
                'tax_ids': [(5, 0, 0)],
                'account_id': income_account.id,
            })]
        })
