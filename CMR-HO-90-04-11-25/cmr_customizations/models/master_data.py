from odoo import fields, models, api, _


class MasterData(models.TransientModel):
    _name = 'master.data'


    store_id = fields.Many2one("stock.warehouse", string="Stores")
    name = fields.Char(string="Sequence", required=True, copy=False, readonly=True, default='New')
    sending_count = fields.Integer(string="Ho Count")
    created_count = fields.Integer(string="Store Count")
    pending_count = fields.Integer(string="Difference Count")
    date_time = fields.Datetime(string="Date")
    desc = fields.Text(string="Text")
    master_type = fields.Many2one("ir.model",string="masters", domain="[('model', 'in', ['product.template', 'product.product', 'product.category', 'hr.employee', 'product.attribute'])]")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('master.data')
        return super(MasterData, self).create(vals)

    def get_category_count(self):
        stores = self.env['master.data'].search([])
        for rec in stores:
            rec.pending_count = 0
            rec.created_count = 0

            store_data = self.env['nhcl.ho.store.master'].sudo().search(
                [('nhcl_store_name', '=', rec.store_id.id)], limit=1
            )
            if not store_data:
                continue

            model_name = rec.master_type.model

            # map model → relation field
            relation_map = {
                'product.category': 'replication_id',
                'product.attribute': 'product_attribute_replication_id',
                'product.template': 'product_replication_id',
                'product.product': 'product_replication_list_id',
                'hr.employee': 'hr_employee_replication_id',
            }

            relation_field = relation_map.get(model_name)
            if not relation_field:
                continue

            # get related comodel dynamically
            comodel = self.env[model_name]._fields[relation_field].comodel_name

            # count directly in the related model (fast SQL count, no Python loops)
            created_count = self.env[comodel].search_count([
                ('date_replication', '=', True),
                ('nhcl_terminal_ip', '=', store_data.nhcl_terminal_ip),
                ('nhcl_api_key', '=', store_data.nhcl_api_key),
            ])

            rec.created_count = created_count
            rec.pending_count = rec.sending_count - created_count
