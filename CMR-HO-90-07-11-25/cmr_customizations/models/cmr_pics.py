from odoo import models,fields, _, api
from odoo.exceptions import ValidationError



class GRCMaster(models.Model):
    _name = 'grc.master'

    name = fields.Char(string="Name")

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            if self.search_count([('name', '=', rec.name), ('id', '!=', rec.id)]):
                raise ValidationError(f"This GRC is {rec.name} Already Used.")