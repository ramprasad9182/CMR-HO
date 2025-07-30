from odoo import models, fields, api, _

class SurveyEmailWizard(models.TransientModel):
    _name = 'survey.email.wizard'
    _description = 'Wizard to Send Interview Form Email'

    partner_id = fields.Many2one('res.partner', string="Recipient", required=True)
    email = fields.Char(string="Email", related='partner_id.email')
    form_id = fields.Many2one('hr.interview.form', required=True, readonly=True)
    survey_link = fields.Char("Survey Link", readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        form = self.env['hr.interview.form'].browse(self._context.get('active_id'))
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        res['form_id'] = form.id
        res['survey_link'] = f"{base_url}/form/{form.access_token}"
        return res

    def action_send_email(self):
        template = self.env.ref('recruitment_interview_form.email_template_interview_form')  # replace with your template ID
        active_id = self.env.context.get('active_id')
        interview_form = self.env['hr.interview.form'].browse(active_id)

        # You may want to update the form with recipient
        interview_form.write({'partner_id': self.partner_id.id})

        template.send_mail(interview_form.id, force_send=True)
        return {'type': 'ir.actions.act_window_close'}
