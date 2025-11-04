from odoo import models, api, _
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def getting_moves_in_dashboard(self):
        total_records = self.search([('nhcl_flag', 'in', ['n', 'y'])])
        processed_records = self.search([('nhcl_flag', '=', 'y')])
        pending_records = self.search([('nhcl_flag', '=', 'n')])

        return {
            'total_records': len(total_records),
            'processed_records': len(processed_records),
            'pending_records': len(pending_records),
        }


class AccountAccount(models.Model):
    _inherit = "account.account"

    @api.model
    def getting_accounts_in_dashboard(self):
        total_records = self.search([('nhcl_flag', 'in', ['n', 'y'])])
        processed_records = self.search([('nhcl_flag', '=', 'y')])
        pending_records = self.search([('nhcl_flag', '=', 'n')])

        return {
            'total_accounts': len(total_records),
            'processed_accounts': len(processed_records),
            'pending_accounts': len(pending_records),
        }


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.model
    def getting_customers_in_dashboard(self):
        domain = [('group_contact', '=', 'Customer')]
        total_records = self.search(domain + [('nhcl_flag', 'in', ['n', 'y'])])
        processed_records = self.search(domain + [('nhcl_flag', '=', 'y')])
        pending_records = self.search(domain + [('nhcl_flag', '=', 'n')])
        return {
            'total_customers': len(total_records),
            'processed_customers': len(processed_records),
            'pending_customers': len(pending_records),
        }

    @api.model
    def getting_vendors_in_dashboard(self):
        domain = [('group_contact', '=', 'Vendor')]
        total_records = self.search(domain + [('nhcl_flag', 'in', ['n', 'y'])])
        processed_records = self.search(domain + [('nhcl_flag', '=', 'y')])
        pending_records = self.search(domain + [('nhcl_flag', '=', 'n')])
        return {
            'total_vendors': len(total_records),
            'processed_vendors': len(processed_records),
            'pending_vendors': len(pending_records),
        }


class AccountGroup(models.Model):
    _inherit = 'account.group'

    @api.model
    def getting_groups_in_dashboard(self):
        total_records = self.search([('nhcl_flag', 'in', ['n', 'y'])])
        processed_records = self.search([('nhcl_flag', '=', 'y')])
        pending_records = self.search([('nhcl_flag', '=', 'n')])

        return {
            'total_groups': len(total_records),
            'processed_groups': len(processed_records),
            'pending_groups': len(pending_records),
        }


class Company(models.Model):
    _inherit = 'res.company'

    @api.model
    def getting_companies_in_dashboard(self):
        total_records = self.search([('nhcl_flag', 'in', ['n', 'y'])])
        processed_records = self.search([('nhcl_flag', '=', 'y')])
        pending_records = self.search([('nhcl_flag', '=', 'n')])

        return {
            'total_companies': len(total_records),
            'processed_companies': len(processed_records),
            'pending_companies': len(pending_records),
        }
