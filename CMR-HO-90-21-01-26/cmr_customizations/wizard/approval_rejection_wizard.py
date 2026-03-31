from odoo import models, fields

class ApprovalRejectionWizard(models.TransientModel):
    _name = 'approval.rejection.wizard'
    _description = 'Approval Rejection Wizard'

    reason = fields.Text(string='Reason', required=True)
    approval_id = fields.Many2one('approval.request', string="Approval Request")

    def action_confirm_rejection(self):
        self.ensure_one()
        if self.approval_id:
            self.approval_id.rejection_reason = self.reason
            self.approval_id.nhcl_approver_reject()


class ApprovalRejectionWizard2(models.TransientModel):
    _name = 'approval.rejection.wizard2'
    _description = 'Approval Rejection Wizard'

    reason = fields.Text(string='Reason', required=True)
    approval_id = fields.Many2one('approval.request', string="Approval Request")

    def action_confirm_rejection(self):
        self.ensure_one()
        if self.approval_id:
            self.approval_id.rejection_reason2 = self.reason
            self.approval_id.action_refuse()