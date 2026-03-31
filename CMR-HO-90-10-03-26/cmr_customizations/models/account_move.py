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
    # taxes_ids = fields.Many2many(
    #     'account.tax',
    #     'account_move_taxes_rel',  # relation table name
    #     'move_id',  # current model column
    #     'tax_id',  # related model column
    #     string='Taxes',
    #     domain="[('company_id', '=', company_id), ('type_tax_use', '=', 'none')]",
    #     help="Shows only taxes belonging to the same company and with tax_type='none'."
    # )

    tds_tax_ids = fields.Many2many(
        'account.tax',
        'account_move_tds_tax_rel',  # relation table
        'move_id',  # column for account.move
        'tax_id',  # column for account.tax
        string='TDS Taxes',
        domain="[('nhcl_tax_type', '=', 'tds')]"
    )

    tcs_tax_ids = fields.Many2many(
        'account.tax',
        'account_move_tcs_tax_rel',  # relation table
        'move_id',
        'tax_id',
        string='TCS Taxes',
        domain="[('nhcl_tax_type', '=', 'tcs')]"
    )

    cess_tax_ids = fields.Many2many(
        'account.tax',
        'account_move_cess_tax_rel',  # relation table
        'move_id',
        'tax_id',
        string='Cess Taxes',
        domain="[('nhcl_tax_type', '=', 'cess')]"
    )
    batch_id = fields.Many2one(
        'stock.picking.batch',
        string="Batch Transfer",
        compute="_compute_batch_id",
        store=True
    )

    def _compute_batch_id(self):
        for move in self:
            batch = False

            if move.move_type == 'out_invoice' and move.invoice_origin:

                picking = self.env['stock.picking'].search([
                    ('origin', '=', move.invoice_origin),
                    ('batch_id.state', '=', 'done')
                ], limit=1)

                if picking:
                    batch = picking.batch_id

            move.batch_id = batch

    @api.model
    def create(self, vals):
        move = super(AccountMove, self).create(vals)

        # ---- Your existing custom logic ----
        move.vehicle_line_account()

        if move.move_type in ['out_invoice', 'out_refund', 'entry']:
            cust = self.env['res.partner'].search([
                ('group_contact.name', 'in', ['Customer', 'Branch'])
            ])
            move.ref_partner_ids = cust

        elif move.move_type in ['in_invoice', 'in_refund', 'in_receipt']:
            vend = self.env['res.partner'].search([
                ('group_contact.name', 'in', ['Vendor', 'Branch', 'Agent'])
            ])
            move.ref_partner_ids = vend

        if move.reversed_entry_id.ref:
            vals['ref'] = f"{vals.get('ref', '')} , {move.reversed_entry_id.ref}"

        # ---- TAX SYNC IN CREATE ----
        selected_taxes = set(move.tds_tax_ids.ids) | set(move.tcs_tax_ids.ids) | set(move.cess_tax_ids.ids)

        for line in move.line_ids:
            if not line.exists() or line.display_type in ('line_section', 'line_note'):
                continue

            current_line_taxes = set(line.tax_ids.ids)

            # 👉 ADD missing taxes
            for tax_id in selected_taxes:
                if tax_id not in current_line_taxes:
                    line.tax_ids = [(4, tax_id)]

            # 👉 REMOVE only removed managed TDS/TCS/Cess
            for tax in line.tax_ids.filtered(lambda t: t.nhcl_tax_type in ['tds', 'tcs', 'cess']):
                if tax.id not in selected_taxes:
                    line.tax_ids = [(3, tax.id)]

        return move

    def write(self, vals):
        res = super(AccountMove, self).write(vals)

        # ---- TAX SYNC IN WRITE ----
        for move in self:
            selected_taxes = set(move.tds_tax_ids.ids) | set(move.tcs_tax_ids.ids) | set(move.cess_tax_ids.ids)

            for line in move.line_ids:
                if not line.exists() or line.display_type in ('line_section', 'line_note'):
                    continue

                current_line_taxes = set(line.tax_ids.ids)

                # 👉 ADD missing taxes
                for tax_id in selected_taxes:
                    if tax_id not in current_line_taxes:
                        line.tax_ids = [(4, tax_id)]

                # 👉 REMOVE only removed managed TDS/TCS/Cess
                for tax in line.tax_ids.filtered(lambda t: t.nhcl_tax_type in ['tds', 'tcs', 'cess']):
                    if tax.id not in selected_taxes:
                        line.tax_ids = [(3, tax.id)]

        return res
    #
    # @api.model
    # def create(self, vals_list):
    #     # Create record first
    #     res = super(AccountMove, self).create(vals_list)
    #
    #     # --- Your existing logic ---
    #     res.vehicle_line_account()
    #
    #     if res.move_type in ['out_invoice', 'out_refund', 'entry']:
    #         cust = self.env['res.partner'].search([
    #             ('group_contact.name', 'in', ['Customer', 'Branch'])
    #         ])
    #         res.ref_partner_ids = cust
    #     elif res.move_type in ['in_invoice', 'in_refund', 'in_receipt']:
    #         vend = self.env['res.partner'].search([
    #             ('group_contact.name', 'in', ['Vendor', 'Branch', 'Agent'])
    #         ])
    #         res.ref_partner_ids = vend
    #
    #     if res.reversed_entry_id.ref:
    #         vals_list['ref'] = f"{vals_list['ref']} , {res.reversed_entry_id.ref}"
    #
    #     # --- ✅ Tax sync logic ---
    #     if res.taxes_ids:
    #         tax_ids = res.taxes_ids.ids
    #         for line in res.line_ids:
    #             if line.exists():
    #                 for t in tax_ids:
    #                     if t not in line.tax_ids.ids:
    #                         line.tax_ids = [(4, t)]
    #
    #     return res
    #
    # def write(self, vals):
    #     old_map = {m.id: set(m.taxes_ids.ids) for m in self}
    #     res = super(AccountMove, self).write(vals)
    #
    #     for move in self:
    #         # ✅ Refresh line records safely for Odoo 17
    #         move_lines = self.env['account.move.line'].sudo().search([('move_id', '=', move.id)])
    #
    #         old = old_map.get(move.id, set())
    #         new = set(move.taxes_ids.ids)
    #         added = new - old
    #         removed = old - new
    #
    #         if added:
    #             for line in move_lines:
    #                 if line.exists():
    #                     for t in added:
    #                         if t not in line.tax_ids.ids:
    #                             line.tax_ids = [(4, t)]
    #
    #         if removed:
    #             for line in move_lines:
    #                 if line.exists():
    #                     for t in removed:
    #                         if t in line.tax_ids.ids:
    #                             line.tax_ids = [(3, t)]
    #     return res

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
    nhcl_tax_ids = fields.Many2many('account.tax', 'nhcl_tax_id', string='Tax', copy=False, compute='get_nhcl_tax_ids')

    def get_nhcl_tax_ids(self):
        for rec in self:
            rec.nhcl_tax_ids = False
            price = rec.price_unit
            taxes = False
            # Determine tax source
            if rec.sale_line_ids:
                taxes = rec.product_id.taxes_id.filtered(
                    lambda t: t.company_id == rec.company_id
                )
            elif rec.purchase_line_id:
                taxes = rec.product_id.supplier_taxes_id.filtered(
                    lambda t: t.company_id == rec.company_id
                )
            if not taxes:
                continue
            # If only one tax → assign directly
            if len(taxes) == 1:
                rec.nhcl_tax_ids = [(6, 0, taxes.ids)]
                continue
            # If multiple taxes → check min/max range
            matched_tax = taxes.filtered(
                lambda t: t.min_amount <= price <= t.max_amount
            )
            if matched_tax:
                rec.nhcl_tax_ids = [(6, 0, [matched_tax[0].id])]

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
    nhcl_tax_type = fields.Selection([
        ('tds', 'TDS'),
        ('tcs', 'TCS'),
        ('cess', 'Cess'),
    ], string='Tax Category')



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