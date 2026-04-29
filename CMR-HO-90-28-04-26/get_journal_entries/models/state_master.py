from odoo import models, fields, api

class StateMaster(models.Model):
    _name = "state.master"
    _rec_name = 'state_id'


    state_id = fields.Many2one(comodel_name='res.country.state', string='State',
                               domain=[('country_id.code', '=', 'IN')],required = True)
    tally_company_name = fields.Char(string="Tally Company Name",required = True)
    tally_company_code = fields.Char(string="Tally Company Code")









