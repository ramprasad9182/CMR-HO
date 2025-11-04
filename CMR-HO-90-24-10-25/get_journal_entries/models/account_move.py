from odoo import models, fields, api
from psycopg2.sql import SQL


class AccountMove(models.Model):
    _inherit = "account.move"

    nhcl_flag = fields.Selection([('n', 'N'), ('y', 'Y')], string='Flag', default='n', copy=False)
    update_flag = fields.Selection([('no_update', 'No Update'), ('update', 'Update')], string='Update Flag',
                                   default='no_update', copy=False)
    nhcl_tally_company_name = fields.Char(string="Tally Company")


    def write(self, vals):
        res = super(AccountMove, self).write(vals)
        if res and ('ref' in vals or 'narration' in vals) and self.update_flag == 'no_update':
            self.update_flag = 'update'
        return res

    @api.onchange('journal_id','company_id')
    def _compute_nhcl_tally_company_name(self):
        for move in self:
            company = move.journal_id.company_id
            state = company.state_id
            if state:
                state_master = self.env['state.master'].search([('state_id', '=', state.id)], limit=1)
                move.nhcl_tally_company_name = state_master.tally_company_name if state_master else False

class AccountAccount(models.Model):
    _inherit = "account.account"

    nhcl_flag = fields.Selection([('n', 'N'), ('y', 'Y')], string='Flag', default='n', copy=False)
    sequence = fields.Char(
        string="Sequence",
        default='New', readonly=True
    )
    update_flag = fields.Selection([('no_update', 'No Update'), ('update', 'Update')], string='Update Flag',
                                   default='no_update', copy=False)

    def write(self, vals):
        res = super(AccountAccount, self).write(vals)
        if res and 'name' in vals and self.update_flag == 'no_update':
            self.update_flag = 'update'
        return res

    @api.depends_context('company')
    @api.depends('code')
    def _compute_account_group(self):
        accounts_with_code = self.filtered(lambda a: a.code)

        (self - accounts_with_code).group_id = False

        if not accounts_with_code:
            return

        codes = accounts_with_code.mapped('code')
        values_placeholder = ', '.join(['(%s)'] * len(codes))
        # account_code_values = SQL(','.join(['(%s)'] * len(codes)), *codes)
        query = f"""
                           SELECT DISTINCT ON (account_code.code)
                                  account_code.code,
                                  agroup.id AS group_id
                             FROM (VALUES {values_placeholder}) AS account_code (code)
                        LEFT JOIN account_group agroup
                               ON agroup.code_prefix_start <= LEFT(account_code.code, char_length(agroup.code_prefix_start))
                                  AND agroup.code_prefix_end >= LEFT(account_code.code, char_length(agroup.code_prefix_end))
                                  AND agroup.company_id = %s
                         ORDER BY account_code.code, char_length(agroup.code_prefix_start) DESC, agroup.id
                       """

        params = codes + [self.env.company.root_id.id]
        self.env.cr.execute(query, params)
        results = self.env.cr.fetchall()
        # print("++++++++++++++++++++++++++++++=", results)
        group_by_code = dict(results)
        # print("++++++++++++++++++++++++++++++=", group_by_code)

        for account in accounts_with_code:
            group_id = group_by_code.get(account.code)
            account.group_id = group_id

            # ✅ Also auto-assign sequence from group
            if group_id:
                print(group_id)
                group = self.env['account.group'].browse(group_id)
                if group.sequence and (account.sequence == 'New' or not account.sequence):
                    account.sequence = group.sequence

        # account_code_values = SQL(','.join(['(%s)'] * len(codes)), *codes)
        # results = self.env.execute_query(SQL(
        #     """
        #          SELECT DISTINCT ON (account_code.code)
        #                 account_code.code,
        #                 agroup.id AS group_id
        #            FROM (VALUES %(account_code_values)s) AS account_code (code)
        #       LEFT JOIN account_group agroup
        #              ON agroup.code_prefix_start <= LEFT(account_code.code, char_length(agroup.code_prefix_start))
        #                 AND agroup.code_prefix_end >= LEFT(account_code.code, char_length(agroup.code_prefix_end))
        #                 AND agroup.company_id = %(root_company_id)s
        #        ORDER BY account_code.code, char_length(agroup.code_prefix_start) DESC, agroup.id
        #     """,
        #     account_code_values=account_code_values,
        #     root_company_id=self.env.company.root_id.id,
        # ))
        # group_by_code = dict(results)


