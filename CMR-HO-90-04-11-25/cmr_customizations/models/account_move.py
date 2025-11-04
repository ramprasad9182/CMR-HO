from odoo import fields, models, api, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', copy=False, tracking=True)
    ref_partner_ids = fields.Many2many('res.partner', string='Pat/Cust')
    transporter = fields.Many2one(
        "res.partner",
        string="Transporter",
        compute="_compute_transporter",
        store=True
    )
    lr_number = fields.Char(
        string="LR Number",
        compute="_compute_transporter",
        store=True
    )
    allow_import_order = fields.Boolean('Allow Import', compute='_compute_import_order_lines')


    def action_map_analytic_distribution(self):
        """
        Copy analytic_distribution from first line to all empty lines
        """
        for move in self:
            if not move.line_ids:
                continue
            # take first line's analytic_distribution
            first_distribution = move.line_ids[0].analytic_distribution
            if not first_distribution:
                continue

            for line in move.line_ids:
                if not line.analytic_distribution:
                    line.analytic_distribution = first_distribution

    def action_post(self):
        self.action_map_analytic_distribution()
        return super().action_post()

    def _compute_import_order_lines(self):
        if self.env.user and self.env.user.import_account_move_line == True:
            self.allow_import_order = True
        else:
            self.allow_import_order = False

    def action_print_text_tiles_report(self):
        self.ensure_one()
        return self.env.ref('cmr_customizations.text_tiles_invoice_report').report_action(self)

    def invoice_odt_report(self):
        self.ensure_one()
        return self.env.ref('cmr_customizations.text_tiles_invoice_report_odt').report_action(self)
    def purchase_vendor_bill(self):
        self.ensure_one()
        return self.env.ref('cmr_customizations.vendor_bill_purchase').report_action(self.id)
    @api.onchange('partner_id')
    def _onchange_fun_import_order(self):
        self._compute_import_order_lines()

    @api.depends("invoice_origin")  # Ensure dependency on PO number
    def _compute_transporter(self):
        for record in self:
            transporter_check = self.env["transport.check"].search([("po_order_id", "=", record.invoice_origin)],
                                                                   limit=1)
            record.transporter = transporter_check.transporter if transporter_check else False
            record.lr_number = transporter_check.logistic_lr_number if transporter_check else False

    @api.model
    def default_get(self, fields_list):
        res = super(AccountMove, self).default_get(fields_list)
        if self.move_type == 'entry' or self._context.get('default_move_type') in ['out_invoice', 'out_refund','entry']:
            cust = self.env['res.partner'].search([('group_contact.name', 'in', ['Customer','Branch'])])
            res['ref_partner_ids'] = cust
        elif self._context.get('default_move_type') in ['in_invoice', 'in_refund', 'in_receipt']:
            vend = self.env['res.partner'].search([('group_contact.name', 'in', ['Vendor','Branch','Agent'])])
            res['ref_partner_ids'] = vend
        return res

    def vehicle_line_account(self):
        previous_vehicle_id = False
        for rec in self.line_ids:
            if rec.vehicle_id:
                previous_vehicle_id = rec.vehicle_id
            elif not rec.vehicle_id and previous_vehicle_id:
                rec.vehicle_id = previous_vehicle_id

    @api.model
    def create(self, vals_list):
        res = super(AccountMove,self).create(vals_list)
        res.vehicle_line_account()
        if res.move_type in ['out_invoice', 'out_refund','entry']:
            cust = self.env['res.partner'].search([('group_contact.name', 'in', ['Customer','Branch'])])
            res.ref_partner_ids = cust
        elif res.move_type in ['in_invoice', 'in_refund', 'in_receipt']:
            vend = self.env['res.partner'].search([('group_contact.name', 'in', ['Vendor', 'Branch', 'Agent'])])
            res.ref_partner_ids = vend
        if res.reversed_entry_id.ref:
            vals_list['ref'] = f"{vals_list['ref'] + ' , '+res.reversed_entry_id.ref}"
        return res

    def open_account_discount_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Apply Discount',
            'res_model': 'account.move.discount.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
            }
        }


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', copy=False, tracking=True)
    account_design_id = fields.Many2one('product.attribute.value', string="Design",
                                        related='purchase_line_id.design_id')
    prod_serial_no = fields.Many2many('stock.lot', string='Lot/Serial No', copy=False)
    prod_barcode = fields.Char('Barcode', copy=False)

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    cust_vend_ids = fields.Many2many('res.partner', string='Pat/Cust')

    @api.model
    def default_get(self, fields_list):
        res = super(AccountPayment, self).default_get(fields_list)
        if self._context.get('default_payment_type') in ['inbound']:
            cust = self.env['res.partner'].search([('group_contact.name', 'in', ['Customer','Branch'])])
            res['cust_vend_ids'] = cust
        elif self._context.get('default_payment_type') in ['outbound']:
            vend = self.env['res.partner'].search([('group_contact.name', 'in', ['Vendor','Branch','Agent'])])
            res['cust_vend_ids'] = vend
        return res


class AccountTax(models.Model):
    _inherit = 'account.tax'

    max_amount = fields.Float(string='Maximum Amount', digits=0, required=True,
                              help="")
    min_amount = fields.Float(string='Minimum Amount', digits=0, required=True,
                              help="")

    nhcl_creadit_note_tax = fields.Boolean(string="Credit Note")



class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)

        if res.get('payment_type') == 'outbound' and res.get('partner_type') == 'customer':
            cash_journal = self.env['account.journal'].search([('type', '=', 'cash')], limit=1)
            if cash_journal:
                res['journal_id'] = cash_journal.id

        return res


class AccountGroup(models.Model):
    _inherit = "account.group"

    nhcl_parent_id = fields.Many2one('account.group', string="NHCL Parent")