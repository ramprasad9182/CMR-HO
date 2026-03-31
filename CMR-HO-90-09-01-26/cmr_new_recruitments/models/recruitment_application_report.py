from calendar import Calendar

from odoo import models, fields

class HrJob(models.Model):
    _inherit = 'hr.job'

    applications_received = fields.Integer(string="Applications Received", compute='_compute_counts')
    shortlisted = fields.Integer(string="Shortlisted", compute='_compute_counts')
    hired = fields.Integer(string="Hired", compute='_compute_counts')
    offer_accepted = fields.Integer(string="Offer Accepted", compute='_compute_counts')
    offer_rejected = fields.Integer(string="Offer Rejected", compute='_compute_counts')
    on_hold_count = fields.Integer(string="On Hold", compute='_compute_counts')
    interviews_conducted = fields.Integer(string="Interviews Conducted", compute='_compute_counts')
    job_offer_emails_sent = fields.Integer(string="Offer Rolled Out", compute='_compute_counts')  # ✅ New Field

    def _compute_counts(self):
        Applicant = self.env['hr.applicant']
        calendar_event_model = self.env['calendar.event']
        for job in self:
            applicants = Applicant.search([('job_id', '=', job.id)])
            applicant_ids = applicants.ids
            job.applications_received = len(applicants)
            # ✅ Updated logic for shortlisted
            job.shortlisted = len(applicants.filtered(
                lambda a: a.stage_id.name not in ['','New', 'Initial Qualification']
            ))
            # job.shortlisted = len(applicants.filtered(lambda a: a.stage_id.name == 'First Interview'))
            job.hired = len(applicants.filtered(lambda a: a.stage_id.name == 'Contract Signed'))
            job.offer_accepted = len(applicants.filtered(lambda a: a.approval_stage == 'job_accepted'))
            job.offer_rejected = len(applicants.filtered(lambda a: a.approval_stage == 'job_rejected'))
            job.on_hold_count = len(applicants.filtered(lambda a: a.on_hold))

            # ✅ Count interviews (calendar events) linked to applicants
            interviews = calendar_event_model.search_count([
                ('res_model', '=', 'hr.applicant'),
                ('res_id', 'in', applicant_ids)
            ])
            job.interviews_conducted = interviews

            # ✅ Count job offer emails sent
            job.job_offer_emails_sent = len(applicants.filtered(lambda a: a.job_offer_sent))