class AccountGroup(models.Model):
    _inherit = "account.group"

    type = fields.Selection([
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('equity', 'Equity'),
        ('revenue', 'Revenue'),
        ('expenditure', 'Expenditure'),
        ('others', 'Others'),
    ], string="Type")
    flag_type = fields.Boolean('Flag')
    sequence = fields.Char('Sequence', default='New')

    asset_sub_type = fields.Selection([
        ('receivable', 'Receivable'),
        ('bank_cash', 'Bank & Cash'),
        ('current_assets', 'Current Assets'),
        ('non_current_assets', 'Non Current Assets'),
        ('prepayments', 'Prepayments'),
        ('fixed_assets', 'Fixed Assets'),
    ], string="Sub Type")
    liability_sub_type = fields.Selection([
        ('payable', 'Payable'),
        ('credit_card', 'Credit Card'),
        ('current_liabilities', 'Current Liabilities'),
        ('non_current_liabilities', 'Non Current Liabilities'),
    ], string="Sub Type")
    equity_sub_type = fields.Selection([
        ('equity', 'Equity'),
        ('current_year_earnings', 'Current Year Earnings'),
    ], string="Sub Type")
    revenue_sub_type = fields.Selection([
        ('income', 'Income'),
        ('other_income', 'Other Income'),
    ], string="Sub Type")
    expense_sub_type = fields.Selection([
        ('expenses', 'Expenses'),
        ('depreciation', 'Depreciation'),
        ('cost_of_revenue', 'Cost of Revenue'),
    ], string="Sub Type")
    other_sub_type = fields.Selection([
        ('off_balance', 'Off Balance'),
    ], string="Sub Type")
    nhcl_flag = fields.Selection([('n', 'N'), ('y', 'Y')], string='Flag', default='n', copy=False)
    update_flag = fields.Selection([('no_update', 'No Update'), ('update', 'Update')], string='Update Flag', default='no_update', copy=False)


    def write(self,vals):
        res = super(AccountGroup, self).write(vals)
        if res and 'name' in vals:
            self.update_flag = 'update'
        if 'code_prefix_start' in vals or 'code_prefix_end' in vals:
            for group in self:
                domain = [
                    ('code', '>=', group.code_prefix_start),
                    ('code', '<=', group.code_prefix_end),
                    ('company_id', '=', group.company_id.id),
                ]
                accounts = self.env['account.account'].search(domain)
                accounts._compute_account_group()

        return res


    _sequence_code_map = {
        'asset': 'account.group.asset',
        'liability': 'account.group.liability',
        'equity': 'account.group.equity',
        'revenue': 'account.group.revenue',
        'expenditure': 'account.group.expenditure',
        'others': 'account.group.others',
    }

    @api.model
    def create(self, vals):
        if vals.get('sequence', 'New') == 'New' and vals.get('type'):
            type_code = vals['type']
            seq_code = self._sequence_code_map.get(type_code)
            if seq_code:
                vals['sequence'] = self.env['ir.sequence'].next_by_code(seq_code)
        return super(AccountGroup, self).create(vals)


class ResPartner(models.Model):
    _inherit = "res.partner"

    nhcl_flag = fields.Selection([('n', 'N'), ('y', 'Y')], string='Flag', default='n', copy=False)
    update_flag = fields.Selection([('no_update', 'No Update'), ('update', 'Update')], string='Update Flag',
                                   default='no_update', copy=False)

    def write(self, vals):
        res = super(ResPartner, self).write(vals)
        if res and ('name' in vals or 'property_supplier_payment_term_id' in vals):
            self.update_flag = 'update'
        return res


class ResCompany(models.Model):
    _inherit = "res.company"

    nhcl_flag = fields.Selection([('n', 'N'), ('y', 'Y')], string='Flag', default='n', copy=False)


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    nhcl_flag = fields.Selection([('n', 'N'), ('y', 'Y')], string='Flag', default='n', copy=False)

class StockLocation(models.Model):
    _inherit = "stock.location"

    nhcl_flag = fields.Selection([('n', 'N'), ('y', 'Y')], string='Flag', default='n', copy=False)
