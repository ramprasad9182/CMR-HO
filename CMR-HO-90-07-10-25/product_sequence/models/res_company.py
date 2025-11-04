

from odoo import fields, models


class Company(models.Model):
    _inherit = "res.company"

    use_parent_categories_to_determine_prefix = fields.Boolean(
        string="Use parent categories to determine the prefix",
        help="Use parent categories to determine the prefix "
        "if the category has no settings for the prefix.",
    )
