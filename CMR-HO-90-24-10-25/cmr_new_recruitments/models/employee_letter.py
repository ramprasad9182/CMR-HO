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
    basic = fields.Float(string="BASIC (Per Annum)", compute="_compute_annual_salary", store=True)
    hra = fields.Float(string="HRA (Per Annum)", compute="_compute_annual_salary", store=True)
    other_allowance = fields.Float(string="OTHER ALLOWANCE (Per Annum)", compute="_compute_annual_salary", store=True)
    pf = fields.Float(string="PF (Per Annum)", compute="_compute_annual_salary", store=True)
    pt = fields.Float(string="PT (Per Annum)", compute="_compute_annual_salary", store=True)
    net_take_home = fields.Float(string="NET TAKE HOME (Per Annum)", compute="_compute_annual_salary", store=True)
    family_insurance = fields.Float(string="FAMILY INSURANCE (Per Annum)")
    bonus = fields.Float(string="BONUS (Per Annum)", compute="_compute_annual_salary", store=True)

    # Monthly Fields
    ctc_m = fields.Float(string="CTC (Per Month)")
    basic_m = fields.Float(string="BASIC (Per Month)", compute="_compute_monthly_salary", store=True)
    hra_m = fields.Float(string="HRA (Per Month)", compute='_compute_monthly_salary', store=True)
    other_allowance_m = fields.Float(string="OTHER ALLOWANCE (Per Month)", compute='_compute_monthly_salary',
                                     store=True)
    pf_m = fields.Float(string="PF (Per Month)", compute='_compute_monthly_salary', store=True)
    pt_m = fields.Float(string="PT (Per Month)", compute='_compute_monthly_salary', store=True)
    net_take_home_m = fields.Float(string="NET TAKE HOME (Per Month)", compute='_compute_monthly_salary', store=True)
    family_insurance_m = fields.Float(string="FAMILY INSURANCE (Per Month)")
    # applicant_name = fields.Char(string='Applicant Name')
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

    @api.onchange('ctc_type')
    def _onchange_ctc_type(self):
        self.ctc_m = 0.0

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.designation_id = self.employee_id.job_id

    @api.onchange('family_insurance_m')
    def _onchange_family_insurance_m(self):
        if self.family_insurance_m:
            self.family_insurance = round(self.family_insurance_m * 12, 2)

    # When user inputs annual CTC, update monthly
    @api.onchange('ctc', 'ctc_type')
    def _onchange_ctc(self):
        for record in self:
            if record.ctc_type == 'with_bonus' and record.ctc:
                record.ctc_m = record.ctc / 13
            elif record.ctc and record.ctc_type in ('without_bonus', 'non_ctc'):
                record.ctc_m = record.ctc / 12

    # Monthly salary calculation
    @api.depends('ctc_m')
    def _compute_monthly_salary(self):
        for record in self:
            record.basic_m = record.ctc_m * 0.60
            record.hra_m = record.ctc_m * 0.30
            record.other_allowance_m = record.ctc_m * 0.10

            record.pf_m = record.basic_m * 0.12
            if record.pf_m > 1800:
                record.pf_m = 1800

            if record.ctc_m <= 15000:
                record.pt_m = 0
            elif record.ctc_m <= 20000:
                record.pt_m = 150
            else:
                record.pt_m = 200

            record.net_take_home_m = (
                    record.basic_m + record.hra_m + record.other_allowance_m
                    - record.pf_m - record.pt_m
            )

    # Annual salary calculation
    @api.depends('ctc_m', 'basic_m', 'hra_m', 'other_allowance_m', 'ctc_type')
    def _compute_annual_salary(self):

        for record in self:
            multiplier = 13 if record.ctc_type == 'with_bonus' else 12

            record.ctc = record.ctc_m * multiplier
            record.basic = record.basic_m * multiplier
            record.hra = record.hra_m * multiplier
            record.other_allowance = record.other_allowance_m * multiplier
            record.pf = record.pf_m * 12
            record.pt = record.pt_m * 12
            record.net_take_home = (
                    record.basic + record.hra + record.other_allowance
                    - record.pf - record.pt
            )
            record.bonus = record.ctc_m

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

    # def _validate_ctc_for_approval(self):
    #     for rec in self:
    #         if not rec.ctc or not rec.ctc_m:
    #             raise ValidationError(
    #                 _("Please enter CTC(Per Annum) or Monthly Salary Computed before requesting approval."))
    #         elif not rec.date_of_joining:
    #             raise ValidationError(
    #                 _("Please enter Date Of Joining in Offer Details Tab"))

    # @api.depends('ctc')
    # def _compute_basic(self):
    #     for rec in self:
    #         rec.basic = round(rec.ctc * 0.60 if rec.ctc else 0.0,2)
    #
    # @api.depends('ctc_m')
    # def _compute_basic_m(self):
    #     for rec in self:
    #
    #         rec.basic_m = round(rec.ctc_m * 0.60 if rec.ctc_m else 0.0,2)
    #
    #
    # @api.depends('basic_m')
    # def _compute_pf_amount(self):
    #     for record in self:
    #         x = round(record.basic_m * 0.12,2)
    #         record.pf_m = x if x <= 1800 else 1800
    #
    # @api.depends('ctc')
    # def _compute_hra(self):
    #     for rec in self:
    #         rec.hra = round(rec.ctc * 0.30 if rec.ctc else 0.0,2)
    #
    # @api.depends('family_insurance')
    # def _compute_family_insurance_m(self):
    #     for record in self:
    #         record.family_insurance = round(record.family_insurance_m * 12,2)
    #
    # @api.depends('ctc_m')
    # def _compute_pt_m(self):
    #     for record in self:
    #         if record.ctc_m <= 15000:
    #             record.pt_m = 0
    #         elif 15001 <= record.ctc_m <= 20000:
    #             record.pt_m = 150
    #         else:
    #             record.pt_m = 200
    #
    # @api.depends('ctc')
    # def _compute_other_allowance(self):
    #     for rec in self:
    #         rec.other_allowance = round(rec.ctc * 0.10 if rec.ctc else 0.0,2)
    #
    # @api.depends('ctc', 'pf', 'pt', 'hra', 'other_allowance', 'basic')
    # def _compute_net_take_home(self):
    #     for rec in self:
    #         rec.net_take_home = round(rec.basic + rec.hra + rec.other_allowance - rec.pf - rec.pt if rec.ctc else 0.0,2)
    #
    # @api.depends('ctc')
    # def _compute_bonus(self):
    #     for rec in self:
    #         rec.bonus = round(rec.ctc_m if rec.ctc_m else 0.0,2)
    #
    # # ========== ONCHANGE METHODS ==========
    #
    # @api.onchange('ctc', 'ctc_type')
    # def _onchange_ctc(self):
    #     for rec in self:
    #         months = 13 if rec.ctc_type == 'with_bonus' else 12
    #         if rec.ctc:
    #             rec.ctc_m = round(rec.ctc / months,2)
    #
    # # @api.onchange('ctc', 'availability', 'job_id')
    # # def _onchange_offer(self):
    # #
    # #     self.ctc_offer = self.ctc
    # #     # self.applicant_name = self.partner_name
    # #     self.date_of_joining = self.availability
    # #     self.designation = self.job_id.name
    #
    # @api.onchange('ctc_m', 'ctc_type')
    # def _onchange_ctc_m(self):
    #     for rec in self:
    #         months = 13 if rec.ctc_type == 'with_bonus' else 12
    #         if rec.ctc_m:
    #             rec.ctc = round(rec.ctc_m * months,2)
    #
    # @api.onchange('ctc', 'ctc_type')
    # def _onchange_ctc(self):
    #     for rec in self:
    #         months = 13 if rec.ctc_type == 'with_bonus' else 12
    #         if rec.ctc:
    #             rec.ctc_m = round(rec.ctc / months,2)
    #
    # @api.onchange('ctc')
    # def _onchange_hra(self):
    #     for rec in self:
    #         rec.hra = round(rec.ctc * 0.30 if rec.ctc else 0.0,2)
    #
    # @api.depends('ctc_m')
    # def _compute_hra_m(self):
    #     for rec in self:
    #         rec.hra_m = round(rec.ctc_m * 0.30 if rec.ctc_m else 0.0,2)
    #
    # @api.onchange('ctc')
    # def _onchange_other_allowance(self):
    #     for rec in self:
    #         rec.other_allowance = round(rec.ctc * 0.10 if rec.ctc else 0.0,2)
    #
    # @api.depends('ctc_m')
    # def _compute_other_allowance_m(self):
    #     for rec in self:
    #         rec.other_allowance_m = round(rec.ctc_m * 0.10 if rec.ctc_m else 0.0,2)
    #
    # @api.depends('ctc', 'pf', 'pt', 'basic', 'hra', 'other_allowance')
    # def _onchange_net_take_home(self):
    #     for rec in self:
    #         if rec.ctc:
    #             # For Annual Net Take Home: basic + hra + other_allowance - pf - pt
    #             rec.net_take_home = round((rec.basic or 0.0) + (rec.hra or 0.0) + (rec.other_allowance or 0.0) - (
    #                     rec.pf or 0.0) - (rec.pt or 0.0),2)
    #         else:
    #             rec.net_take_home = 0.0
    #
    # @api.depends('ctc_m', 'pf_m', 'pt_m', 'basic_m', 'hra_m', 'other_allowance_m')
    # def _compute_net_take_home_m(self):
    #     for rec in self:
    #         if rec.ctc_m:
    #             # For Monthly Net Take Home: basic_m + hra_m + other_allowance_m - pf_m - pt_m
    #             rec.net_take_home_m =round( (rec.basic_m or 0.0) + (rec.hra_m or 0.0) + (rec.other_allowance_m or 0.0) - (
    #                     rec.pf_m or 0.0) - (rec.pt_m or 0.0),2)
    #         else:
    #             rec.net_take_home_m = 0.0
    #
    # # ========== PF and PT OnChange ==========
    #
    # @api.onchange('pf')
    # def _onchange_pf(self):
    #     for rec in self:
    #         months = 12
    #         if rec.pf:
    #             rec.pf_m = round(rec.pf / months,2)
    #
    # @api.onchange('pf_m')
    # def _onchange_pf_m(self):
    #     for rec in self:
    #         months = 12
    #         if rec.pf_m:
    #             rec.pf = round(rec.pf_m * months,2)
    #
    # @api.onchange('pt')
    # def _onchange_pt(self):
    #     for rec in self:
    #         months = 12
    #         if rec.pt:
    #             rec.pt_m = round(rec.pt / months,2)
    #
    # @api.onchange('pt_m')
    # def _onchange_pt_m(self):
    #     for rec in self:
    #         months = 12
    #         if rec.pt_m:
    #             rec.pt = round(rec.pt_m * months,2)
    #
    # @api.depends('ctc_m')
    # def _compute_pt_m(self):
    #     for record in self:
    #         if record.ctc_m <= 15000:
    #             record.pt_m = 0
    #         elif 15001 <= record.ctc_m <= 20000:
    #             record.pt_m = 150
    #         else:
    #             record.pt_m = 200


    @api.depends('ctc')
    def _compute_ctc_offer(self):
        for record in self:
            record.ctc_offer = record.ctc



    def action_quotation_send(self):
        self.ensure_one()
        if not self.ctc or not self.ctc_m:
            raise ValidationError("Please enter CTC(Per Annum) or Monthly Salary Computed before requesting approval.")
        elif not self.date_of_joining:
            raise ValidationError("Please enter Date Of Joining in Offer Details Tab")
        try:
            # Generate PDF
            pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                'cmr_new_recruitments.nhcl_offer_letter_action_direct',
                [self.id]
            )

            # Create TEMPORARY attachment (not linked to employee.letter yet)
            attachment = self.env['ir.attachment'].create({
                'name': f'Offer_Letter_{self.name}.pdf',
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'mimetype': 'application/pdf',
                'res_model': 'mail.compose.message',  # Temporary model
            })

            # Get email template
            template_id = self.env['ir.model.data']._xmlid_to_res_id(
                'cmr_new_recruitments.email_template_applicant_job_offer_direct',
                raise_if_not_found=False
            )

            # Prepare email context
            ctx = {
                'default_model': 'employee.letter',
                'default_res_ids': [self.id],  # Note: using list format
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'default_composition_mode': 'comment',
                'mark_so_as_sent': True,
                'custom_layout': "mail.mail_notification_paynow",
                'force_email': True,
                'default_attachment_ids': [(4, attachment.id)],  # Link temporarily
                'approval_type': 'quotation_sent',
                'attachment_to_relink': attachment.id,  # Store for post-processing
            }

            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'target': 'new',
                'context': ctx,
            }

        except Exception as e:
            _logger.error("Failed to prepare quotation email: %s", str(e))
            raise UserError(_("Failed to prepare offer letter email: %s") % str(e))

    def action_appointment_letter_send(self):
        self.ensure_one()
        # self._validate_ctc_for_approval()
        try:
            # Generate PDF
            pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
                'cmr_new_recruitments.action_appointment_letter_report_direct',
                [self.id]
            )

            # Create TEMPORARY attachment
            attachment = self.env['ir.attachment'].create({
                'name': f'Appointment_Letter_{self.name}.pdf',
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'mimetype': 'application/pdf',
                'res_model': 'mail.compose.message',  # Temporary model
            })

            # Get template
            template_id = self.env['ir.model.data']._xmlid_to_res_id(
                'cmr_new_recruitments.email_template_applicant_appointment_letter_direct',
                raise_if_not_found=False
            )

            # Prepare context
            ctx = {
                'default_model': 'employee.letter',
                'default_res_ids': [self.id],
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'default_composition_mode': 'comment',
                'default_attachment_ids': [(4, attachment.id)],
                'mark_so_as_sent': True,
                'custom_layout': "mail.mail_notification_paynow",
                'force_email': True,
                'approval_type': 'appointment_sent',
                'attachment_to_relink': attachment.id,  # For post-processing
            }

            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'target': 'new',
                'context': ctx,
            }

        except Exception as e:
            _logger.error("Failed to prepare appointment letter: %s", str(e))
            raise UserError(_("Failed to prepare appointment letter: %s") % str(e))


    # # Compute methods
    # @api.depends('ctc')
    # def _compute_basic(self):
    #     for rec in self:
    #         rec.basic = round(rec.ctc * 0.60 if rec.ctc else 0.0,2)
    #
    # @api.depends('ctc')
    # def _compute_hra(self):
    #     for rec in self:
    #         rec.hra = round(rec.ctc * 0.30 if rec.ctc else 0.0,2)
    #
    # @api.depends('ctc')
    # def _compute_other_allowance(self):
    #     for rec in self:
    #         rec.other_allowance = round(rec.ctc * 0.10 if rec.ctc else 0.0,2)
    #
    # @api.depends('ctc', 'pf', 'pt', 'hra', 'other_allowance', 'basic')
    # def _compute_net_take_home(self):
    #     for rec in self:
    #         rec.net_take_home = round(rec.basic + rec.hra + rec.other_allowance - rec.pf - rec.pt if rec.ctc else 0.0,2)
    #
    # @api.depends('ctc')
    # def _compute_bonus(self):
    #     for rec in self:
    #         rec.bonus = round(rec.ctc_m if rec.ctc_m else 0.0,2)
    #
    # @api.depends('ctc', 'ctc_type')
    # def _compute_monthly_fields(self):
    #     for rec in self:
    #         months = 13 if rec.ctc_type == 'with_bonus' else 12
    #         if rec.ctc:
    #             rec.ctc_m = rec.ctc / months
    #             rec.basic_m = rec.basic / months
    #             rec.hra_m = rec.hra / months
    #             rec.other_allowance_m = rec.other_allowance / months
    #             rec.pf_m = rec.pf / months if rec.pf else 0.0
    #             rec.pt_m = rec.pt / months if rec.pt else 0.0
    #             rec.net_take_home_m = rec.net_take_home / months
    #         else:
    #             rec.ctc_m = rec.basic_m = rec.hra_m = rec.other_allowance_m = rec.pf_m = rec.pt_m = rec.net_take_home_m = 0.0
    #
    # # Onchange
    # @api.onchange('ctc', 'ctc_type')
    # def _onchange_ctc(self):
    #     for rec in self:
    #         months = 13 if rec.ctc_type == 'with_bonus' else 12
    #         rec.ctc_m = round(rec.ctc / months if rec.ctc else 0.0,2)
    #
    # # @api.onchange('ctc', 'availability', 'job_id')
    # # def _onchange_offer(self):
    # #     self.ctc_offer = self.ctc
    # #     self.applicant_name = self.partner_name
    # #     self.date_of_joining = self.availability
    # #     self.designation_id = self.job_id
    #
    # @api.onchange('ctc_m', 'ctc_type')
    # def _onchange_ctc_m(self):
    #     for rec in self:
    #         months = 13 if rec.ctc_type == 'with_bonus' else 12
    #         rec.ctc = rec.ctc_m * months if rec.ctc_m else 0.0
    #
    # @api.onchange('pf')
    # def _onchange_pf(self):
    #     for rec in self:
    #         rec.pf_m = round(rec.pf / 12 if rec.pf else 0.0,2)
    #
    # @api.onchange('pf_m')
    # def _onchange_pf_m(self):
    #     for rec in self:
    #         rec.pf =round( rec.pf_m * 12 if rec.pf_m else 0.0,2)
    #
    # @api.onchange('pt')
    # def _onchange_pt(self):
    #     for rec in self:
    #         rec.pt_m =round( rec.pt / 12 if rec.pt else 0.0 ,2)
    #
    # @api.onchange('pt_m')
    # def _onchange_pt_m(self):
    #     for rec in self:
    #         rec.pt = round(rec.pt_m * 12 if rec.pt_m else 0.0,2)



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
            # First send the email
            messages = super()._action_send_mail_comment(res_ids)

            # Handle post-send processing
            approval_type = self.env.context.get('approval_type')
            attachment_id = self.env.context.get('attachment_to_relink')

            if self.model == 'employee.letter' and res_ids and approval_type:
                # Update email stage
                letters = self.env['employee.letter'].browse(res_ids)
                letters.write({'email_stage': approval_type})

                # Relink attachment to employee.letter if email was sent successfully
                if attachment_id:
                    attachment = self.env['ir.attachment'].browse(attachment_id)
                    if attachment.exists():
                        attachment.write({
                            'res_model': 'employee.letter',
                            'res_id': letters.id,
                        })

            return messages
