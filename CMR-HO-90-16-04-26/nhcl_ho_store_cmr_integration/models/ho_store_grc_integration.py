from odoo import models, fields, api
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)
import requests

class IntegrationReceiptScreen(models.Model):
    _name = 'integration.receipt.screen'
    _description = 'Integration Receipt Screen'



    nhcl_store_id = fields.Many2one(
        'nhcl.ho.store.master',
        string='Company',
        domain="[('nhcl_store_type','!=','ho'), ('nhcl_active','=',True)]"
    )
    nhcl_create_status = fields.Boolean(string="Create Status")

    receipt_ids = fields.Many2many(
        'stock.picking',
        string="Receipts"
    )

    company_domain = fields.Char(string="Company domain", compute="compute_company_domain", store=True)

    @api.onchange('nhcl_store_id')
    def compute_company_domain(self):
        for rec in self:
            if rec.nhcl_store_id:
                company_ids = rec.nhcl_store_id.mapped('nhcl_store_name.company_id.id')
                domain = [('company_id', 'in', company_ids), ('state', '=', 'done'), ('picking_type_code', '=', 'incoming'),('stock_type', '=', 'data_import'),('nhcl_receipt_status','=', False)]
            else:
                domain = [('id', '=', 0)]

            rec.company_domain = str(domain)

    def action_integrate_receipts(self):
        for rec in self:

            if not rec.nhcl_store_id:
                raise ValidationError("Please select Store")

            if not rec.receipt_ids:
                raise ValidationError("Please select Receipts")

            errors = []

            # Only not integrated receipts
            for picking in rec.receipt_ids.filtered(lambda p: not p.nhcl_receipt_status):
                try:
                    picking.get_receipts_data()
                except Exception as e:
                    errors.append(f"{picking.name}: {str(e)}")

            # Update screen only if all success
            if all(p.nhcl_receipt_status for p in rec.receipt_ids):
                rec.nhcl_create_status = True

            if errors:
                raise ValidationError("\n".join(errors))
