from odoo import fields, models, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    import_sale_order_line = fields.Boolean(string="Import Sale Order")
    import_purchase_order_line = fields.Boolean(string="Import Purchase Order")
    import_account_move_line = fields.Boolean(string="Import Invoice")
    import_stock_move_line = fields.Boolean(string="Import Inventory Transfer")
    import_approval_line = fields.Boolean(string="Import Approval")
    import_bom_line = fields.Boolean(string="Import BoM")
    import_mrp_prod_line = fields.Boolean(string="Import MRP")
