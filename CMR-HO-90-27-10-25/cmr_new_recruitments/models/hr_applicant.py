import base64

from odoo import models,fields,api,_
from odoo.exceptions import UserError, AccessError, ValidationError
import logging
_logger = logging.getLogger(__name__)


class HrApplicant(models.Model):
    _inherit = 'hr.applicant'

    applicant_professional_ids = fields.One2many(
        'professional.details',
        'applicant_id',
        string="Professional Details"
    )
    total_experience = fields.Float(string="Total Years of Experience")

    applicant_reference_ids = fields.One2many('employee.reference', 'applicant_employee_id', string="References")
    applicant_education_ids = fields.One2many('employee.education', 'applicant_employee_id', string="Educational Details")

    shortlisted = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string='Shortlisted')
    check_list_ids = fields.Many2many("check.list")
    checklist_tab_visible = fields.Boolean(string="Checklist Tab Visible", default=False)

    checklist_order_line_ids = fields.One2many('hr.applicant.checklist.orderline', 'check_list_id', string="Checklist Documents")
    stage_remark_ids = fields.One2many('hr.applicant.stage.remark', 'applicant_id', string='Stage Remarks')

    is_stage_initial = fields.Boolean(
        string="Is Initial Stage",
        compute="_compute_is_stage_initial",
        store=True
    )
    is_stage_signed = fields.Boolean(
        string="Is Initial Signed",
        compute="_compute_is_stage_signed",
        store=True
    )

    on_hold = fields.Boolean(string='On Hold', default=False)


    job_offer_sent = fields.Boolean(string="Job Offer Email Sent")
    division_id = fields.Many2one(
        'product.category',
        string='Division',
        domain=[('parent_id', '=', False)],
        help="Select division from top-level product categories (no parent)."
    )





    approval_stage = fields.Selection([
        ('draft', 'Draft'),
        ('first_requested', 'Approval Requested'),
        ('first_approved', 'First Approved'),
        ('second_approved', 'Second Approved'),
        ('job_accepted', 'Job Accepted'),#job offer sent
        ('job_rejected', 'Job Rejected'),
        ('first_approved_offer', 'First Approved'),#job offer accepted
        ('second_approved_offer', 'Second Approved'),#approval request
        ('third_approved_offer', 'Third Approved'),#approved level1
        ('appointment', 'Appointment'),#approved level2
        ('appointment_accepted', 'Appointment Accepted'),# sent appointment letter
        ('appointment_rejected', 'Appointment Rejected'),
        ('checklist', 'Checklist'),# appointment letter accepted
        ('done', 'Done'),#checklist done
    ], default='draft')

    ctc_type = fields.Selection([
        ('with_bonus', 'With Bonus'),
        ('without_bonus', 'Without Bonus'),
        ('non_ctc', 'Non Ctc'),
    ], string='CTC Type')
    # --------------------------------dev------------------------
    # --------------------------------dev------------------------
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

    applicant_name = fields.Char(string='Applicant Name', related="partner_name", store=True)
    todays_date = fields.Date(string="Date", default=fields.Date.today)
    date_of_joining = fields.Date(string='Date Of Joining', related="availability", store=True)
    ctc_offer = fields.Float(string="CTC", related="ctc", store=True)
    designation = fields.Char(string="Designation", related="job_id.name", store=True)
    is_employee_created = fields.Boolean(string="Employee Created", default=False)

    @api.onchange('ctc_type')
    def _onchange_ctc_type(self):
        self.ctc_m = 0.0

    @api.depends('stage_id', 'job_id')
    def _compute_application_status(self):
        super()._compute_application_status()  # Call Odoo's default logic

        for applicant in self:
            if applicant.application_status == 'refused':
                applicant.approval_stage = 'draft'
                applicant.is_stage_initial = False
                applicant.is_stage_signed = False

    @api.onchange('job_id')
    def _onchange_job_id_fetch_interviewers(self):
        if self.job_id:
            self.interviewer_ids = self.job_id.interviewer_ids

    @api.model
    def create(self, vals):
        # Only copy interviewers from job if they were not passed already
        if vals.get('job_id') and not vals.get('interviewer_ids'):
            job = self.env['hr.job'].browse(vals['job_id'])
            vals['interviewer_ids'] = [(6, 0, job.interviewer_ids.ids)]
        return super().create(vals)

    # def _validate_ctc_for_approval(self):
    #     for rec in self:
    #         if not rec.ctc or not rec.ctc_m:
    #             raise ValidationError(
    #                 _("Please enter CTC(Per Annum) or Monthly Salary Computed before requesting approval."))
    #         elif not rec.availability:
    #             raise ValidationError("Please enter Date Of Joining")

            # elif not rec.date_of_joining:
            #     raise ValidationError(
            #         _("Please enter Date Of Joining in Offer Details Tab"))
            # elif not rec.ctc_type:
            #     raise ValidationError(
            #         _("Please Select CTC Type"))


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
    # @api.depends('basic_m','ctc_m')
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
    # @api.depends('family_insurance_m')
    # def _compute_family_insurance(self):
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

    # @api.onchange('ctc', 'partner_name', 'availability', 'job_id', 'ctc_m')
    # def _onchange_offer(self):
    #     self.ctc_offer = self.ctc
    #     self.applicant_name = self.partner_name
    #     self.date_of_joining = self.availability
    #     self.designation = self.job_id.name

    # @api.onchange('ctc_m', 'ctc_type')
    # def _onchange_ctc_m(self):
    #     for rec in self:
    #         months = 13 if rec.ctc_type == 'with_bonus' else 12
    #         if rec.ctc_m:
    #             rec.ctc = round(rec.ctc_m * months,2)
    #
    # # @api.onchange('ctc', 'ctc_type')
    # # def _onchange_ctc(self):
    # #     for rec in self:
    # #         months = 13 if rec.ctc_type == 'with_bonus' else 12
    # #         if rec.ctc:
    # #             rec.ctc_m = round(rec.ctc / months,2)
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
    #         rec.other_allowance_m =round( rec.ctc_m * 0.10 if rec.ctc_m else 0.0,2)
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
    #             rec.net_take_home_m = round((rec.basic_m or 0.0) + (rec.hra_m or 0.0) + (rec.other_allowance_m or 0.0) - (
    #                     rec.pf_m or 0.0) - (rec.pt_m or 0.0),2)
    #         else:
    #             rec.net_take_home_m = 0.0
    #
    # # ========== PF and PT OnChange ==========
    #
    #
    # @api.onchange('pf_m')
    # def _onchange_pf(self):
    #     for rec in self:
    #         months = 12
    #         if rec.pf_m:
    #             rec.pf =round( rec.pf_m * months,2)
    #
    #
    #
    # @api.onchange('pt_m')
    # def _onchange_pt(self):
    #     for rec in self:
    #         months = 12
    #         if rec.pt_m:
    #             rec.pt = round(rec.pt_m * months,2)
    #
    # @api.depends('ctc_m','ctc')
    # def _compute_pt_m(self):
    #     for record in self:
    #         if record.ctc_m <= 15000:
    #             record.pt_m = 0
    #         elif 15001 <= record.ctc_m <= 20000:
    #             record.pt_m = 150
    #         else:
    #             record.pt_m = 200

    @api.constrains('family_insurance_m')
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


    def action_request_approval(self):
            self.ensure_one()
            if not self.availability:
                raise ValidationError("Please Enter DOJ (Date of Joining).")
            elif not self.ctc_type:
                raise ValidationError("Please Select CTC Type")
            elif not self.ctc and not self.ctc_m:
                raise ValidationError(
                    _("Please enter CTC (Per Annum) or Monthly Salary Computed before requesting approval.")
                )

            # ✅ Move to stage: "Job Offer Approval Sent"
            job_offer_stage = self.env['hr.recruitment.stage'].search([
                ('name', '=', 'Job Offer Approval Sent')
            ], limit=1)
            if not job_offer_stage:
                raise AccessError("Stage 'Job Offer Approval Sent' not found.")

            self.stage_id = job_offer_stage.id

            self.approval_stage = 'first_requested'
            first_group = self.env.ref('cmr_new_recruitments.group_hr_applicant_first_approval', raise_if_not_found=False)
            if not first_group:
                raise AccessError("Group for first-level approval not found.")

            for user in first_group.users:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user.id,
                    summary='Approval Level 1 Needed',
                    note='Please review and approve (Level 1).'
                )

    def action_first_approve(self):
        self.ensure_one()
        self.approval_stage = 'first_approved'

        # ✅ Properly find and mark only current user's activity as done
        activity = self.env['mail.activity'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('user_id', '=', self.env.user.id),
            ('summary', '=', 'Approval Level 1 Needed'),
        ], limit=1)
        if activity:
            activity.action_feedback(_('✅ Level 1 Approved by %s') % self.env.user.name)


        second_group = self.env.ref('cmr_new_recruitments.group_hr_applicant_second_approval', raise_if_not_found=False)
        if second_group:
            for user in second_group.users:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user.id,
                    summary='Approval Level 2 Needed',
                    note='Please review and approve (Level 2).'
                )

    def action_second_approve(self):
        self.ensure_one()

        # ✅ Move to stage: "Job Offer Approval Sent"
        job_offer_stage = self.env['hr.recruitment.stage'].search([
            ('name', '=', 'Job Offer Approved')
        ], limit=1)
        if not job_offer_stage:
            raise AccessError("Stage 'Job Offer Approved' not found.")

        self.stage_id = job_offer_stage.id

        self.approval_stage = 'second_approved'
        activity = self.env['mail.activity'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('user_id', '=', self.env.user.id),
            ('summary', '=', 'Approval Level 2 Needed'),
        ], limit=1)
        if activity:
            activity.action_feedback(_('✅ Level 2 Approved by %s') % self.env.user.name)

    def action_refuse_approval_one(self):
        self.ensure_one()

        # ✅ Move to 'Refused' stage
        refused_stage = self.env['hr.recruitment.stage'].search([
            ('name', '=', 'Contract Proposal')
        ], limit=1)
        if not refused_stage:
            raise AccessError("Stage 'Contract Proposal' not found. Please configure the stage.")

        self.stage_id = refused_stage.id
        self.approval_stage = 'draft'

        # ✅ Mark all pending activities as done
        activities = self.env['mail.activity'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('user_id', '=', self.env.user.id),

        ])
        if activities:
            activities.action_feedback(_("❌ Approval Refused by %s") % self.env.user.name)


    def action_refuse_approval_two(self):
        self.ensure_one()

        # ✅ Move to 'Refused' stage
        refused_stage = self.env['hr.recruitment.stage'].search([
            ('name', '=', 'Contract Proposal')
        ], limit=1)
        if not refused_stage:
            raise AccessError("Stage 'Contract Proposal' not found. Please configure the stage.")

        self.stage_id = refused_stage.id
        self.approval_stage = 'draft'

        # ✅ Mark all pending activities as done
        activities = self.env['mail.activity'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('user_id', '=', self.env.user.id),

        ])
        if activities:
            activities.action_feedback(_("❌ Approval Refused by %s") % self.env.user.name)






    def action_appointment_request_approval(self):
        self.ensure_one()
        self.approval_stage="second_approved_offer"
        # ✅ Move to stage: "Job Offer Approval Sent"
        job_offer_stage = self.env['hr.recruitment.stage'].search([
            ('name', '=', 'Appointment Approval Sent')
        ], limit=1)
        if not job_offer_stage:
            raise AccessError("Stage 'Appointment Approval Sent' not found.")

        self.stage_id = job_offer_stage.id


        first_group = self.env.ref('cmr_new_recruitments.group_hr_applicant_first_approval', raise_if_not_found=False)
        if not first_group:
            raise AccessError("Group for first-level approval not found.")

        for user in first_group.users:
            self.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=user.id,
                summary='Approval Level 1 Needed',
                note='Please review and approve (Level 1).'
            )

    def action_appointment_first_approve(self):
        self.ensure_one()
        self.approval_stage="third_approved_offer"


        # ✅ Properly find and mark only current user's activity as done
        activity = self.env['mail.activity'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('user_id', '=', self.env.user.id),
            ('summary', '=', 'Approval Level 1 Needed'),
        ], limit=1)
        if activity:
            activity.action_feedback(_('✅ Level 1 Approved by %s') % self.env.user.name)

        second_group = self.env.ref('cmr_new_recruitments.group_hr_applicant_second_approval', raise_if_not_found=False)
        if second_group:
            for user in second_group.users:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user.id,
                    summary='Approval Level 2 Needed',
                    note='Please review and approve (Level 2).'
                )

    def action_appointment_second_approve(self):
        self.ensure_one()
        # self.approval_stage = 'appointment'
        self.approval_stage = 'appointment_accepted'

        # ✅ Move to stage: "Job Offer Approval Sent"
        job_offer_stage = self.env['hr.recruitment.stage'].search([
            ('name', '=', 'Appointment Offer Approved')
        ], limit=1)
        if not job_offer_stage:
            raise AccessError("Stage 'Appointment Offer Approved' not found.")

        self.stage_id = job_offer_stage.id


        activity = self.env['mail.activity'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('user_id', '=', self.env.user.id),
            ('summary', '=', 'Approval Level 2 Needed'),
        ], limit=1)
        if activity:
            activity.action_feedback(_('✅ Level 2 Approved by %s') % self.env.user.name)

    def action_appointment_refuse_approval_one(self):
        self.ensure_one()

        # ✅ Move to 'Refused' stage
        refused_stage = self.env['hr.recruitment.stage'].search([
            ('name', '=', 'Job Offer Approved')
        ], limit=1)
        if not refused_stage:
            raise AccessError("Stage 'Job Offer Approved' not found. Please configure the stage.")

        self.stage_id = refused_stage.id
        self.approval_stage = 'first_approved_offer'

        # ✅ Mark all pending activities as done
        activities = self.env['mail.activity'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('user_id', '=', self.env.user.id),

        ])
        if activities:
            activities.action_feedback(_("❌ Approval Refused by %s") % self.env.user.name)

    def action_appointment_refuse_approval_two(self):
        self.ensure_one()

        # ✅ Move to 'Refused' stage
        refused_stage = self.env['hr.recruitment.stage'].search([
            ('name', '=', 'Job Offer Approved')
        ], limit=1)
        if not refused_stage:
            raise AccessError("Stage 'Job Offer Approved' not found. Please configure the stage.")

        self.stage_id = refused_stage.id
        self.approval_stage = 'first_approved_offer'

        # ✅ Mark all pending activities as done
        activities = self.env['mail.activity'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('user_id', '=', self.env.user.id),

        ])
        if activities:
            activities.action_feedback(_("❌ Approval Refused by %s") % self.env.user.name)

    #########################################################################################

    def action_add_stage_remarks(self):
        """Create missing stage remark lines for this applicant."""
        for applicant in self:
            existing_stage_ids = applicant.stage_remark_ids.mapped('stage_id.id')
            all_stages = self.env['hr.recruitment.stage'].search([], order='sequence')
            for stage in all_stages:
                if stage.id not in existing_stage_ids:
                    self.env['hr.applicant.stage.remark'].create({
                        'applicant_id': applicant.id,
                        'stage_id': stage.id,
                    })

    # def action_offer_accepted(self):
    #     for rec in self:
    #         # rec.document_type = 'checklist'
    #         rec.approval_stage = 'checklist'
    #         rec.offer_tag = 'accepted'
    #
    # def action_offer_rejected(self):
    #     for rec in self:
    #         # rec.document_type = 'rejected'
    #         rec.approval_stage = 'appointment_rejected'
    #         rec.offer_tag = 'rejected'




    def action_quotation_send_accepted(self):
        for rec in self:
            # rec.document_type = 'appointment'
            rec.approval_stage = 'first_approved_offer'


    def action_quotation_send_rejected(self):
        for rec in self:
            # rec.document_type = 'job_rejected'
            rec.approval_stage = 'job_rejected'
            # rec.offer_tag = 'rejected'
            rejected_stage = self.env['hr.recruitment.stage'].search([('name', '=', 'Rejected')], limit=1)
            if not rejected_stage:
                raise ValidationError(
                    "Recruitment stage 'Rejected' does not exist. Please create it under Recruitment → Configuration → Stages.")

            rec.stage_id = rejected_stage.id


    def action_appointment_letter_accepted(self):
        for rec in self:
            # rec.document_type = 'accepted'
            rec.approval_stage = 'checklist'


    def action_appointment_letter_rejected(self):
        for rec in self:
            # rec.document_type = 'appointment_rejected'
            rec.approval_stage = 'appointment_rejected'
            # rec.offer_tag = 'rejected'
            rejected_stage = self.env['hr.recruitment.stage'].search([('name', '=', 'Rejected')], limit=1)
            if not rejected_stage:
                raise ValidationError(
                    "Recruitment stage 'Rejected' does not exist. Please create it under Recruitment → Configuration → Stages.")

            rec.stage_id = rejected_stage.id


    def action_set_on_hold(self):
        for rec in self:
            rec.on_hold = True

    def action_unhold(self):
        for rec in self:
            rec.on_hold = False

    @api.depends('stage_id')
    def _compute_is_stage_second_interview(self):
        for rec in self:
            rec.is_stage_second_interview = rec.stage_id.name == 'Second Interview'

    @api.depends('stage_id')
    def _compute_is_stage_initial(self):
        for rec in self:
            rec.is_stage_initial = rec.stage_id.name == 'Contract Proposal'

    @api.depends('stage_id')
    def _compute_is_stage_signed(self):
        for rec in self:
            rec.is_stage_signed = rec.stage_id.name == 'Contract Signed'

    def action_quotation_send(self):
        """ Action to send the job offer letter """
        self.ensure_one()

        try:
            # Generate the PDF content
            pdf_content, content_type = self.env['ir.actions.report']._render_qweb_pdf(
                'cmr_new_recruitments.nhcl_offer_letter_action',
                [self.id]
            )
            _logger.info("Offer letter PDF generated successfully for applicant %s", self.name)

            # Create a temporary attachment (not linked to applicant yet)
            attachment = self.env['ir.attachment'].create({
                'name': f'Offer_Letter_{self.name}.pdf',
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'mimetype': 'application/pdf',
                'res_model': 'mail.compose.message',  # Temporary model
            })

            # Get the email template
            template_id = self.env['ir.model.data']._xmlid_to_res_id(
                'cmr_new_recruitments.email_template_applicant_job_offer',
                raise_if_not_found=False
            )

            # Prepare context for the email composer
            ctx = {
                'default_model': 'hr.applicant',
                'default_res_ids': [self.id],  # Changed from default_res_id
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'default_composition_mode': 'comment',
                'mark_so_as_sent': True,
                'custom_layout': "mail.mail_notification_paynow",
                'force_email': True,
                'default_attachment_ids': [(4, attachment.id)],  # Add attachment without linking
                'approval_type': 'job_accepted',
            }

            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'views': [(False, 'form')],
                'target': 'new',
                'context': ctx,
            }

        except Exception as e:
            _logger.error("Failed to prepare offer letter email for applicant %s: %s", self.name, str(e))
            raise UserError(_("Failed to prepare offer letter email: %s") % str(e))

    def action_appointment_letter_send(self):
        """ Action to send the appointment letter """
        self.ensure_one()

        try:
            # Generate the PDF content
            pdf_content, content_type = self.env['ir.actions.report']._render_qweb_pdf(
                'cmr_new_recruitments.report_appointment_letter',
                [self.id]
            )
            _logger.info("Appointment letter PDF generated successfully for applicant %s", self.name)

            # Create a temporary attachment
            attachment = self.env['ir.attachment'].create({
                'name': f'Appointment_Letter_{self.name}.pdf',
                'type': 'binary',
                'datas': base64.b64encode(pdf_content),
                'mimetype': 'application/pdf',
                'res_model': 'mail.compose.message',  # Temporary model
            })

            # Get the email template
            template_id = self.env['ir.model.data']._xmlid_to_res_id(
                'cmr_new_recruitments.email_template_applicant_appointment_letter',
                raise_if_not_found=False
            )
            if not template_id:
                raise UserError(_("Appointment email template not found."))

            # Prepare context for the email composer
            ctx = {
                'default_model': 'hr.applicant',
                'default_res_ids': [self.id],  # Changed from default_res_id
                'default_use_template': bool(template_id),
                'default_template_id': template_id,
                'default_composition_mode': 'comment',
                'mark_so_as_sent': True,
                'custom_layout': "mail.mail_notification_paynow",
                'force_email': True,
                'default_attachment_ids': [(4, attachment.id)],  # Add attachment without linking
                # 'approval_type': 'appointment_accepted',
                'approval_type': 'done',
            }

            return {
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mail.compose.message',
                'views': [(False, 'form')],
                'target': 'new',
                'context': ctx,
            }

        except Exception as e:
            _logger.error("Failed to prepare appointment letter email for applicant %s: %s", self.name, str(e))
            raise UserError(_("Failed to prepare appointment letter email: %s") % str(e))

    @api.model
    def _get_next_stage(self, current_stage):
        return self.env['hr.recruitment.stage'].search([
            ('sequence', '>', current_stage.sequence)
        ], order='sequence asc', limit=1)

    def write(self, vals):
        res = super().write(vals)

        # Handle shortlisted logic AFTER write
        if 'shortlisted' in vals and vals['shortlisted'] == 'yes':
            for applicant in self:
                next_stage = self._get_next_stage(applicant.stage_id)
                if next_stage:
                    applicant.stage_id = next_stage.id
                    applicant.shortlisted = False

        return res

    def create_employee_from_applicant(self):
        for applicant in self:
            # ✅ 1. Validate checklist
            if not applicant.check_list_ids:
                raise ValidationError("Please select at least one checklist document before creating an employee.")
            if not applicant.company_id:
                raise ValidationError("Please assign a Company before creating an employee.")

            # ✅ 2. Prepare vals dict from applicant (must include all salary fields)
            employee_vals = {
                'name': applicant.partner_name,
                'job_title': applicant.job_id.name,
                'job_id': applicant.job_id.id,
                'department_id': applicant.department_id.id,
                'company_id': applicant.company_id.id,
                'work_email': applicant.email_from,
                'mobile_phone': applicant.partner_phone,
                'work_phone': applicant.partner_mobile,
                'private_email': applicant.email_from,
                'private_street': applicant.permanent_street,
                'private_street2': applicant.permanent_street2,
                'private_city': applicant.permanent_city,
                'private_state_id': applicant.permanent_state_id.id,
                'private_zip': applicant.permanent_zip,
                'private_country_id': applicant.permanent_country_id.id,
                'birthday': applicant.dob,
                'gender': applicant.gender,
                'marital': applicant.marital_status,
                'age': applicant.age,
                'division_id': applicant.division_id.id,
                'ctc': applicant.ctc,
                'basic': applicant.basic,
                'hra': applicant.hra,
                'other_allowance': applicant.other_allowance,
                'pf': applicant.pf,
                'pt': applicant.pt,
                'bonus': applicant.bonus,
                'net_take_home': applicant.net_take_home,
                'family_insurance': applicant.family_insurance,
                'family_insurance_m': applicant.family_insurance_m,
                'ctc_m': applicant.ctc_m,
                'basic_m': applicant.basic_m,
                'hra_m': applicant.hra_m,
                'other_allowance_m': applicant.other_allowance_m,
                'pf_m': applicant.pf_m,
                'pt_m': applicant.pt_m,
                'net_take_home_m': applicant.net_take_home_m,
                'check_list_ids': [(6, 0, applicant.check_list_ids.ids)],
                'total_experience': applicant.total_experience,
            }

            # ✅ 3. Create employee manually so that create() will auto-create contract
            employee = self.env['hr.employee'].create(employee_vals)

            # ✅ 4. Link employee to applicant
            applicant.write({'emp_id': employee.id,
                             'is_employee_created': True,
                             })
            employee._compute_grade()

            # ✅ 5. Copy related records
            for line in applicant.applicant_professional_ids:
                line.copy({'employee_id': employee.id, 'applicant_id': False})

            for ref in applicant.applicant_reference_ids:
                ref.copy({'employee_id': employee.id, 'applicant_employee_id': False})

            for edu in applicant.applicant_education_ids:
                edu.copy({'employee_id': employee.id, 'applicant_employee_id': False})

            attachments = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'hr.applicant'),
                ('res_id', '=', applicant.id),
                ('mimetype', '!=', 'application/octet-stream')  # Optional: skip weird blobs
            ])

            # ✅ 6. Duplicate attachments instead of moving
            attachments = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'hr.applicant'),
                ('res_id', '=', applicant.id)
            ])
            for attachment in attachments:
                attachment.copy({
                    'res_model': 'hr.employee',
                    'res_id': employee.id
                })

            # for attachment in attachments:
            #     if not attachment.document_ids:  # ✅ Only move if not linked to DMS
            #         attachment.write({
            #             'res_model': 'hr.employee',
            #             'res_id': employee.id
            #         })
            #     else:
            #         _logger.warning(f"Skipping attachment {attachment.name}: already a document.")

            # ✅ 6. Move attachments
            # attachments = self.env['ir.attachment'].sudo().search([
            #     ('res_model', '=', 'hr.applicant'),
            #     ('res_id', '=', applicant.id)
            # ])
            # for attachment in attachments:
            #     attachment.write({
            #         'res_model': 'hr.employee',
            #         'res_id': employee.id
            #     })

        return True

    @api.onchange('applicant_education_ids', 'applicant_professional_ids')
    def _onchange_applicant_lines(self):
        """Auto-assign sequence numbers for both educational and professional lines."""
        for idx, line in enumerate(self.applicant_education_ids, start=1):
            line.sequence = idx
        for idx, line in enumerate(self.applicant_professional_ids, start=1):
            line.sequence = idx

    def action_open_checklist_tab(self):
        self.ensure_one()

        # self.approval_stage = 'done'
        self.approval_stage = 'appointment'
        self.checklist_tab_visible = True

        # Safe way: shared stages
        next_stage = self.env['hr.recruitment.stage'].search([
            ('sequence', '>', self.stage_id.sequence)
        ], order='sequence asc', limit=1)

        if next_stage:
            self.stage_id = next_stage.id

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.applicant',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
        }


