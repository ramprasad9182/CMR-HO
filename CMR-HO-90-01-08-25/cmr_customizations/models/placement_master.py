from odoo import fields,models,api,_


class PlacementMaster(models.Model):
    _name = 'placement.master.data'

    name = fields.Char(string="Name", copy=False, required=True)
    code = fields.Integer(string="Code", copy=False, required=True)

    def unlink(self): pass


