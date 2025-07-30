from datetime import date
from email.policy import default

from odoo import models,fields,api,_
from odoo.exceptions import ValidationError


class TallyIntegration(models.Model):
    _name="tally.integration"
    _description = "Tally Integration Screen"
    _rec_name = "name"


    name = fields.Char(string='Doc No', required=True, copy=False, readonly=True, default='New')
    user_id = fields.Many2one("res.users", string="Created By", default=lambda self: self.env.user)
    posting_type = fields.Selection([
        ('single', 'Single'),
        ('multiple', 'Multiple'),
    ], string="Posting Type")
    today_date = fields.Date(default=lambda self: date.today(),string="Created On")
    active_record = fields.Boolean(string="Active")
    company = fields.Many2one("res.company", default=lambda self: self.env.company, string="Base Company")
    odoo_server = fields.Char(string="Odoo Server")
    odoo_ip = fields.Char(string="Odoo IP")
    odoo_db = fields.Char(string="Odoo DB")
    odoo_user = fields.Char(string="Odoo User")
    odoo_password = fields.Char(string="Odoo Password")
    tally_server = fields.Char(string="SAP Server")
    tally_ip = fields.Char(string="SAP IP")
    tally_db = fields.Char(string="SAP DB")
    tally_user = fields.Char(string="SAP User")
    tally_password = fields.Char(string="SAP Password")
    api_key=fields.Char(string="Api Key")


    account_group = fields.Boolean(string="Account Group")
    coa = fields.Boolean(string="Chart of Accounts")
    customers = fields.Boolean(string="Customers")
    vendors = fields.Boolean(string="Vendors")
    company_enable = fields.Boolean(string="Company")
    warehouse_enable = fields.Boolean(string="Warehouse")
    location_enable = fields.Boolean(string="Locations")

    sale_invoice = fields.Boolean(string="Sale Invoice",default=True,readonly=True)
    sale_credit_note = fields.Boolean(string="Sale Credit Note",default=True,readonly=True)
    purchase_invoice = fields.Boolean(string="Purchase Invoice",default=True,readonly=True)
    purchase_credit_note = fields.Boolean(string="Purchase Credit Note",default=True,readonly=True)
    journal_entries = fields.Boolean(string="Journal Entries")

    account_group_tally_company_ids = fields.Many2many("state.master",  relation="account_group_tally_company_rel", string="Tally company for Account Groups")
    coa_tally_company_ids = fields.Many2many("state.master", relation="coa_tally_company_rel",string="Tally company for COA")
    customers_tally_company_ids = fields.Many2many("state.master",  relation="customers_tally_company_rel",string="Tally company for Customers")
    vendors_tally_company_ids = fields.Many2many("state.master",  relation="vendors_tally_company_rel",string="Tally company for Vendors")

    account_group_tally_company_code_ids = fields.Text(string="Tally company code for AG",compute="_compute_all_tally_company_codes", readonly=True)
    coa_tally_company_code_ids = fields.Text(string="Tally company code for COA", compute="_compute_all_tally_company_codes",readonly=True)
    customers_tally_company_code_ids = fields.Text(string="Tally company code for Customer",compute="_compute_all_tally_company_codes",readonly=True)
    vendors_tally_company_code_ids = fields.Text(string="Tally company code for Vendor", compute="_compute_all_tally_company_codes",readonly=True)




    sale_invoice_tally_company_ids = fields.Many2many("state.master", relation="sale_invoice_tally_company_rel",
                                                      string="Tally company for Sale Invoice")
    sale_credit_note_tally_company_ids = fields.Many2many("state.master", relation="sale_credit_note_tally_company_rel",
                                                          string="Tally company for Sale Credit Note")
    purchase_invoice_tally_company_ids = fields.Many2many("state.master", relation="purchase_invoice_tally_company_rel",
                                                          string="Tally company for Purchase Invoice")
    purchase_credit_note_tally_company_ids = fields.Many2many("state.master",
                                                              relation="purchase_credit_note_tally_company_rel",
                                                              string="Tally company for Purchase Credit Note")
    journal_entries_tally_company_ids = fields.Many2many("state.master", relation="journal_entries_tally_company_rel",
                                                         string="Tally company for Journal Entries")

    sale_invoice_tally_company_code_ids = fields.Text(string="Tally company code for SI", compute="_compute_all_tally_company_codes" ,readonly=True)
    sale_credit_note_tally_company_code_ids = fields.Text(string="Tally company code for SCN", compute="_compute_all_tally_company_codes",readonly=True)
    purchase_invoice_tally_company_code_ids = fields.Text(string="Tally company code for PI",compute="_compute_all_tally_company_codes", readonly=True)
    purchase_credit_note_tally_company_code_ids = fields.Text(string="Tally company code for PCN", compute="_compute_all_tally_company_codes",readonly=True)
    journal_entries_tally_company_code_ids = fields.Text(string="Tally company code for JE", compute="_compute_all_tally_company_codes",readonly=True)

    account_group_tally_company_name_ids = fields.Text(
        string="Tally company name for AG", compute="_compute_all_tally_company_codes", readonly=True)
    coa_tally_company_name_ids = fields.Text(
        string="Tally company name for COA", compute="_compute_all_tally_company_codes", readonly=True)
    customers_tally_company_name_ids = fields.Text(
        string="Tally company name for Customer", compute="_compute_all_tally_company_codes", readonly=True)
    vendors_tally_company_name_ids = fields.Text(
        string="Tally company name for Vendor", compute="_compute_all_tally_company_codes", readonly=True)

    sale_invoice_tally_company_name_ids = fields.Text(
        string="Tally company name for SI", compute="_compute_all_tally_company_codes", readonly=True)
    sale_credit_note_tally_company_name_ids = fields.Text(
        string="Tally company name for SCN", compute="_compute_all_tally_company_codes", readonly=True)
    purchase_invoice_tally_company_name_ids = fields.Text(
        string="Tally company name for PI", compute="_compute_all_tally_company_codes", readonly=True)
    purchase_credit_note_tally_company_name_ids = fields.Text(
        string="Tally company name for PCN", compute="_compute_all_tally_company_codes", readonly=True)
    journal_entries_tally_company_name_ids = fields.Text(
        string="Tally company name for JE", compute="_compute_all_tally_company_codes", readonly=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('tally.integration') or 'New'
        return super().create(vals)

    # @api.constrains('posting_type')
    # def _check_posting_type(self):
    #     for rec in self:
    #         if rec.posting_type in ('none',False):
    #             raise ValidationError("Please select a valid Posting Type.")

    @api.depends(
        'account_group_tally_company_ids',
        'coa_tally_company_ids',
        'customers_tally_company_ids',
        'vendors_tally_company_ids',
        'sale_invoice_tally_company_ids',
        'sale_credit_note_tally_company_ids',
        'purchase_invoice_tally_company_ids',
        'purchase_credit_note_tally_company_ids',
        'journal_entries_tally_company_ids',
    )
    def _compute_all_tally_company_codes(self):
        for rec in self:
            rec.account_group_tally_company_code_ids = ', '.join(
                filter(None, rec.account_group_tally_company_ids.mapped('tally_company_code')))
            rec.account_group_tally_company_name_ids = ', '.join(
                filter(None, rec.account_group_tally_company_ids.mapped('tally_company_name')))

            rec.coa_tally_company_code_ids = ', '.join(
                filter(None, rec.coa_tally_company_ids.mapped('tally_company_code')))
            rec.coa_tally_company_name_ids = ', '.join(filter(None, rec.coa_tally_company_ids.mapped('tally_company_name')))

            rec.customers_tally_company_code_ids = ', '.join(
                filter(None, rec.customers_tally_company_ids.mapped('tally_company_code')))
            rec.customers_tally_company_name_ids = ', '.join(
                filter(None, rec.customers_tally_company_ids.mapped('tally_company_name')))

            rec.vendors_tally_company_code_ids = ', '.join(
                filter(None, rec.vendors_tally_company_ids.mapped('tally_company_code')))
            rec.vendors_tally_company_name_ids = ', '.join(
                filter(None, rec.vendors_tally_company_ids.mapped('tally_company_name')))

            rec.sale_invoice_tally_company_code_ids = ', '.join(
                filter(None, rec.sale_invoice_tally_company_ids.mapped('tally_company_code')))
            rec.sale_invoice_tally_company_name_ids = ', '.join(
                filter(None, rec.sale_invoice_tally_company_ids.mapped('tally_company_name')))

            rec.sale_credit_note_tally_company_code_ids = ', '.join(
                filter(None, rec.sale_credit_note_tally_company_ids.mapped('tally_company_code')))
            rec.sale_credit_note_tally_company_name_ids = ', '.join(
                filter(None, rec.sale_credit_note_tally_company_ids.mapped('tally_company_name')))

            rec.purchase_invoice_tally_company_code_ids = ', '.join(
                filter(None, rec.purchase_invoice_tally_company_ids.mapped('tally_company_code')))
            rec.purchase_invoice_tally_company_name_ids = ', '.join(
                filter(None, rec.purchase_invoice_tally_company_ids.mapped('tally_company_name')))

            rec.purchase_credit_note_tally_company_code_ids = ', '.join(
                filter(None, rec.purchase_credit_note_tally_company_ids.mapped('tally_company_code')))
            rec.purchase_credit_note_tally_company_name_ids = ', '.join(
                filter(None, rec.purchase_credit_note_tally_company_ids.mapped('tally_company_name')))

            rec.journal_entries_tally_company_code_ids = ', '.join(
                filter(None, rec.journal_entries_tally_company_ids.mapped('tally_company_code')))
            rec.journal_entries_tally_company_name_ids = ', '.join(
                filter(None, rec.journal_entries_tally_company_ids.mapped('tally_company_name')))

    @api.onchange(
        'account_group_tally_company_ids',
        'coa_tally_company_ids',
        'customers_tally_company_ids',
        'vendors_tally_company_ids',
        'sale_invoice_tally_company_ids',
        'sale_credit_note_tally_company_ids',
        'purchase_invoice_tally_company_ids',
        'purchase_credit_note_tally_company_ids',
        'journal_entries_tally_company_ids',
        'posting_type'
    )
    def _onchange_company_selection_limit(self):
        if self.posting_type == 'single':
            warning_fields = []

            if len(self.account_group_tally_company_ids) > 1:
                self.account_group_tally_company_ids = False
                warning_fields.append("Account Group")

            if len(self.coa_tally_company_ids) > 1:
                self.coa_tally_company_ids = False
                warning_fields.append("Chart of Accounts")

            if len(self.customers_tally_company_ids) > 1:
                self.customers_tally_company_ids = False
                warning_fields.append("Customers")

            if len(self.vendors_tally_company_ids) > 1:
                self.vendors_tally_company_ids = False
                warning_fields.append("Vendors")

            if len(self.sale_invoice_tally_company_ids) > 1:
                self.sale_invoice_tally_company_ids = False
                warning_fields.append("Sale Invoice")

            if len(self.sale_credit_note_tally_company_ids) > 1:
                self.sale_credit_note_tally_company_ids = False
                warning_fields.append("Sale Credit Note")

            if len(self.purchase_invoice_tally_company_ids) > 1:
                self.purchase_invoice_tally_company_ids = False
                warning_fields.append("Purchase Invoice")

            if len(self.purchase_credit_note_tally_company_ids) > 1:
                self.purchase_credit_note_tally_company_ids = False
                warning_fields.append("Purchase Credit Note")

            if len(self.journal_entries_tally_company_ids) > 1:
                self.journal_entries_tally_company_ids = False
                warning_fields.append("Journal Entries")

            if warning_fields:
                return {
                    'warning': {
                        'title': "Company Selection Restricted",
                        'message': (
                                "Only one company can be selected for the following fields when "
                                "Posting Type is 'Single':\n- " + '\n- '.join(warning_fields)
                        )
                    }
                }
        elif self.posting_type is False:
            # Only trigger if the user has actually selected any company fields
            if any([
                self.account_group_tally_company_ids,
                self.coa_tally_company_ids,
                self.customers_tally_company_ids,
                self.vendors_tally_company_ids,
                self.sale_invoice_tally_company_ids,
                self.sale_credit_note_tally_company_ids,
                self.purchase_invoice_tally_company_ids,
                self.purchase_credit_note_tally_company_ids,
                self.journal_entries_tally_company_ids
            ]):
                # Reset the selections
                self.account_group_tally_company_ids = False
                self.coa_tally_company_ids = False
                self.customers_tally_company_ids = False
                self.vendors_tally_company_ids = False
                self.sale_invoice_tally_company_ids = False
                self.sale_credit_note_tally_company_ids = False
                self.purchase_invoice_tally_company_ids = False
                self.purchase_credit_note_tally_company_ids = False
                self.journal_entries_tally_company_ids = False

                return {
                    'warning': {
                        'title': "Posting Type Required",
                        'message': "Please select a Posting Type before selecting company fields."
                    }
                }

    # when the checkbox enable, must be select the state
    @api.constrains('account_group', 'account_group_tally_company_ids', 'customers', 'vendors',
                    'customers_tally_company_ids', 'vendors_tally_company_ids', 'coa', 'coa_tally_company_ids')
    def _check_account_group_tally_company_ids(self):
        for rec in self:
            if rec.account_group and not rec.account_group_tally_company_ids:
                raise ValidationError("Please select Tally Company for Account Groups when Account Group is enabled.")
            elif rec.customers and not rec.customers_tally_company_code_ids:
                raise ValidationError("Please select Tally Company for Customer when Customer Master is enabled.")
            elif rec.vendors and not rec.vendors_tally_company_code_ids:
                raise ValidationError("Please select Tally Company for Vendors when Vendor Master is enabled.")
            elif rec.coa and not rec.coa_tally_company_ids:
                raise ValidationError("Please select Tally Company for Chat of Accounts when COA Master is enabled.")

