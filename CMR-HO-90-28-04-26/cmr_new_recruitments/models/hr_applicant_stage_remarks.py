from odoo import models, fields

class HrApplicantStageRemark(models.Model):
    _name = 'hr.applicant.stage.remark'
    _description = 'Applicant Stage Remarks'

    applicant_id = fields.Many2one('hr.applicant', string='Applicant', required=True, ondelete='cascade')
    stage_id = fields.Many2one('hr.recruitment.stage', string='Stage', required=True)
    remarks = fields.Text(string='Remarks')
