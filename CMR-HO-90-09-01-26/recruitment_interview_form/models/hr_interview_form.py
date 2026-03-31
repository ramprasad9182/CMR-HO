from odoo import models, fields, api
import base64
import qrcode
import io
import uuid

class HRInterviewForm(models.Model):
    _name = 'hr.interview.form'
    _description = 'Interview Form'

    name = fields.Char("Form Title", required=True)
    partner_id = fields.Many2one('res.partner', string="Recipient")
    access_token = fields.Char("Access Token", default=lambda self: str(uuid.uuid4()), readonly=True)
    show_name = fields.Char("1. Name as per Aadhar", readonly=True)
    show_email = fields.Char("2. Email Address ", readonly=True)
    show_mobile = fields.Char("3. Mobile Number", readonly=True)
    show_phone = fields.Char("4. Alternate Mobile Number", readonly=True)
    show_dob = fields.Char("5. Date of birth", readonly=True)
    show_age = fields.Char("6. Age", readonly=True)
    show_gender = fields.Char("7. Gender", readonly=True)
    show_marital = fields.Char("8. Marital Status", readonly=True)
    show_current_address = fields.Char("9. Current Address", readonly=True)
    show_prefer_company = fields.Char("10. Prefer Companies", readonly=True)
    show_company = fields.Char("11. Which position are you applying", readonly=True)
    show_dept = fields.Char("12. Department", readonly=True)
    show_experience_type = fields.Char("13. Experience Type", readonly=True)
    show_total_exp = fields.Char(string="14. Total Experience (Years)", readonly=True)
    show_retail_experience_years = fields.Char("15. Total Years of  relevant(Fashion) Experience", readonly=True)
    show_emp_details = fields.Char("16. Previous Employment Details", readonly=True)
    show_ref_details = fields.Char("17. Reference Details", readonly=True)
    show_edu_details = fields.Char("18. Educational Details", readonly=True)

    applicant_count = fields.Integer(string="Applicants", compute="_compute_applicant_count")

    @api.depends()
    def _compute_applicant_count(self):
        for rec in self:
            rec.applicant_count = self.env['hr.applicant'].search_count([('interview_form_id', '=', rec.id)])

    def action_view_applicants(self):
        self.ensure_one()
        action = self.env.ref('hr_recruitment.crm_case_categ0_act_job').read()[0]
        action['domain'] = [('interview_form_id', '=', self.id)]
        action['context'] = {'default_interview_form_id': self.id}
        return action

    def get_form_url(self):
        return f"/form/{self.access_token}"


    def get_qr_code_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        full_url = f"{base_url}{self.get_form_url()}"

        qr = qrcode.QRCode()
        qr.add_data(full_url)
        qr.make(fit=True)
        img = qr.make_image(fill="black", back_color="white")
        stream = io.BytesIO()
        img.save(stream, format="PNG")
        qr_code = base64.b64encode(stream.getvalue()).decode()
        return f"data:image/png;base64,{qr_code}"

    def action_open_link_wizard(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'survey.email.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'active_id': self.id},
        }

    def action_print_qr(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        form_url = f"{base_url}{self.get_form_url()}"

        qr = qrcode.QRCode()
        qr.add_data(form_url)
        qr.make(fit=True)
        img = qr.make_image(fill="black", back_color="white")

        # Save QR image to stream
        stream = io.BytesIO()
        img.save(stream, format="PNG")
        qr_img_data = stream.getvalue()

        # Create an attachment to serve as download
        attachment = self.env['ir.attachment'].create({
            'name': f'QR_{self.name}.png',
            'type': 'binary',
            'datas': base64.b64encode(qr_img_data),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'image/png',
        })

        download_url = f'/web/content/{attachment.id}?download=true'
        return {
            'type': 'ir.actions.act_url',
            'url': download_url,
            'target': 'self',
        }



