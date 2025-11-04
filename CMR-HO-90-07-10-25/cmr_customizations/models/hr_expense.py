from odoo import api, fields, Command, models, _


class HrExpense(models.Model):
    _inherit = "hr.expense"

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', copy=False, tracking=True)

    def _prepare_move_lines_vals(self):
        self.ensure_one()
        account = self.account_id
        if not account:
            # We need to do this as the installation process may delete the original account, and it doesn't recompute properly after.
            # This forces the default values if none is found
            if self.product_id:
                account = self.product_id.product_tmpl_id._get_product_accounts()['expense']
            else:
                account = self.env['ir.property']._get('property_account_expense_categ_id', 'product.category')
        expense_name = self.name.split('\n')[0][:64]
        return {
            'name': f'{self.employee_id.name}: {expense_name}',
            'account_id': account.id,
            'quantity': self.quantity or 1,
            'price_unit': self.price_unit,
            'product_id': self.product_id.id,
            'vehicle_id': self.vehicle_id.id,
            'product_uom_id': self.product_uom_id.id,
            'analytic_distribution': self.analytic_distribution,
            'expense_id': self.id,
            'partner_id': False if self.payment_mode == 'company_account' else self.employee_id.sudo().work_contact_id.id,
            'tax_ids': [Command.set(self.tax_ids.ids)],
        }

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    sale_employee = fields.Selection([('yes','YES'), ('no','NO')], string="Sale Employee")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
