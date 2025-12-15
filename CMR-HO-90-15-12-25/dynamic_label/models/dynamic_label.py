from odoo import models, fields , api

class DynamicLabel(models.Model):
    _name = 'dynamic.label'
    _description = 'Dynamic Label Upload or Download'

    name = fields.Char(string="Doc NO", required=True, readonly=True, copy=False, default='New')
    config_name = fields.Char(string="Configration Name", required=True)
    description = fields.Char(string="Description",related="config_name")
    upload_file = fields.Binary(string="upload File")

    upload_date = fields.Datetime(string="Date", default=fields.Datetime.now)
    drop_down = fields.Selection(
        [
            ('items', 'Items'),
            ('packet', 'Packet'),
            ('set', 'Set'),
            ('promotion_item', 'Promotion Item'),
            ('logistic', 'Logistic'),
        ],
        string="Drop Down",
        default='items'
    )

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            # Get next sequence from ir.sequence
            vals['name'] = self.env['ir.sequence'].next_by_code('dynamic.label.dlu') or 'New'
        return super(DynamicLabel, self).create(vals)