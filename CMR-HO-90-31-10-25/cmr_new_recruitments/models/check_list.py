from odoo import models, fields

class GradeMaster(models.Model):
    _name = 'check.list'
    _description = 'Check List'

    _rec_name = "list_of_docs"


    list_of_docs = fields.Char(string="List Of Documents")

