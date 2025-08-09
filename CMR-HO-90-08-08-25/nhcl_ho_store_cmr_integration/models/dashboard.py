from odoo import models, fields, api, _
from datetime import date

class AccountAccount(models.Model):
    _inherit = "account.account"

    @api.model
    def get_pending_account(self):
        pending_account = self.env['account.account'].search_count([('update_replication','=',False)])
        return {
            'pending_account': f"{pending_account:,}",
        }

    @api.model
    def get_processed_account(self):
        processed_account = self.env['account.account'].search_count([('update_replication', '=', True)])
        return {
            'processed_account': f"{processed_account:,}",
        }

    @api.model
    def get_total_account(self):
        total_account = self.env['account.account'].search_count([])
        return {
            'total_account': f"{total_account:,}",
        }



class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def get_pending_tax(self):
        pending_tax = self.search_count([('update_replication', '=', False)])
        return {
            'pending_tax': f"{pending_tax:,}",
        }

    @api.model
    def get_processed_tax(self):
        processed_tax = self.search_count([('update_replication', '=', True)])
        return {
            'processed_tax': f"{processed_tax:,}",
        }

    @api.model
    def get_total_tax(self):
        total_tax = self.search_count([])
        return {
            'total_tax': f"{total_tax:,}",
        }


class AccountFiscalYear(models.Model):
    _inherit = "account.fiscal.year"

    @api.model
    def get_pending_fiscal(self):
        pending_fiscal = self.search_count([('update_replication', '=', False)])
        return {
            'pending_fiscal': f"{pending_fiscal:,}",
        }

    @api.model
    def get_processed_fiscal(self):
        processed_fiscal = self.search_count([('update_replication', '=', True)])
        return {
            'processed_fiscal': f"{processed_fiscal:,}",
        }

    @api.model
    def get_total_fiscal(self):
        total_fiscal = self.search_count([])
        return {
            'total_fiscal': f"{total_fiscal:,}",
        }


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def get_pending_employee(self):
        pending_employee = self.search_count([('update_replication', '=', False)])
        return {
            'pending_employee': f"{pending_employee:,}",
        }

    @api.model
    def get_processed_employee(self):
        processed_employee = self.search_count([('update_replication', '=', True)])
        return {
            'processed_employee': f"{processed_employee:,}",
        }

    @api.model
    def get_total_employee(self):
        total_employee = self.search_count([])
        return {
            'total_employee': f"{total_employee:,}",
        }

class Contact(models.Model):
    _inherit = "res.partner"

    @api.model
    def get_pending_partner(self):
        pending_partner = self.search_count([('update_replication', '=', False)])
        return {
            'pending_partner': f"{pending_partner:,}",
        }

    @api.model
    def get_processed_partner(self):
        processed_partner = self.search_count([('update_replication', '=', True)])
        return {
            'processed_partner': f"{processed_partner:,}",
        }

    @api.model
    def get_total_partner(self):
        total_partner = self.search_count([])
        return {
            'total_partner': f"{total_partner:,}",
        }



class ProductTemplate(models.Model):
    _inherit = 'product.template'


    @api.model
    def get_pending_template(self):
        pending_template = self.env['product.template'].search_count([('update_replication','=',False)])
        return {
            'pending_template': f"{pending_template:,}",
        }

    @api.model
    def get_processed_template(self):
        processed_template = self.env['product.template'].search_count([('update_replication', '=', True)])
        return {
            'processed_template': f"{processed_template:,}",
        }

    @api.model
    def get_total_template(self):
        total_template = self.search_count([])
        return {
            'total_template': f"{total_template:,}",
        }

class ProductCategory(models.Model):
    _inherit = "product.category"

    @api.model
    def get_pending_category(self):
        pending_category = self.search_count([('update_replication', '=', False)])
        return {
            'pending_category': f"{pending_category:,}",
        }

    @api.model
    def get_processed_category(self):
        processed_category = self.search_count([('update_replication', '=', True)])
        return {
            'processed_category': f"{processed_category:,}",
        }

    @api.model
    def get_total_category(self):
        total_category = self.search_count([])
        return {
            'total_category': f"{total_category:,}",
        }

