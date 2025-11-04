# -*- coding: utf-8 -*-
from odoo import fields, models, api, exceptions, _

class Company(models.Model):
    _inherit = "res.company"

    sepration_credit_account_id = fields.Many2one('account.account', string="Credit Account")
    sepration_debit_account_id = fields.Many2one('account.account', string="Debit Account")

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sepration_credit_account_id = fields.Many2one('account.account', related="company_id.sepration_credit_account_id", string="Credit Account", readonly=False)
    sepration_debit_account_id = fields.Many2one('account.account', related="company_id.sepration_debit_account_id", string="Debit Account", readonly=False)

class HrWorkEntryType(models.Model):
    _inherit = 'hr.work.entry.type'

    is_paid = fields.Boolean('Is Paid')

class AccountMove(models.Model):
    _inherit = 'account.move'

    emp_settlement_id = fields.Many2one('hr.employee.settlement',string='Employee Settlement')


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    is_salary_wages = fields.Boolean(string="Salaries and wages")

class HrContract(models.Model):
    _inherit = 'hr.contract'

    gross_amount = fields.Float(string="Gross Amount")
    net_amount = fields.Float(string="Net Amount")