# class MailComposeMessage(models.TransientModel):
#     _inherit = 'mail.compose.message'
#
#     def action_send_mail(self):
#
#         # Keep context so we know which button was used
#         self = self.with_context(document_type_to_set=self.env.context.get('document_type_to_set'))
#         return super().action_send_mail()
#
#
#     def _action_send_mail_comment(self, res_ids):
#         # Send mail using standard method
#
#         messages = super()._action_send_mail_comment(res_ids)
#
#         # Set document_type after email is sent
#         doc_type = self.env.context.get('document_type_to_set')
#         if self.model == 'hr.applicant' and res_ids and doc_type:
#             applicants = self.env['hr.applicant'].browse(res_ids)
#             applicants.write({'document_type': doc_type})
#
#             # ✅ Mark Job Offer Email as sent
#             if doc_type == 'appointment':
#                 applicants.write({'job_offer_sent': True})
#
#         return messages


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def action_send_mail(self):
        """ Override to maintain context """
        self = self.with_context(approval_type=self.env.context.get('approval_type'))
        return super().action_send_mail()

    def _action_send_mail_comment(self, res_ids):
        """
        Override to:
        1. Update applicant status after email is sent
        2. Properly link attachments to the applicant record
        """
        # First send the email (original behavior)
        messages = super()._action_send_mail_comment(res_ids)

        # Handle post-send actions
        approval_type = self.env.context.get('approval_type')
        if self.model == 'hr.applicant' and res_ids and approval_type:
            applicants = self.env['hr.applicant'].browse(res_ids)

            # Update applicant status
            update_vals = {'approval_stage': approval_type}
            if approval_type == 'job_accepted':
                update_vals['job_offer_sent'] = True
            applicants.write(update_vals)

            # Re-link attachments from compose message to the applicant
            attachments = self.attachment_ids.filtered(
                lambda a: a.res_model == 'mail.compose.message'
            )
            if attachments:
                attachments.write({
                    'res_model': 'hr.applicant',
                    'res_id': applicants.id,
                })

        return messages



class HrContract(models.Model):
    _inherit = 'hr.contract'

    net_salary = fields.Float(string='Net Salary')
    basic = fields.Float('Basic')
    p_tax = fields.Float('PT')
    cost_to_company = fields.Float(string='Cost to company')
    provident_fund= fields.Float('PF')
    other_allowance = fields.Float(string="Other Allowance")