class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def get_pending_product(self):
        pending_product = self.search_count([('update_replication', '=', False)])
        return {
            'pending_product': f"{pending_product:,}",
        }

    @api.model
    def get_processed_product(self):
        processed_product = self.search_count([('update_replication', '=', True)])
        return {
            'processed_product': f"{processed_product:,}",
        }

    @api.model
    def get_total_product(self):
        total_product = self.search_count([])
        return {
            'total_product': f"{total_product:,}",
        }


class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"

    @api.model
    def get_pending_loyalty(self):
        pending_loyalty = self.search_count([('update_replication', '=', False)])
        return {
            'pending_loyalty': f"{pending_loyalty:,}",
        }
    @api.model
    def get_processed_loyalty(self):
        processed_loyalty = self.search_count([('update_replication', '=', True)])
        return {
            'processed_loyalty': f"{processed_loyalty:,}",
        }

    @api.model
    def get_total_loyalty(self):
        total_loyalty = self.search_count([])
        return {
            'total_loyalty': f"{total_loyalty:,}",
        }


class ProductAttribute(models.Model):
    _inherit = "product.attribute"


    @api.model
    def get_pending_attribute(self):
        pending_attribute = self.search_count([('update_replication', '=', False)])
        return {
            'pending_attribute': f"{pending_attribute:,}",
        }

    @api.model
    def get_processed_attribute(self):
        processed_attribute = self.search_count([('update_replication', '=', True)])
        return {
            'processed_attribute': f"{processed_attribute:,}",
        }

    @api.model
    def get_total_attribute(self):
        total_attribute = self.search_count([])
        return {
            'total_attribute': f"{total_attribute:,}",
        }

class Users(models.Model):
    _inherit = 'res.users'

    @api.model
    def get_pending_users(self):
        pending_users = self.search_count([('update_replication', '=', False)])
        return {
            'pending_users': f"{pending_users:,}",
        }

    @api.model
    def get_processed_users(self):
        processed_users = self.search_count([('update_replication', '=', True)])
        return {
            'processed_users': f"{processed_users:,}",
        }

    @api.model
    def get_total_users(self):
        total_users = self.search_count([])
        return {
            'total_users': f"{total_users:,}",
        }

class HoStoreMaster(models.Model):
    _inherit = "nhcl.ho.store.master"


    @api.model
    def get_total_liveSync(self):
        total_liveSync = self.search_count([('nhcl_active', '=', True)])
        return {
            'total_liveSync': f"{total_liveSync:,}",
        }


    @api.model
    def get_total_liveStore(self):
        total_liveStore = self.search_count([])
        return {
            'total_liveStore': f"{total_liveStore:,}",
        }

class TransactionReplicationLog(models.Model):
    _inherit = 'nhcl.transaction.replication.log'



    @api.model
    def get_total_transactionEvent(self):
        total_transactionEvent = self.search_count([])
        return {
            'total_transactionEvent': f"{total_transactionEvent:,}",
        }

    @api.model
    def get_total_transactionToday(self):
        # Get today's date
        today_date = date.today()
        # Count records where nhcl_date_of_log equals today's date
        total_transactionToday = self.search_count([('nhcl_date_of_log', '=', today_date)])
        return {
            'total_transactionToday': f"{total_transactionToday:,}",
        }

class OldStoreReplicationLog(models.Model):
    _inherit = 'nhcl.old.store.replication.log'


    @api.model
    def get_total_processedEvent(self):
        total_processedEvent = self.search_count([])
        return {
            'total_processedEvent': f"{total_processedEvent:,}",
        }

    @api.model
    def get_total_processedToday(self):
        # Get today's date
        today_date = date.today()
        # Count records where nhcl_date_of_log equals today's date
        total_processedToday = self.search_count([('nhcl_date_of_log', '=', today_date)])
        return {
            'total_processedToday': f"{total_processedToday:,}",
        }
