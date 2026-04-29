from odoo import models, fields


class StoresAuditPlanReplicationLog(models.Model):
    _name = 'store.audit.plan.replication.log'
    _description = "Store Audit Plan Replication Log"

    nhcl_serial_no = fields.Char('S.No',default=lambda self: self.env['ir.sequence'].next_by_code('store.audit.plan.replication.log'),readonly=True,copy=False)
    nhcl_date_of_log = fields.Datetime('Date of Log')
    nhcl_source_name = fields.Char("Source Id")
    nhcl_source_id = fields.Many2one('stock.warehouse', string='Source Name')
    nhcl_destination_name = fields.Char("Destination Id")
    nhcl_destination_id = fields.Many2one('stock.warehouse', string='Destination Name')
    nhcl_record_id = fields.Integer('Record Id')
    nhcl_function_required = fields.Selection([('add', 'ADD'), ('update', 'Update')], default=False,
                                              string="Function Required")
    nhcl_status = fields.Selection([('success', 'Success'), ('failure', 'Failure')], default=False, string='Status')
    nhcl_details_status = fields.Char('Response')
    nhcl_model = fields.Char('Model')
    nhcl_status_code = fields.Char('Status Code')