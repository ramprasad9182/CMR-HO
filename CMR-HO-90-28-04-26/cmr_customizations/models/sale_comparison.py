from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def get_company_sales_comparison(self, year, quarter=None, month=None):
        def _get_date_range(y):
            if quarter:
                q_map = {
                    1: (1, 3),
                    2: (4, 6),
                    3: (7, 9),
                    4: (10, 12),
                }
                # IMPORTANT FIX — handles "Q1", "Q2", etc.
                q = int(quarter.replace("Q", "")) if isinstance(quarter, str) else int(quarter)
                start_m, end_m = q_map[q]
                start = date(y, start_m, 1)
                end = date(y, end_m, 1) + relativedelta(months=1, days=-1)
                return start, end
            if month:
                m = int(month)
                start = date(y, m, 1)
                end = start + relativedelta(months=1, days=-1)
                return start, end
            return date(y, 1, 1), date(y, 12, 31)
        current_start, current_end = _get_date_range(year)
        prev_start, prev_end = _get_date_range(year - 1)
        Move = self.env["account.move"].sudo()

        def _aggregate(start, end):
            sales_domain = [
                ("journal_id.name", "ilike", "point"),
                ("state", "=", "posted"),
                ("date", ">=", start),
                ("date", "<=", end),
            ]

            sales_groups = Move.read_group(
                sales_domain,
                ["amount_total:sum"],
                ["company_id"],
            )

            sales_totals = {
                g["company_id"][0]: g.get("amount_total", 0.0) or 0.0
                for g in sales_groups
                if g.get("company_id")
            }

            if not sales_totals:
                return {}

            sales_company_ids = list(sales_totals.keys())

            refund_domain = [
                ("company_id", "in", sales_company_ids),
                ("state", "=", "posted"),
                ("move_type", "=", "out_refund"),
                ("date", ">=", start),
                ("date", "<=", end),
            ]

            refund_groups = Move.read_group(
                refund_domain,
                ["amount_total:sum"],
                ["company_id"],
            )

            refund_totals = {
                g["company_id"][0]: g.get("amount_total", 0.0) or 0.0
                for g in refund_groups
                if g.get("company_id")
            }

            result = {}
            for cid, sales in sales_totals.items():
                refund = refund_totals.get(cid, 0.0)
                result[cid] = round(sales - refund, 2)

            return result

        current_totals = _aggregate(current_start, current_end)
        previous_totals = _aggregate(prev_start, prev_end)
        company_ids = list(set(current_totals.keys()) | set(previous_totals.keys()))
        if not company_ids:
            return []
        companies = self.env["res.company"].browse(company_ids)
        output = []
        for company in companies:
            current = current_totals.get(company.id, 0.0)
            previous = previous_totals.get(company.id, 0.0)

            if previous == 0:
                delta_pct = 0.0
            else:
                delta_pct = ((current - previous) / previous) * 100

            delta_pct = round(delta_pct, 2)

            output.append({
                "company_id": company.id,
                "company_name": company.name,
                "current_total": round(current, 2),
                "previous_total": round(previous, 2),
                "delta_display": f"{delta_pct}%",
                "delta_class": "positive" if delta_pct > 0 else "negative" if delta_pct < 0 else "",
            })

        return output
