from odoo import models, fields, api


class HoStoreTransactions(models.Model):
    """Created nhcl.ho.store.transactions class to add fields and functions"""
    _name = "nhcl.ho.store.transactions"
    _description = "HO/Store Transactions"

    nhcl_from_warehouse_id = fields.Many2one('stock.warehouse', string='From Warehouse')
    nhcl_to_warehouse_id = fields.Many2one('stock.warehouse', string='To Warehouse')
    nhcl_from_terminal_ip = fields.Char('From Terminal IP')
    nhcl_to_terminal_ip = fields.Char('To Terminal IP')
    nhcl_document = fields.Many2one('ir.model', string='Document')
    nhcl_endpoint = fields.Char(string='End Point')
    nhcl_active = fields.Boolean(default=True, string="Status")
    nhcl_effective_date = fields.Date('Effective Date')
    nhcl_create_date = fields.Date('Create Date', default=fields.Date.context_today)
    nhcl_sync_type = fields.Selection([('ho_to_store', 'HO to Stores'), ('store_to_ho', 'Stores to HO')],
                                      default='ho_to_store', string='Sync Type')
