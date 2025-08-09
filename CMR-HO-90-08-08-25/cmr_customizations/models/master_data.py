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
        store = self.env['master.data'].search([])
        for rec in store:
            rec.pending_count = 0
            rec.created_count = 0
            store_data = self.env['nhcl.ho.store.master'].sudo().search([('nhcl_store_name', '=', rec.store_id.id)])
            model_name = rec.master_type.model
            if model_name == 'product.category':
                product_categs = self.env['product.category'].search([])
                for category in product_categs:
                    pending_repl = category.replication_id.filtered(
                        lambda repl: repl.date_replication == True and repl.nhcl_terminal_ip == store_data.nhcl_terminal_ip and repl.nhcl_api_key == store_data.nhcl_api_key)
                    rec.created_count += len(pending_repl)
                rec.pending_count = rec.sending_count - rec.created_count
            if model_name == 'product.attribute':
                product_attribute = self.env['product.attribute'].search([])
                for attribute in product_attribute:
                    pending_repl = attribute.product_attribute_replication_id.filtered(
                        lambda repl: repl.date_replication == True and repl.nhcl_terminal_ip == store_data.nhcl_terminal_ip and repl.nhcl_api_key == store_data.nhcl_api_key)
                    rec.created_count += len(pending_repl)
                rec.pending_count = rec.sending_count - rec.created_count
            if model_name == 'product.template':
                product_template = self.env['product.template'].search([])
                for template in product_template:
                    pending_repl = template.product_replication_id.filtered(
                        lambda repl: repl.date_replication == True and repl.nhcl_terminal_ip == store_data.nhcl_terminal_ip and repl.nhcl_api_key == store_data.nhcl_api_key)
                    rec.created_count += len(pending_repl)
                rec.pending_count = rec.sending_count - rec.created_count
            if model_name == 'product.product':
                products = self.env['product.product'].search([])
                for product in products:
                    pending_repl = product.product_replication_list_id.filtered(
                        lambda repl: repl.date_replication == True and repl.nhcl_terminal_ip == store_data.nhcl_terminal_ip and repl.nhcl_api_key == store_data.nhcl_api_key)
                    rec.created_count += len(pending_repl)
                rec.pending_count = rec.sending_count - rec.created_count
            if model_name == 'hr.employee':
                products = self.env['hr.employee'].search([])
                for product in products:
                    pending_repl = product.hr_employee_replication_id.filtered(
                        lambda repl: repl.date_replication == True and repl.nhcl_terminal_ip == store_data.nhcl_terminal_ip and repl.nhcl_api_key == store_data.nhcl_api_key)
                    rec.created_count += len(pending_repl)
                rec.pending_count = rec.sending_count - rec.created_count

