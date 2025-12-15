from datetime import timedelta
from odoo import models, fields, api

class StockLot(models.Model):
    _inherit = 'stock.lot'

    def reset_margin_to_default_from_approval_dates(self):
        today = fields.Date.today()
        # Find all approved margin lines
        margin_lines = self.env['product.margin.approval.line'].search(
            [('product_margin_approval_id.state', '=', 'approved')])
        for line in margin_lines:
            approval = line.product_margin_approval_id
            if not approval.from_date or not approval.to_date:
                continue

            # Skip if line's create_date is not within approval date range
            if not (approval.from_date <= line.create_date <= approval.to_date):
                continue
            # Skip if approval is expired
            if approval.to_date < today:
                continue
            lot = line.lot_id
            if not lot:
                continue
            # Reset margin from category default based on cost price
            category = lot.product_id.product_tmpl_id.categ_id
            if category.parent_id and category.parent_id.parent_id and category.parent_id.parent_id.parent_id:
                margin_lines = category.parent_id.parent_id.parent_id.product_category_margin_ids
                matched = False
                for margin in margin_lines:
                    if margin.from_range <= lot.cost_price <= margin.to_range:
                        lot.nhcl_margin_lot = margin.margin
                        matched = True
                        break
                if not matched:
                    lot.nhcl_margin_lot = 0
            else:
                lot.nhcl_margin_lot = 0
            # Trigger calculation after setting margin
            lot.calculate_rsp_price()