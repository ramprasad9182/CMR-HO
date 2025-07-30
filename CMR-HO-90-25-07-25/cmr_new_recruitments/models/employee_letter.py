import base64

from odoo import models, fields, api, _
import logging

from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class EmployeeLetter(models.Model):
    _name = 'employee.letter'
    _description = 'Employee Letter'
    _rec_name = 'employee_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Reference", compute="_compute_name", store=True)

    @api.depends('employee_id', 'todays_date')
    def _compute_name(self):
        for rec in self:
            if rec.employee_id and rec.todays_date:
                rec.name = f"{rec.employee_id.name} - {rec.todays_date.strftime('%Y-%m-%d')}"
            elif rec.employee_id:
                rec.name = rec.employee_id.name
            else:
                rec.name = "Offer Letter"

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)


    todays_date = fields.Date(string="Date", default=fields.Date.today)
    date_of_joining = fields.Date(string='Date Of Joining')
    ctc_offer = fields.Float(string='CTC', compute="_compute_ctc_offer", store=True)
    designation_id = fields.Many2one('hr.job', string="Designation")

    ctc_type = fields.Selection([
        ('with_bonus', 'With Bonus'),
        ('without_bonus', 'Without Bonus'),
        ('non_ctc', 'Non Ctc'),
    ], string='CTC Type', required='True')

    # Annual Fields
    ctc = fields.Float(string="CTC (Per Annum)")
    basic = fields.Float(string="BASIC (Per Annum)", compute="_compute_basic", store=True)
    hra = fields.Float(string="HRA (Per Annum)", compute="_compute_hra", store=True)
    other_allowance = fields.Float(string="OTHER ALLOWANCE (Per Annum)", compute="_compute_other_allowance", store=True)
    pf = fields.Float(string="PF (Per Annum)")
    pt = fields.Float(string="PT (Per Annum)")
    net_take_home = fields.Float(string="NET TAKE HOME (Per Annum)", compute="_compute_net_take_home", store=True)
    family_insurance = fields.Float(string="FAMILY INSURANCE (Per Annum)", compute="_compute_family_insurance_m")
    bonus = fields.Float(string="BONUS (Per Annum)", compute="_compute_bonus", store=True)

    # Monthly Fields
    ctc_m = fields.Float(string="CTC (Per Month)")
    basic_m = fields.Float(string="BASIC (Per Month)", compute="_compute_basic_m", store=True)
    hra_m = fields.Float(string="HRA (Per Month)", compute='_compute_hra_m', store=True)
    other_allowance_m = fields.Float(string="OTHER ALLOWANCE (Per Month)", compute='_compute_other_allowance_m',
                                     store=True)
    pf_m = fields.Float(string="PF (Per Month)", compute='_compute_pf_amount', store=True)
    pt_m = fields.Float(string="PT (Per Month)", compute='_compute_pt_m', store=True)
    net_take_home_m = fields.Float(string="NET TAKE HOME (Per Month)", compute='_compute_net_take_home_m', store=True)
    family_insurance_m = fields.Float(string="FAMILY INSURANCE (Per Month)")
    applicant_name = fields.Char(string='Applicant Name')
    todays_date = fields.Date(string="Date", default=fields.Date.today)
    date_of_joining = fields.Date(string='Date Of Joining', default=fields.Date.today)
    ctc_offer = fields.Float(string='CTC', compute='_compute_ctc_offer')
    designation = fields.Char(string="Designation")
    email_stage = fields.Selection([
        ('draft', 'Draft'),
        ('fetched', 'Details Fetched'),
        ('quotation_sent', 'Quotation Sent'),
        ('appointment_sent', 'Appointment Sent'),
    ], string="Email Stage", default='draft')

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.designation_id = self.employee_id.job_id

    def action_fetch_employee_details(self):
        for record in self:
            if not record.employee_id:
                raise ValidationError(_("Please select an Employee to fetch details."))

            emp = record.employee_id

            # Push annual values from employee.letter → hr.employee
            emp.ctc = record.ctc
            emp.basic = record.basic
            emp.hra = record.hra
            emp.other_allowance = record.other_allowance
            emp.pf = record.pf
            emp.pt = record.pt
            emp.net_take_home = record.net_take_home
            emp.family_insurance = record.family_insurance
            emp.bonus = record.bonus

            # Push monthly values from employee.letter → hr.employee
            emp.ctc_m = record.ctc_m
            emp.basic_m = record.basic_m
            emp.hra_m = record.hra_m
            emp.other_allowance_m = record.other_allowance_m
            emp.pf_m = record.pf_m
            emp.pt_m = record.pt_m
            emp.net_take_home_m = record.net_take_home_m
            emp.family_insurance_m = record.family_insurance_m

            # ✅ Copy attachments from employee.letter → hr.employee
            attachments = self.env['ir.attachment'].search([
                ('res_model', '=', 'employee.letter'),
                ('res_id', '=', record.id)
            ])
            for att in attachments:
                att.copy({
                    'res_model': 'hr.employee',
                    'res_id': emp.id,
                })

            # ✅ Update contract with monthly details
            contract = self.env['hr.contract'].search([
                ('employee_id', '=', emp.id),
                ('state', 'in', ['draft', 'open'])
            ], limit=1, order="id desc")
            if contract:
                contract.write({
                    'cost_to_company': record.ctc or 0.0,
                    'basic': record.basic_m or 0.0,
                    'l10n_in_house_rent_allowance_metro_nonmetro': record.hra_m or 0.0,
                    'provident_fund': record.pf_m or 0.0,
                    'p_tax': record.pt_m or 0.0,
                    'net_salary': record.net_take_home_m or 0.0,
                    'wage': record.ctc_m or 0.0,
                    'l10n_in_esic_amount': record.basic * 0.0075 or 0.0,
                    'other_allowance': record.other_allowance or 0.0,
                })

            # ✅ Set stage to hide Fetch button
            record.email_stage = 'fetched'

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _validate_ctc_for_approval(self):
        for rec in self:
            if not rec.ctc or not rec.ctc_m:
                raise ValidationError(
                    _("Please enter CTC(Per Annum) or Monthly Salary Computed before requesting approval."))
            elif not rec.date_of_joining:
                raise ValidationError(
                    _("Please enter Date Of Joining in Offer Details Tab"))

    @api.depends('ctc')
    def _compute_basic(self):
        for rec in self:
            rec.basic = round(rec.ctc * 0.60 if rec.ctc else 0.0,2)

    @api.depends('ctc_m')
    def _compute_basic_m(self):
        for rec in self:

            rec.basic_m = round(rec.ctc_m * 0.60 if rec.ctc_m else 0.0,2)


    @api.depends('basic_m')
    def _compute_pf_amount(self):
        for record in self:
            x = round(record.basic_m * 0.12,2)
            record.pf_m = x if x <= 1800 else 1800

    @api.depends('ctc')
    def _compute_hra(self):
        for rec in self:
            rec.hra = round(rec.ctc * 0.30 if rec.ctc else 0.0,2)

    @api.depends('family_insurance')
    def _compute_family_insurance_m(self):
        for record in self:
            record.family_insurance = round(record.family_insurance_m * 12,2)

    @api.depends('ctc_m')
    def _compute_pt_m(self):
        for record in self:
            if record.ctc_m <= 15000:
                record.pt_m = 0
            elif 15001 <= record.ctc_m <= 20000:
                record.pt_m = 150
            else:
                record.pt_m = 200

    @api.depends('ctc')
    def _compute_other_allowance(self):
        for rec in self:
            rec.other_allowance = round(rec.ctc * 0.10 if rec.ctc else 0.0,2)

    @api.depends('ctc', 'pf', 'pt', 'hra', 'other_allowance', 'basic')
    def _compute_net_take_home(self):
        for rec in self:
            rec.net_take_home = round(rec.basic + rec.hra + rec.other_allowance - rec.pf - rec.pt if rec.ctc else 0.0,2)

    @api.depends('ctc')
    def _compute_bonus(self):
        for rec in self:
            rec.bonus = round(rec.ctc_m if rec.ctc_m else 0.0,2)

    # ========== ONCHANGE METHODS ==========

    @api.onchange('ctc', 'ctc_type')
    def _onchange_ctc(self):
        for rec in self:
            months = 13 if rec.ctc_type == 'with_bonus' else 12
            if rec.ctc:
                rec.ctc_m = round(rec.ctc / months,2)

    # @api.onchange('ctc', 'availability', 'job_id')
    # def _onchange_offer(self):
    #
    #     self.ctc_offer = self.ctc
    #     # self.applicant_name = self.partner_name
    #     self.date_of_joining = self.availability
    #     self.designation = self.job_id.name

    @api.onchange('ctc_m', 'ctc_type')
    def _onchange_ctc_m(self):
        for rec in self:
            months = 13 if rec.ctc_type == 'with_bonus' else 12
            if rec.ctc_m:
                rec.ctc = round(rec.ctc_m * months,2)

    @api.onchange('ctc', 'ctc_type')
    def _onchange_ctc(self):
        for rec in self:
            months = 13 if rec.ctc_type == 'with_bonus' else 12
            if rec.ctc:
                rec.ctc_m = round(rec.ctc / months,2)

    @api.onchange('ctc')
    def _onchange_hra(self):
        for rec in self:
            rec.hra = round(rec.ctc * 0.30 if rec.ctc else 0.0,2)

    @api.depends('ctc_m')
    def _compute_hra_m(self):
        for rec in self:
            rec.hra_m = round(rec.ctc_m * 0.30 if rec.ctc_m else 0.0,2)

    @api.onchange('ctc')
    def _onchange_other_allowance(self):
        for rec in self:
            rec.other_allowance = round(rec.ctc * 0.10 if rec.ctc else 0.0,2)

    @api.depends('ctc_m')
    def _compute_other_allowance_m(self):
        for rec in self:
            rec.other_allowance_m = round(rec.ctc_m * 0.10 if rec.ctc_m else 0.0,2)

    @api.depends('ctc', 'pf', 'pt', 'basic', 'hra', 'other_allowance')
    def _onchange_net_take_home(self):
        for rec in self:
            if rec.ctc:
                # For Annual Net Take Home: basic + hra + other_allowance - pf - pt
                rec.net_take_home = round((rec.basic or 0.0) + (rec.hra or 0.0) + (rec.other_allowance or 0.0) - (
                        rec.pf or 0.0) - (rec.pt or 0.0),2)
            else:
                rec.net_take_home = 0.0

    @api.depends('ctc_m', 'pf_m', 'pt_m', 'basic_m', 'hra_m', 'other_allowance_m')
    def _compute_net_take_home_m(self):
        for rec in self:
            if rec.ctc_m:
                # For Monthly Net Take Home: basic_m + hra_m + other_allowance_m - pf_m - pt_m
                rec.net_take_home_m =round( (rec.basic_m or 0.0) + (rec.hra_m or 0.0) + (rec.other_allowance_m or 0.0) - (
                        rec.pf_m or 0.0) - (rec.pt_m or 0.0),2)
            else:
                rec.net_take_home_m = 0.0

    # ========== PF and PT OnChange ==========

    @api.onchange('pf')
    def _onchange_pf(self):
        for rec in self:
            months = 12
            if rec.pf:
                rec.pf_m = round(rec.pf / months,2)

    @api.onchange('pf_m')
    def _onchange_pf_m(self):
        for rec in self:
            months = 12
            if rec.pf_m:
                rec.pf = round(rec.pf_m * months,2)

    @api.onchange('pt')
    def _onchange_pt(self):
        for rec in self:
            months = 12
            if rec.pt:
                rec.pt_m = round(rec.pt / months,2)

    @api.onchange('pt_m')
    def _onchange_pt_m(self):
        for rec in self:
            months = 12
            if rec.pt_m:
                rec.pt = round(rec.pt_m * months,2)

    @api.depends('ctc_m')
    def _compute_pt_m(self):
        for record in self:
            if record.ctc_m <= 15000:
                record.pt_m = 0
            elif 15001 <= record.ctc_m <= 20000:
                record.pt_m = 150
            else:
                record.pt_m = 200
    @api.depends('ctc')
    def _compute_ctc_offer(self):
        for record in self:
            record.ctc_offer = record.ctc

    def action_quotation_send(self):
        self.ensure_one()
        if not self.ctc or not self.ctc_m:
            raise ValidationError(
                _("Please enter CTC(Per Annum) or Monthly Salary Computed before sending job offer"))

        try:
            # Generate the offer letter PDF
            report_name = 'cmr_new_recruitments.nhcl_offer_letter_action_direct'


            # Retrieve the email template
            template_id = self.env['ir.model.data']._xmlid_to_res_id(
                'cmr_new_recruitments.email_template_applicant_job_offer_direct',
                raise_if_not_found=False
            )
            lang = self.env.context.get('lang')
            template = self.env['mail.template'].browse(template_id)
            if template and template.lang:
                lang = template._render_lang(self.ids)[self.id]

            # Build context for compose wizard
            ctx = {
                'default_model': 'employee.letter',
                'default_res_ids': self.ids,
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'default_composition_mode': 'comment',
                'mark_so_as_sent': True,
                'custom_layout': "mail.mail_notification_paynow",
                'proforma': self.env.context.get('proforma', False),
                'force_email': True,
                'model_description': self.with_context(lang=lang),
                'approval_type': 'quotation_sent',
                'generate_attachment': True,
                'report_name': 'cmr_new_recruitments.nhcl_offer_letter_action_direct',
            }

            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'views': [(False, 'form')],
                'view_id': False,
                'target': 'new',
                'context': ctx,
            }

        except Exception as e:
            _logger.exception("Failed to prepare quotation email.")
            raise UserError(_("Failed to prepare offer letter email: %s") % str(e))

    def action_appointment_letter_send(self):
        self.ensure_one()
        try:
            _logger.info("🔹 Starting appointment letter generation for: %s", self.name)




            # Step 3: Get the email template ID
            template_id = self.env['ir.model.data']._xmlid_to_res_id(
                'cmr_new_recruitments.email_template_applicant_appointment_letter_direct', raise_if_not_found=False)
            if not template_id:
                raise UserError(_("Appointment email template not found."))

            template = self.env['mail.template'].browse(template_id)

            # Step 4: Determine language
            lang = self.env.context.get('lang')
            if template.lang:
                lang = template._render_lang(self.ids)[self.id]

            # Step 5: Open the email wizard with context
            ctx = {
                'default_model': 'employee.letter',
                'default_res_ids': self.ids,
                'default_use_template': True,
                'default_template_id': template.id,
                'default_composition_mode': 'comment',

                'mark_so_as_sent': True,
                'custom_layout': "mail.mail_notification_paynow",
                'force_email': True,
                'approval_type': 'appointment_sent',
                'generate_attachment': True,
                'report_name': 'cmr_new_recruitments.action_appointment_letter_report_direct',
            }

            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'target': 'new',
                'context': ctx,
            }

        except Exception as e:
            _logger.error("❌ Failed to send appointment letter: %s", str(e))
            raise UserError(_("An error occurred while sending the appointment letter:\n%s") % str(e))


    # Compute methods
    @api.depends('ctc')
    def _compute_basic(self):
        for rec in self:
            rec.basic = round(rec.ctc * 0.60 if rec.ctc else 0.0,2)

    @api.depends('ctc')
    def _compute_hra(self):
        for rec in self:
            rec.hra = round(rec.ctc * 0.30 if rec.ctc else 0.0,2)

    @api.depends('ctc')
    def _compute_other_allowance(self):
        for rec in self:
            rec.other_allowance = round(rec.ctc * 0.10 if rec.ctc else 0.0,2)

    @api.depends('ctc', 'pf', 'pt', 'hra', 'other_allowance', 'basic')
    def _compute_net_take_home(self):
        for rec in self:
            rec.net_take_home = round(rec.basic + rec.hra + rec.other_allowance - rec.pf - rec.pt if rec.ctc else 0.0,2)

    @api.depends('ctc')
    def _compute_bonus(self):
        for rec in self:
            rec.bonus = round(rec.ctc_m if rec.ctc_m else 0.0,2)

    @api.depends('ctc', 'ctc_type')
    def _compute_monthly_fields(self):
        for rec in self:
            months = 13 if rec.ctc_type == 'with_bonus' else 12
            if rec.ctc:
                rec.ctc_m = rec.ctc / months
                rec.basic_m = rec.basic / months
                rec.hra_m = rec.hra / months
                rec.other_allowance_m = rec.other_allowance / months
                rec.pf_m = rec.pf / months if rec.pf else 0.0
                rec.pt_m = rec.pt / months if rec.pt else 0.0
                rec.net_take_home_m = rec.net_take_home / months
            else:
                rec.ctc_m = rec.basic_m = rec.hra_m = rec.other_allowance_m = rec.pf_m = rec.pt_m = rec.net_take_home_m = 0.0

    # Onchange
    @api.onchange('ctc', 'ctc_type')
    def _onchange_ctc(self):
        for rec in self:
            months = 13 if rec.ctc_type == 'with_bonus' else 12
            rec.ctc_m = round(rec.ctc / months if rec.ctc else 0.0,2)

    # @api.onchange('ctc', 'availability', 'job_id')
    # def _onchange_offer(self):
    #     self.ctc_offer = self.ctc
    #     self.applicant_name = self.partner_name
    #     self.date_of_joining = self.availability
    #     self.designation_id = self.job_id

    @api.onchange('ctc_m', 'ctc_type')
    def _onchange_ctc_m(self):
        for rec in self:
            months = 13 if rec.ctc_type == 'with_bonus' else 12
            rec.ctc = rec.ctc_m * months if rec.ctc_m else 0.0

    @api.onchange('pf')
    def _onchange_pf(self):
        for rec in self:
            rec.pf_m = round(rec.pf / 12 if rec.pf else 0.0,2)

    @api.onchange('pf_m')
    def _onchange_pf_m(self):
        for rec in self:
            rec.pf =round( rec.pf_m * 12 if rec.pf_m else 0.0,2)

    @api.onchange('pt')
    def _onchange_pt(self):
        for rec in self:
            rec.pt_m =round( rec.pt / 12 if rec.pt else 0.0 ,2)

    @api.onchange('pt_m')
    def _onchange_pt_m(self):
        for rec in self:
            rec.pt = round(rec.pt_m * 12 if rec.pt_m else 0.0,2)



    def action_print_offer_letter(self):
        self.ensure_one()
        report = self.env.ref('cmr_new_recruitments.nhcl_offer_letter_action_direct')

        # Dynamically set filename via context — by overriding 'report_file' in self.env.context
        self = self.with_context(report_file=f'Odoo-{self.employee_id.name.replace(" ", "_")}')

        return report.report_action(self)

    def action_print_appointment_letter(self):
        self.ensure_one()
        report = self.env.ref('cmr_new_recruitments.action_appointment_letter_report_direct')

        self = self.with_context(report_file=f'Odoo-{self.employee_id.name.replace(" ", "_")}')

        return report.report_action(self)

    class MailComposeMessage(models.TransientModel):
        _inherit = 'mail.compose.message'

        def _action_send_mail_comment(self, res_ids):
            messages = super()._action_send_mail_comment(res_ids)

            approval_type = self.env.context.get('approval_type')
            generate_attachment = self.env.context.get('generate_attachment')
            report_name = self.env.context.get('report_name')
            filename_prefix = (
                'Offer' if approval_type == 'quotation_sent' else 'Appointment'
            )

            if (
                    self.model == 'employee.letter'
                    and res_ids
                    and generate_attachment
                    and report_name
            ):
                letters = self.env['employee.letter'].browse(res_ids)

                for letter in letters:
                    # ✅ Generate PDF
                    pdf_content, content_type = self.env['ir.actions.report']._render_qweb_pdf(
                        report_name, [letter.id]
                    )

                    # ✅ Create attachment (linked to employee.letter)
                    attachment = self.env['ir.attachment'].create({
                        'name': f'{filename_prefix}_Letter_{letter.name}.pdf',
                        'type': 'binary',
                        'datas': base64.b64encode(pdf_content),
                        'res_model': 'employee.letter',
                        'res_id': letter.id,
                        'mimetype': 'application/pdf',
                    })

                    # ✅ Link attachment to the actual email message
                    message = messages.filtered(lambda m: m.res_id == letter.id)
                    if message:
                        message.attachment_ids = [(4, attachment.id)]

                    # ✅ Optional: update stage
                    if approval_type:
                        letter.email_stage = approval_type

            return messages
