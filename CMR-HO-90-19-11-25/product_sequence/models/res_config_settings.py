

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_parent_categories_to_determine_prefix = fields.Boolean(
        related="company_id.use_parent_categories_to_determine_prefix",
        readonly=False,
    )
