from odoo import models, fields, api


class HRApplicant(models.Model):
    _inherit = 'hr.applicant'

    company_id = fields.Many2one('res.company')
    multi_company_ids = fields.Many2many('res.company', string='Preferred Companies')
    experience_type = fields.Selection([
        ('fresher', 'Fresher'),
        ('experienced', 'Experienced')
    ], string="Experienced / Fresher")
    present_company = fields.Char(string="Present Working Company (or) Store")
    retail_experience_years = fields.Float(string="Total Years of Relevant(Fashion) Experience")
    current_salary = fields.Monetary(string="Current Salary")
    currency_id = fields.Many2one('res.currency', string="Currency", default=lambda self: self.env.company.currency_id)
    interview_form_id = fields.Many2one('hr.interview.form', string="Interview Form")

    permanent_street = fields.Char(string="Permanent Address")
    permanent_street2 = fields.Char(string="Permanent Street 2")
    permanent_city = fields.Char(string="Permanent City")
    permanent_state_id = fields.Many2one('res.country.state', string="Permanent State")
    permanent_zip = fields.Char(string="Permanent ZIP")
    permanent_country_id = fields.Many2one('res.country', string="Permanent Country")

    dob = fields.Date(string = "Date of Birth")
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female')
    ], string="Gender")
    marital_status = fields.Selection([
        ('single', 'Single'),
        ('married', 'Married')
    ], string="Marital Status")
    age = fields.Integer(string="Age")

    salary_type = fields.Selection([
        ('salary', 'Salary'),
        ('ctc', 'CTC')
    ], string="Salary Type")
    current_ctc = fields.Float(string="Current CTC")
    expected_ctc = fields.Float(string="Expected CTC")
    expected_ctc_extra = fields.Char(string="Proposed CTC Extra")
    proposed_ctc = fields.Float(string="Proposed CTC")
    proposed_ctc_extra = fields.Char(string="Proposed CTC Extra")



    @api.onchange('multi_company_ids')
    def _onchange_multi_company_ids(self):
        if self.multi_company_ids:
            if len(self.multi_company_ids) == 1:
                self.company_id = self.multi_company_ids[0]
            else:
                self.company_id = False











