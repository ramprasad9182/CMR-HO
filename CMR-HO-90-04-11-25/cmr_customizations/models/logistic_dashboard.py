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

        # Domain: automatic OR state in ('delivered','delivery')
        domain = ['|', ('delivery_entry_types', '=', 'automatic'), ('state', '=', 'delivered')]

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

        counts = Counter()
        BATCH = 1000

        for i in range(0, len(ids), BATCH):
            rows = Delivery.browse(ids[i:i + BATCH]).read(['item_details'])
            for r in rows:
                s = r.get('item_details') or ''
                if not isinstance(s, str):
                    try:
                        s = str(s)
                    except Exception:
                        s = ''

                # substring after first closing bracket ']' if present
                rb = s.find(']')
                after = s[rb + 1:].strip() if rb != -1 else s.strip()
                after = re.sub(r'\s+', ' ', after)  # normalize spaces

                # split on hyphen, trimming spaces around segments
                parts = [p.strip() for p in re.split(r'\s*-\s*', after) if p.strip() != ""]

                cat = ""
                # If first segment is exactly one alphabetical character, return the FIRST TWO segments joined by '-'
                # e.g. parts = ['H','GAGRAS','ETHNIC ...'] -> cat = 'H-GAGRAS'
                if parts and len(parts[0]) == 1 and parts[0].isalpha():
                    if len(parts) >= 2:
                        cat = f"{parts[0].strip()}-{parts[1].strip()}"
                    else:
                        # no second segment: fallback to full 'after' text (or mark uncategorized)
                        cat = after or ""
                else:
                    # Default behavior: take text after ']' up to first '-' (i.e., parts[0]) if exists
                    if parts:
                        cat = parts[0].strip()
                    else:
                        cat = after

                # Final fallback
                if not cat:
                    cat = _("Uncategorized")

                counts[cat] += 1

        top = counts.most_common(5)
        items = []
        total = 0
        for cat, cnt in top:
            items.append({
                "key": cat,
                "product_name": cat,
                "parent_category": cat,
                "count": int(cnt),
            })
            total += int(cnt)

        max_count = max((it["count"] for it in items), default=0)
        payload = {"total": total, "max": max_count, "items": items}

        _logger.debug("Top5 delivered categories (two-segment single-letter rule): %s", payload)
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

    @api.model
    def get_unopened_zone_counts(self, top_n=5, **kwargs):
        """
        Returns top N placements (zones) with counts of unique draft LRs (open.parcel.parcel_lr_no).
        Relation: delivery.check.placements -> placement.master.data
        """

        try:
            # 1️⃣ Collect draft open.parcel LR numbers
            Parcel = self.env['open.parcel'].sudo()
            parcel_domain = [
                ('state', '=', 'draft'),
                ('parcel_lr_no', '!=', False),
            ]
            parcels = Parcel.search_read(parcel_domain, ['parcel_lr_no'])

            lr_set = {str(p['parcel_lr_no']).strip() for p in parcels if p.get('parcel_lr_no')}
            if not lr_set:
                return []

            # 2️⃣ Find delivery.check records that match those LRs (latest first)
            Delivery = self.env['delivery.check'].sudo()
            deliveries = Delivery.search(
                [('logistic_lr_number', 'in', list(lr_set))],
                order='id desc'
            )

            # 3️⃣ Map each LR to its latest placement
            lr_to_placement = {}
            for d in deliveries:
                if not d.logistic_lr_number:
                    continue
                lr_key = str(d.logistic_lr_number).strip()
                if lr_key not in lr_to_placement and d.placements:
                    lr_to_placement[lr_key] = d.placements.id  # Many2one to placement.master.data

            if not lr_to_placement:
                return []

            # 4️⃣ Count how many unique LRs per placement
            placement_counts = {}
            for pid in lr_to_placement.values():
                if not pid:
                    continue
                placement_counts[pid] = placement_counts.get(pid, 0) + 1

            if not placement_counts:
                return []

            # 5️⃣ Get placement names from placement.master.data
            Placement = self.env['placement.master.data'].sudo()
            placement_ids = list(placement_counts.keys())
            placements = Placement.browse(placement_ids).read(['name'])

            id_name_map = {rec['id']: rec.get('name') or f'Placement #{rec["id"]}' for rec in placements}

            print("the data of the zones", placement_ids, id_name_map)

            # 6️⃣ Build and sort final result
            results = [
                {
                    'placement_id': pid,
                    'placement_name': id_name_map.get(pid, f'#{pid}'),
                    'count': count,
                }
                for pid, count in placement_counts.items()
            ]

            results.sort(key=lambda x: x['count'], reverse=True)

            # 7️⃣ Return top N
            return results[:int(top_n)]

        except Exception as e:
            _logger.exception("Error computing unopened zone counts: %s", e)
            return []

    @api.model
    def get_unopened_division_counts(self, top_n=10, **kwargs):
        """
        Return top N divisions (parsed from delivery.check.item_details) for draft open.parcel LRs.

        Returns: list of dicts:
          [{ 'division_name': 'ROYAL PURPLE', 'count': 12 }, ...]
        """
        try:
            # 1) collect draft open.parcel LR numbers (deduped)
            Parcel = self.env['open.parcel'].sudo()
            parcel_domain = [
                ('state', '=', 'draft'),
                ('parcel_lr_no', '!=', False),
            ]
            parcels = Parcel.search_read(parcel_domain, ['parcel_lr_no'])
            lr_set = {str(p['parcel_lr_no']).strip() for p in parcels if p.get('parcel_lr_no')}
            if not lr_set:
                return []

            lr_list = list(lr_set)

            # 2) find delivery.check records that match those LR numbers, latest first
            Delivery = self.env['delivery.check'].sudo()
            deliveries = Delivery.search([('logistic_lr_number', 'in', lr_list)], order='id desc')

            # 3) map LR -> latest delivery.check id (we need to read item_details later)
            lr_to_delivery_id = {}
            for d in deliveries:
                lr_val = d.logistic_lr_number
                if lr_val is None:
                    continue
                lr_key = str(lr_val).strip()
                if lr_key not in lr_to_delivery_id:
                    lr_to_delivery_id[lr_key] = int(d.id)

            if not lr_to_delivery_id:
                return []

            # 4) batch-read delivery.check.item_details for chosen delivery ids
            delivery_ids = list(set(lr_to_delivery_id.values()))
            BATCH = 1000
            id_to_item = {}
            for i in range(0, len(delivery_ids), BATCH):
                chunk = delivery_ids[i:i + BATCH]
                rows = Delivery.browse(chunk).read(['item_details'])
                for r in rows:
                    did = r.get('id')
                    item = r.get('item_details') or ''
                    # normalize to string
                    if not isinstance(item, str):
                        try:
                            item = str(item)
                        except Exception:
                            item = ''
                    id_to_item[did] = item

            # 5) For each LR, parse division from its chosen delivery's item_details
            counts = Counter()
            for lr, did in lr_to_delivery_id.items():
                s = id_to_item.get(did, '') or ''
                s = s.strip()
                if not s:
                    counts[_("Uncategorized")] += 1
                    continue

                # substring after first closing bracket ']' if present
                rb = s.find(']')
                after = s[rb + 1:].strip() if rb != -1 else s.strip()

                # normalize spaces
                after = re.sub(r'\s+', ' ', after)

                # split on hyphen, trimming spaces around segments
                parts = [p.strip() for p in re.split(r'\s*-\s*', after) if p.strip() != ""]

                division = ""
                # If first segment is exactly one alphabetical character -> join first two segments by '-'
                # e.g. parts = ['H','GAGRAS','ETHNIC ...'] -> division = 'H-GAGRAS'
                if parts and len(parts[0]) == 1 and parts[0].isalpha():
                    if len(parts) >= 2:
                        division = f"{parts[0].strip()}-{parts[1].strip()}"
                    else:
                        # fallback to the full 'after' text if second segment missing
                        division = after or ""
                else:
                    # Default: take first segment (or whole 'after' if no hyphen)
                    if parts:
                        division = parts[0].strip()
                    else:
                        division = after

                if not division:
                    division = _("Uncategorized")

                counts[division] += 1

            if not counts:
                return []

            # 6) build results sorted by count desc
            results = [
                {'division_name': name, 'count': cnt}
                for name, cnt in counts.items()
            ]
            results.sort(key=lambda x: x['count'], reverse=True)

            # 7) return top N
            return results[:int(top_n)]

        except Exception as exc:
            _logger.exception("Error in get_unopened_division_counts: %s", exc)
            return []

    @api.model
    def get_divisionwise_bale_totals(self, top_n=5, **kwargs):
        """
        Returns top N divisions (from delivery.check.item_details)
        ranked by total parcel_bale quantity from draft open.parcel LRs.

        Output example:
        [
            { "division_name": "H-GAGRAS", "parcel_bale_total": 123 },
            { "division_name": "ROYAL PURPLE", "parcel_bale_total": 95 },
            ...
        ]
        """

        try:
            # 1️⃣ Collect draft parcels and aggregate parcel_bale by LR number
            Parcel = self.env['open.parcel'].sudo()
            parcel_domain = [
                ('state', '=', 'draft'),
                ('parcel_lr_no', '!=', False),
            ]
            parcels = Parcel.search_read(parcel_domain, ['parcel_lr_no', 'parcel_bale'])

            lr_bale_map = {}
            for p in parcels:
                lr = str(p.get('parcel_lr_no') or '').strip()
                if not lr:
                    continue
                bale_val = p.get('parcel_bale') or 0
                try:
                    qty = float(bale_val)
                except Exception:
                    qty = 0.0
                lr_bale_map[lr] = lr_bale_map.get(lr, 0.0) + qty

            if not lr_bale_map:
                return []

            lr_list = list(lr_bale_map.keys())

            # 2️⃣ Find delivery.check records matching those LR numbers (latest first)
            Delivery = self.env['delivery.check'].sudo()
            deliveries = Delivery.search(
                [('logistic_lr_number', 'in', lr_list)],
                order='id desc'
            )

            # 3️⃣ Map LR -> latest delivery.check.id
            lr_to_delivery_id = {}
            for d in deliveries:
                lr_val = d.logistic_lr_number
                if lr_val is None:
                    continue
                lr_key = str(lr_val).strip()
                if lr_key not in lr_to_delivery_id:
                    lr_to_delivery_id[lr_key] = d.id

            if not lr_to_delivery_id:
                return []

            # 4️⃣ Batch read item_details for chosen deliveries
            BATCH = 1000
            id_to_item = {}
            delivery_ids = list(set(lr_to_delivery_id.values()))
            for i in range(0, len(delivery_ids), BATCH):
                chunk = delivery_ids[i:i + BATCH]
                rows = Delivery.browse(chunk).read(['item_details'])
                for r in rows:
                    did = r.get('id')
                    s = r.get('item_details') or ''
                    if not isinstance(s, str):
                        try:
                            s = str(s)
                        except Exception:
                            s = ''
                    id_to_item[did] = s

            # 5️⃣ Parse division names and aggregate parcel_bale quantities
            division_totals = Counter()

            for lr, bale_qty in lr_bale_map.items():
                delivery_id = lr_to_delivery_id.get(lr)
                if not delivery_id:
                    # no related delivery.check → skip (you could map to "Unknown" if needed)
                    continue
                s = id_to_item.get(delivery_id, '') or ''
                s = s.strip()
                if not s:
                    division_name = _("Uncategorized")
                else:
                    # substring after first closing bracket ']'
                    rb = s.find(']')
                    after = s[rb + 1:].strip() if rb != -1 else s.strip()
                    after = re.sub(r'\s+', ' ', after)
                    # split on hyphen
                    parts = [p.strip() for p in re.split(r'\s*-\s*', after) if p.strip()]

                    division_name = ""
                    if parts and len(parts[0]) == 1 and parts[0].isalpha():
                        if len(parts) >= 2:
                            division_name = f"{parts[0]}-{parts[1]}"
                        else:
                            division_name = after
                    else:
                        division_name = parts[0] if parts else after
                    if not division_name:
                        division_name = _("Uncategorized")

                division_totals[division_name] += bale_qty

            if not division_totals:
                return []

            # 6️⃣ Build result list and sort by total bale qty desc
            results = [
                {"division_name": name, "parcel_bale_total": round(total, 2)}
                for name, total in division_totals.items()
            ]
            results.sort(key=lambda x: x['parcel_bale_total'], reverse=True)

            # 7️⃣ Return top N
            return results[:int(top_n)]

        except Exception as e:
            _logger.exception("Error in get_divisionwise_bale_totals: %s", e)
            return []

    @api.model
    def get_zone_summary_and_top5(self, top_n=5, **kwargs):
        """
        Returns:
        {
            'total_zones': <int>,  # total distinct zones across matched LRs
            'total_lrs': <int>,    # total unique LR numbers found
            'top_zones': [
                {'zone_id': <int>, 'zone_name': <str>, 'zone_count': <int>},
                ...
            ]
        }

        Logic:
         - From open.parcel where state='draft' and parcel_lr_no is present
         - Deduplicate parcel_lr_no
         - Match with delivery.check.logistic_lr_number
         - For each LR, take latest record (id desc)
         - Group by delivery.check.placements (Many2one -> placement.master.data)
         - Count number of LRs per zone
         - Return total zones, total LRs, and top 5 zones by count
        """
        try:
            # 1️⃣ Collect draft LRs
            Parcel = self.env['open.parcel'].sudo()
            parcel_domain = [
                ('state', '=', ['draft', 'done']),
                ('parcel_lr_no', '!=', False),
            ]
            parcels = Parcel.search_read(parcel_domain, ['parcel_lr_no'])

            lr_set = {str(p['parcel_lr_no']).strip() for p in parcels if p.get('parcel_lr_no')}
            if not lr_set:
                return {'total_zones': 0, 'total_lrs': 0, 'top_zones': []}

            lr_list = list(lr_set)

            # 2️⃣ Find related delivery.check (latest only per LR)
            Delivery = self.env['delivery.check'].sudo()
            deliveries = Delivery.search([('logistic_lr_number', 'in', lr_list)], order='id desc')

            # 3️⃣ Map each LR to its placement (zone)
            lr_to_zone = {}
            for d in deliveries:
                lr_key = str(d.logistic_lr_number or '').strip()
                if not lr_key:
                    continue
                if lr_key not in lr_to_zone and d.placements:
                    lr_to_zone[lr_key] = d.placements.id

            if not lr_to_zone:
                return {'total_zones': 0, 'total_lrs': 0, 'top_zones': []}

            # 4️⃣ Count unique LRs per zone
            zone_counts = Counter()
            for zone_id in lr_to_zone.values():
                if zone_id:
                    zone_counts[zone_id] += 1

            total_lrs = len(lr_to_zone)
            total_zones = len(zone_counts)

            if not zone_counts:
                return {'total_zones': total_zones, 'total_lrs': total_lrs, 'top_zones': []}

            # 5️⃣ Fetch zone names from placement.master.data
            Placement = self.env['placement.master.data'].sudo()
            zone_ids = list(zone_counts.keys())
            zones = Placement.browse(zone_ids).read(['name'])

            id_name_map = {z['id']: z.get('name') or f'Zone #{z["id"]}' for z in zones}

            # 6️⃣ Build top zones list
            top_zones = [
                {
                    'zone_id': zone_id,
                    'zone_name': id_name_map.get(zone_id, f'Zone #{zone_id}'),
                    'zone_count': count
                }
                for zone_id, count in zone_counts.items()
            ]

            # Sort by count descending
            top_zones.sort(key=lambda x: x['zone_count'], reverse=True)
            top_zones = top_zones[:int(top_n)]

            # 7️⃣ Return the summary
            return {
                'total_zones': total_zones,
                'total_lrs': total_lrs,
                'top_zones': top_zones
            }

        except Exception as e:
            _logger.exception("Error in get_zone_summary_and_top5: %s", e)
            return {'total_zones': 0, 'total_lrs': 0, 'top_zones': []}

