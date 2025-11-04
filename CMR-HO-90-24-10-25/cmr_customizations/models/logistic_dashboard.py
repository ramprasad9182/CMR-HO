# -*- coding: utf-8 -*-
from odoo import models, api, fields,_
from dateutil.relativedelta import relativedelta
from datetime import datetime, time
from collections import Counter
import re
import logging
_logger = logging.getLogger(__name__)


class LogisticScreen(models.Model):
    _inherit = 'logistic.screen.data'

    @api.model
    def get_lr_po_counts(self, **kwargs):
        count = [('state', '=', 'done')]
        with_po = self.search_count([('logistic_entry_types', '=', 'automatic')] + count)
        without_po = self.search_count([('logistic_entry_types', '=', 'manual')] + count)
        return {"lr_with_po": int(with_po), "lr_without_po": int(without_po)}

    @api.model
    def get_delivery_period_counts(self, **kwargs):
        Delivery = self.env['delivery.check'].sudo()

        # Scope to the correct "screen"
        base = [('delivery_entry_types', '=', 'automatic')]

        # Date anchors
        today = fields.Date.context_today(self)
        week_start = today - relativedelta(days=6)  # last 7 days inclusive
        month_start = today - relativedelta(days=29)  # last 30 days inclusive

        # Handle Date vs Datetime fields cleanly
        ld_field = Delivery._fields.get('logistic_date')
        is_datetime = bool(ld_field and ld_field.type == 'datetime')

        def range_domain(start_date, end_date):
            """Inclusive start/end filter for logistic_date."""
            if is_datetime:
                start_dt = datetime.combine(start_date, time.min)
                end_dt = datetime.combine(end_date, time.max)
                return [
                    ('logistic_date', '>=', fields.Datetime.to_string(start_dt)),
                    ('logistic_date', '<=', fields.Datetime.to_string(end_dt)),
                ]
            else:
                return [
                    ('logistic_date', '>=', start_date),
                    ('logistic_date', '<=', end_date),
                ]

        def cnt(state_domain, *, exact=None, start=None, end=None):
            dom = list(base) + list(state_domain)
            if exact is not None:
                dom += range_domain(exact, exact)
            else:
                dom += range_domain(start, end)
            return Delivery.search_count(dom)

        # States
        draft_domain = [('state', '=', 'draft')]
        done_domain = [('state', 'in', ['delivered', 'delivery', 'done'])]

        # Draft buckets
        draft_today = cnt(draft_domain, exact=today)
        draft_week = cnt(draft_domain, start=week_start, end=today)
        draft_month = cnt(draft_domain, start=month_start, end=today)

        # Done buckets
        done_today = cnt(done_domain, exact=today)
        done_week = cnt(done_domain, start=week_start, end=today)
        done_month = cnt(done_domain, start=month_start, end=today)

        return {
            "draft": {"today": draft_today, "week": draft_week, "month": draft_month},
            "done": {"today": done_today, "week": done_week, "month": done_month},
        }

    @api.model
    def get_partial_delivered_count(self, **kwargs):

        Delivery = self.env['delivery.check']
        count = Delivery.search_count([('delivery_entry_types', '=', 'automatic'),
                                       ("overall_remaining_bales", ">=", 1),
                                       ('state', '=', 'delivery')])
        return {"partial_delivered": int(count)}

    @api.model
    def get_status_delivered(self, **kwargs):

        Delivery = self.env['delivery.check']
        count = [('state', '=', 'delivery')]
        delivered = Delivery.search_count([('delivery_entry_types', '=', 'automatic')] + count)
        return {"delivered": int(delivered)}

    @api.model
    def get_status_transit_delayed(self, **kwargs):

        today = fields.Date.context_today(self)
        Lr = self.env['delivery.check']
        in_transit = Lr.search_count([('delivery_entry_types', '=', 'automatic'),('state', '=', 'draft')])
        delayed = Lr.search_count([('delivery_entry_types', '=', 'automatic'),('state', '=', 'done'), ('logistic_date', '>', today)])
        canceled = Lr.search_count([('delivery_entry_types', '=', 'automatic'),('state', '=', 'cancel')])
        return {"in_transit": int(in_transit), "delayed": int(delayed), "canceled": int(canceled)}

    @api.model
    def get_top5_products_delivered(self, **kwargs):
        Delivery = self.env['delivery.check'].sudo()

        # Accept both 'delivered' and 'delivery' to avoid state mismatches
        domain = ['|',('delivery_entry_types', '=', 'automatic'), ('state', '=', 'delivered'), ('state', '=', 'delivery')]

        # Optional date filters
        date_from = (kwargs or {}).get('date_from')
        date_to = (kwargs or {}).get('date_to')
        if date_from:
            domain += [('logistic_date', '>=', date_from)]
        if date_to:
            domain += [('logistic_date', '<=', date_to)]

        ids = Delivery.search(domain).ids
        if not ids:
            return {"total": 0, "max": 0, "items": []}

        # Regex: after ']' grab everything up to first '-' (trim spaces)
        # Also guard against strings without ']' or '-'
        pattern = re.compile(r'\]\s*([^-]+)')

        counts = Counter()
        BATCH = 1000
        for i in range(0, len(ids), BATCH):
            rows = Delivery.browse(ids[i:i + BATCH]).read(['item_details'])
            for r in rows:
                s = r.get('item_details') or ''
                if not isinstance(s, str):
                    s = str(s)

                cat = None
                m = pattern.search(s)
                if m:
                    cat = (m.group(1) or '').strip()
                else:
                    # Fallback: remove leading bracket block, split on '-'
                    text = s
                    rb = text.find(']')
                    if rb != -1:
                        text = text[rb + 1:].lstrip()
                    cat = text.split('-', 1)[0].strip() if text else ''

                if not cat:
                    cat = _("Uncategorized")
                counts[cat] += 1

        top = counts.most_common(5)
        items = []
        total = 0
        for cat, cnt in top:
            items.append({
                # unique key for OWL t-key
                "key": cat,  # <--- use this in t-key
                "product_name": cat,  # tooltip/title
                "parent_category": cat,  # bottom label in your XML
                "count": int(cnt),
            })
            total += int(cnt)

        max_count = max((it["count"] for it in items), default=0)
        payload = {"total": total, "max": max_count, "items": items}

        # Optional: debug log so you can see what's parsed
        _logger.debug("Top5 delivered categories: %s", payload)
        return payload

    @api.model
    def get_basement_and_delivery_counts(self, **kwargs):
        """
        - Basement: logistic.screen.data records with state='draft' AND placements='Basement'
        - Delivered total: delivery.check records in delivered state
          (robust to either 'delivered' or 'delivery' values)
        """
        Lr = self.env['logistic.screen.data'].sudo()
        Delivery = self.env['delivery.check'].sudo()

        basement = Lr.search_count([
            ('state', '=', 'draft'),
            ('placements', '=', 'Basement'),
        ])

        delivered_total = Delivery.search_count([
            '|', ('state', '=', 'delivered'), ('state', '=', 'delivery')
        ])

        return {
            "basement": int(basement),
            "delivered_total": int(delivered_total),
        }

    @api.model
    def get_owner_role_split(self, **kwargs):
        """
        Count logistic.screen.data records into exactly one bucket each:
          - Agent        -> logistic_vendor present
          - Transporter  -> transporter present (and agent empty)
          - Vendor       -> vendor present (and agent/transporter empty)
          - None present -> Vendor (default)
        Each record counts as 1.

        Optional filters via kwargs (future-proof), e.g. state/date, but none required now.
        """
        Model = self.sudo()  # read-only dashboard

        # Base domain – adjust later via kwargs if you add filters (e.g., state/date)
        domain = []
        # Example of future filters:
        # state = (kwargs or {}).get('state')
        # if state:
        #     domain.append(('state', '=', state))

        ids = Model.search(domain).ids
        if not ids:
            return {"agent": 0, "transporter": 0, "vendor": 0}

        counts = {"agent": 0, "transporter": 0, "vendor": 0}
        BATCH = 1000
        for i in range(0, len(ids), BATCH):
            rows = Model.browse(ids[i:i + BATCH]).read(['logistic_vendor', 'transporter', 'vendor'])
            for r in rows:
                # Many2one values from read() are [id, display_name] or False
                agent_val = r.get('logistic_vendor')
                transporter_val = r.get('transporter')
                vendor_val = r.get('vendor')

                has_agent = bool(
                    agent_val and (agent_val[0] if isinstance(agent_val, (list, tuple)) else agent_val))
                has_transporter = bool(transporter_val and (
                    transporter_val[0] if isinstance(transporter_val, (list, tuple)) else transporter_val))
                has_vendor = bool(
                    vendor_val and (vendor_val[0] if isinstance(vendor_val, (list, tuple)) else vendor_val))

                if has_agent:
                    counts["agent"] += 1
                elif has_transporter:
                    counts["transporter"] += 1
                elif has_vendor:
                    counts["vendor"] += 1
                else:
                    # default to Vendor when none present
                    counts["vendor"] += 1

        total = counts["agent"] + counts["transporter"] + counts["vendor"]
        payload = {"agent": counts["agent"], "transporter": counts["transporter"], "vendor": counts["vendor"]}
        _logger.debug("Owner role split payload: %s", payload)
        return payload

    @api.model
    def get_open_parcel_state_counts(self, **kwargs):
        Parcel = self.env['open.parcel'].sudo()
        base = []
        draft = Parcel.search_count(base + [('state', '=', 'draft')])
        done = Parcel.search_count(base + [('state', '=', 'done')])
        return {
            "draft": int(draft),
            "done": int(done),
        }

    @api.model
    def get_charges_totals(self, **kwargs):

        Model = self.env['logistic.screen.data'].sudo()
        base_domain = [('logistic_entry_types', '=', 'automatic')]
        rec_ids = Model.search(base_domain).ids
        if not rec_ids:
            return {"draft_rupees": 0.0, "done_rupees": 0.0, "total_rupees": 0.0}

        def to_amount(val):
            if val is None:
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            s = str(val).strip()
            if not s:
                return 0.0
            s = s.replace('₹', '').replace('INR', '').replace(',', '').replace(' ', '')
            try:
                return float(s)
            except Exception:
                m = re.search(r'-?\d+(?:\.\d+)?', s)
                return float(m.group(0)) if m else 0.0

        draft = done = total = 0.0
        DONE_STATES = {'done', 'delivered'}

        BATCH = 1000
        for i in range(0, len(rec_ids), BATCH):
            rows = Model.browse(rec_ids[i:i+BATCH]).read(['charges', 'state'])
            for r in rows:
                amt = to_amount(r.get('charges'))
                total += amt
                st = (r.get('state') or '').lower()
                if st == 'draft':
                    draft += amt
                elif st in DONE_STATES:
                    done += amt

        return {
            "draft_rupees": draft,
            "done_rupees": done,
            "total_rupees": total,
        }
