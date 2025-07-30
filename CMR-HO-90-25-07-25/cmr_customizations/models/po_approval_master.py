from odoo import fields,models,api,_
from odoo.exceptions import ValidationError


class ApprovalsMaster(models.Model):
    _name = 'po.approvals.master'

    date = fields.Date("Date")
    min_approvals = fields.Integer("Min Approvals")
    approval_type = fields.Char("Type")
    max_approvals = fields.Integer("Max Approvals")
    approval_limit = fields.Integer("Level Of Approvals")
    approval_active = fields.Boolean(string='Active', default=True)
    table_type = fields.Char("Table Type")
    nhcl_approval_state = fields.Selection(
        [('draft', 'Draft'), ('activate', 'Active'), ('in_activate', 'Deactivate')],
        string='Status', default='draft')

    @api.constrains('approval_limit', 'max_approvals', 'nhcl_approval_state', 'table_type')
    def check_approval_limit(self):
        for record in self:
            if record.table_type and record.table_type.lower() != 'purchase.order':
                raise ValidationError("Table type must be 'purchase.order'.")
            if record.min_approvals == 0:
                raise ValidationError("The minimum approvals cannot be zero.")
            if record.max_approvals == 0:
                raise ValidationError("Maximum Approvals Cannot Be Zero.")
            if record.max_approvals > 4:
                raise ValidationError("Maximum approvals cannot exceed four.")
            if record.approval_limit == 0:
                raise ValidationError("The level of approval cannot be zero.")
            if record.approval_limit > record.max_approvals:
                raise ValidationError("Approval limit cannot exceed maximum approvals.")
            if record.nhcl_approval_state == 'activate':
                active_records = self.search_count([('nhcl_approval_state', '=', 'activate')])
                if active_records > 1:
                    raise ValidationError("Only one record can be in the 'Activate' state at a time.")

    def activate_approvals(self):
        if self.nhcl_approval_state in ['draft', 'in_activate']:
            self.nhcl_approval_state = 'activate'

    def deactivate_approvals(self):
        if self.nhcl_approval_state == 'activate':
            self.nhcl_approval_state = 'in_activate'
            self.approval_active = False
        return {
            'type': 'ir.actions.client', 'tag': 'reload'
        }