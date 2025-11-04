# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    category_id = fields.One2many("hsn.category", "company_id", string="HSN CATEGORY")
