from odoo import models,fields,api,_

class SalePersonIncentiveAgeingReport(models.Model):
    _name = 'sale.person.incentive.ageing.report'
    _description = "Sales Person Incentive Ageing Report"

    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    ref_company_id = fields.Many2one('res.company', string='Company', domain=lambda self: self._get_company_domain())
    sale_person = fields.Many2one('hr.employee', string='Sale Person')
    sale_person_incentive_ids = fields.One2many('sales.person.ageing.incentive.report.line', 'sale_person_incentive_id')

    @api.model
    def _get_company_domain(self):
        # Get the companies currently selected in the us
        #
        #
        # er's session context (allowed companies)
        allowed_company_ids = self.env.context.get('allowed_company_ids', [])

        # Apply the domain to show only the companies selected in the session
        return [('id', 'in', allowed_company_ids)] if allowed_company_ids else []

    @api.onchange('nhcl_store_id')
    def _onchange_get_ref_company(self):
        if self.nhcl_store_id:
            self.ref_company_id = self.nhcl_store_id.nhcl_store_name.sudo().company_id

    def action_check_sale_person_incentive_report(self):
        return

    def action_to_reset(self):
        self.sale_person = False
        self.from_date = False
        self.to_date = False
        self.ref_company_id = False
        self.sale_person_incentive_ids.unlink()

    def get_excel_sheet(self):
        return




class SetuSalesPersonAgeingIncentiveLine(models.TransientModel):
    _name = 'sales.person.ageing.incentive.report.line'
    _description = "Sales Person Incentive Report Lines"

    sale_person_incentive_id = fields.Many2one('sale.person.incentive.ageing.report', string="Sale Icentive Lines")
    sale_person_id = fields.Many2one('hr.employee', string='Sale Person')
    incentive_rule_name = fields.Char(string='Incentive Rule')
    base_value = fields.Float(string='Base Value')
    amount = fields.Float(string='Incentive Amount')
    ref_company_id = fields.Many2one('res.company', store=True)
    name = fields.Char(string="Order Reference")
    pos_date = fields.Date(string="POS Order Date")

