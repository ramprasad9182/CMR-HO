from odoo import fields, models, api, _


class MasterData(models.TransientModel):
    _name = 'master.data'


    store_id = fields.Many2one("stock.warehouse", string="Stores")
    name = fields.Char(string="Sequence", required=True, copy=False, readonly=True, default='New')
    sending_count = fields.Integer(string="Send Count")
    created_count = fields.Integer(string="Created Records Count")
    pending_count = fields.Integer(string="Pending Records Count")
    date_time = fields.Datetime(string="Date")
    desc = fields.Text(string="Text")
    master_type = fields.Many2one("ir.model",string="masters", domain="[('model', 'in', ['product.template', 'product.product', 'product.category', 'hr.employee', 'product.attribute'])]")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('master.data')
        return super(MasterData, self).create(vals)
