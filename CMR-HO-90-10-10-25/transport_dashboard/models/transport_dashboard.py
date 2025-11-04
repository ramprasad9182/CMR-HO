# models/stock_picking.py
from odoo import api, fields, models
from datetime import timedelta
import re
import logging
_logger = logging.getLogger(__name__)

class Picking(models.Model):
    _inherit = "stock.picking"

    @api.model
    def get_delivery_dashboard_summary(self, **kwargs):
        Company = self.env['res.company']
        Category = self.env['product.category']
        Move = self.env['stock.move']
        def _to_ids(val):
            """Positive ints only; ignore 0 / None / 'All' sentinels."""
            if not val:
                return set()
            if isinstance(val, int):
                return {val} if val > 0 else set()
            out = set()
            for x in (val or []):
                if isinstance(x, int) and x > 0:
                    out.add(x)
                elif isinstance(x, str) and x.isdigit() and int(x) > 0:
                    out.add(int(x))
                elif isinstance(x, dict):
                    xid = x.get("id") or x.get("value") or x.get("res_id")
                    if isinstance(xid, int) and xid > 0:
                        out.add(xid)
            return out

        # ------------ inputs ------------
        group_by = (kwargs.get("group_by") or "category").lower()  # we’ll keep category/root behavior
        period_days = kwargs.get("period_days")
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")

        filter_cat_ids = _to_ids(kwargs.get("category_ids"))
        requested_company_ids = _to_ids(kwargs.get("company_ids"))

        # --- issuer = current main company only
        issuer_company_id = self.env.company.id  # single "main company" as issuer

        # --- counterparties = all companies except main, optionally intersect with user selection
        all_company_ids = set(self.env['res.company'].search([]).ids)
        counterparty_company_ids = all_company_ids - {issuer_company_id}
        if requested_company_ids:
            counterparty_company_ids &= requested_company_ids  # keep only selected
        if not counterparty_company_ids:
            return {"total_deliveries": 0, "total_categories": 0, "rows": []}

        # company partners for counterparties (use commercial partner on domain)
        counterparty_partner_ids = self.env['res.company'].browse(list(counterparty_company_ids)).mapped(
            'partner_id').ids

        # --- domain (on moves via picking_*)
        domain = [
            ('picking_id.state', '!=', 'cancel'),
            ('picking_id.stock_picking_type', 'in', ['exchange', 'receipt', 'goods_return', 'delivery','pos_order', 'regular', 'damage', 'return','damage_main', 'main_damage', 'return_main']),
            ('picking_id.company_id', '=', issuer_company_id),  # issuer fixed to main
            ('picking_id.partner_id.commercial_partner_id', 'in', counterparty_partner_ids),  # counterparty
        ]
        # dates: custom range beats period_days
        if start_date and end_date:
            start_dt = fields.Datetime.to_datetime(start_date)
            end_dt = fields.Datetime.to_datetime(end_date)
            domain += [('picking_id.date_done', '>=', start_dt), ('picking_id.date_done', '<=', end_dt)]
        elif period_days:
            today = fields.Date.context_today(self)
            start_dt = fields.Datetime.to_datetime(today - timedelta(days=int(period_days)))
            domain.append(('picking_id.date_done', '>=', start_dt))

        # category filter: accept descendants → use a domain so DB prunes early
        if filter_cat_ids:
            domain.append(('product_id.categ_id', 'child_of', list(filter_cat_ids)))

        # ------------ read_group on moves: (picking, leaf_category) ------------
        # Each row = one delivery×category bucket; we’ll treat each row as "1 bale".
        # 1) read_group by (picking, product) — supported & fast
        groups = self.env['stock.move'].read_group(
            domain,
            fields=['id:count'],
            groupby=['picking_id', 'product_id'],
            lazy=False,
        )
        if not groups:
            return {"total_deliveries": 0, "total_categories": 0, "rows": []}

        # 2) fetch picking flags once
        picking_ids = {g['picking_id'][0] for g in groups if g.get('picking_id')}
        flags = {r['id']: (bool(r.get('is_received')), bool(r.get('is_opened')))
                 for r in self.search_read([('id', 'in', list(picking_ids))], ['id', 'is_received', 'is_opened'])}

        # 3) map product -> leaf category (no binaries requested)
        prod_ids = {g['product_id'][0] for g in groups if g.get('product_id')}
        prod_rows = self.env['product.product'].search_read([('id', 'in', list(prod_ids))], ['id', 'categ_id'])
        prod_leaf = {r['id']: (r['categ_id'][0] if r.get('categ_id') else False) for r in prod_rows}
        leaf_ids = {cid for cid in prod_leaf.values() if cid}

        # 4) leaf -> ROOT category (id & name), cached
        root_of_leaf = {}
        root_name = {}
        if leaf_ids:
            for leaf in self.env['product.category'].browse(list(leaf_ids)):
                cur = leaf
                while cur.parent_id:
                    cur = cur.parent_id
                root_of_leaf[leaf.id] = cur.id
                if cur.id not in root_name:
                    root_name[cur.id] = cur.name or "Uncategorized"

        # 5) aggregate: 1 bale per UNIQUE (picking, root_category)
        seen_pairs = set()
        by_name = {}  # name_norm -> {name,total,received,opened}
        for g in groups:
            p = g.get('picking_id');
            prod = g.get('product_id')
            if not p or not prod:
                continue
            pid = p[0];
            prod_id = prod[0]
            leaf = prod_leaf.get(prod_id)
            if not leaf:
                continue
            root_id = root_of_leaf.get(leaf)
            if not root_id:
                continue

            pair = (pid, root_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            name = root_name.get(root_id, "Uncategorized")
            is_recv, is_open = flags.get(pid, (False, False))

            k = (name or "").strip().lower()
            agg = by_name.setdefault(k, {"name": name, "total": 0, "received": 0, "opened": 0})
            agg["total"] += 1
            if is_recv:
                agg["received"] += 1
                if is_open:
                    agg["opened"] += 1

        # 6) flatten
        rows = []
        for k, d in by_name.items():
            total = d["total"]
            received = min(d["received"], total)
            opened = min(d["opened"], received)
            rows.append({
                "group_key": f"catname:{k}",
                "category_name": d["name"],
                "total_bales": total,
                "bales_in_transit": max(0, total - received),
                "bales_received": received,
                "bales_opened": opened,
                "bales_not_opened": max(0, received - opened),
                "pending_bales": max(0, total - opened),
            })

        rows.sort(key=lambda r: (r["category_name"] or "").lower())
        return {
            "total_deliveries": len(picking_ids),
            "total_categories": len(rows),
            "rows": rows,
        }

    @api.model
    def get_return_dashboard_summary(self, payload=None, **kwargs):
        """Return dashboard:
           - state = done
           - issuer company_id: any non-main company (intersect with user selection if provided)
           - partner_id.commercial_partner_id: main company
           - NO picking type filter
           - Count 1 bale per unique (picking × ROOT category)
        """
        kwargs = payload or kwargs or {}
        Company = self.env['res.company']
        Category = self.env['product.category']
        Move = self.env['stock.move']
        Product = self.env['product.product']
        from datetime import timedelta
        from odoo import fields
        def _to_ids(val):
            """Normalize multiselect values -> set of positive ints."""
            if not val:
                return set()
            if isinstance(val, int):
                return {val} if val > 0 else set()
            out = set()
            for x in (val or []):
                if isinstance(x, int) and x > 0:
                    out.add(x)
                elif isinstance(x, str) and x.isdigit() and int(x) > 0:
                    out.add(int(x))
                elif isinstance(x, dict):
                    xid = x.get("id") or x.get("value") or x.get("res_id")
                    if isinstance(xid, int) and xid > 0:
                        out.add(xid)
            return out

        # ------------ inputs ------------
        period_days = kwargs.get("period_days")
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        filter_cat_ids = _to_ids(kwargs.get("category_ids"))
        requested_company_ids = _to_ids(kwargs.get("company_ids"))  # issuers (non-main)

        # ------------ main & issuers ------------
        main_company_id = self.env.company.id
        main_partner_id = self.env.company.partner_id.commercial_partner_id.id

        # Issuers = all companies except main, ∩ selection (if any)
        all_company_ids = set(Company.search([]).ids)
        issuer_company_ids = all_company_ids - {main_company_id}
        if requested_company_ids:
            issuer_company_ids &= requested_company_ids
        if not issuer_company_ids:
            return {"total_deliveries": 0, "total_categories": 0, "rows": []}

        # ------------ domain (NO picking type) ------------
        domain = [
            ('picking_id.state', '!=', 'cancel'),
            ('picking_id.stock_picking_type', 'in', ['exchange', 'receipt', 'goods_return', 'delivery','pos_order', 'regular', 'damage', 'return','damage_main', 'main_damage', 'return_main' ]),
            ('picking_id.company_id', 'in', list(issuer_company_ids)),  # issuer = non-main
            ('picking_id.partner_id.commercial_partner_id', '=', main_partner_id)  # counterparty = main
        ]

        # ---------- DATE WINDOW (handle done vs not-done correctly) ----------
        # For done pickings use date_done, for others use scheduled_date.
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        period_days = kwargs.get("period_days")

        if start_date and end_date:
            start_dt = fields.Datetime.to_datetime(start_date)
            end_dt = fields.Datetime.to_datetime(end_date)
            domain += [
                '|',
                '&', ('picking_id.date_done', '!=', False),
                '&', ('picking_id.date_done', '>=', start_dt),
                ('picking_id.date_done', '<=', end_dt),
                '&', ('picking_id.date_done', '=', False),
                '&', ('picking_id.scheduled_date', '>=', start_dt),
                ('picking_id.scheduled_date', '<=', end_dt),
            ]
        elif period_days:
            today = fields.Date.context_today(self)
            start_dt = fields.Datetime.to_datetime(today - timedelta(days=int(period_days)))
            domain += [
                '|',
                ('picking_id.date_done', '>=', start_dt),  # done ones
                '&', ('picking_id.date_done', '=', False),  # not-done ones
                ('picking_id.scheduled_date', '>=', start_dt),
            ]

        # ---------- Category filter (unchanged) ----------
        filter_cat_ids = _to_ids(kwargs.get("category_ids"))
        if filter_cat_ids:
            domain.append(('product_id.categ_id', 'child_of', list(filter_cat_ids)))

        # Ensure access to both issuer(s) & main when reading moves/pickings
        allowed_ids = list(issuer_company_ids | {main_company_id})
        MoveCtx = Move.with_context(allowed_company_ids=allowed_ids)

        # ------------ read_group on moves: (picking, product) ------------
        groups = MoveCtx.read_group(
            domain,
            fields=['id:count'],
            groupby=['picking_id', 'product_id'],
            lazy=False,
        )
        if not groups:
            return {"total_deliveries": 0, "total_categories": 0, "rows": []}

        # 2) fetch picking flags once
        picking_ids = {g['picking_id'][0] for g in groups if g.get('picking_id')}
        flags = {
            r['id']: (bool(r.get('is_received')), bool(r.get('is_opened')))
            for r in self.with_context(allowed_company_ids=allowed_ids)
            .search_read([('id', 'in', list(picking_ids))], ['id', 'is_received', 'is_opened'])
        }

        # 3) product -> leaf category
        prod_ids = {g['product_id'][0] for g in groups if g.get('product_id')}
        prod_rows = Product.search_read([('id', 'in', list(prod_ids))], ['id', 'categ_id'])
        prod_leaf = {r['id']: (r['categ_id'][0] if r.get('categ_id') else False) for r in prod_rows}
        leaf_ids = {cid for cid in prod_leaf.values() if cid}

        # 4) leaf -> ROOT category (id & name)
        root_of_leaf, root_name = {}, {}
        if leaf_ids:
            for leaf in Category.browse(list(leaf_ids)):
                cur = leaf
                while cur.parent_id:
                    cur = cur.parent_id
                root_of_leaf[leaf.id] = cur.id
                if cur.id not in root_name:
                    root_name[cur.id] = cur.name or "Uncategorized"

        # 5) aggregate: **1 bale per UNIQUE (picking × ROOT)**
        seen_pairs = set()  # {(picking_id, root_id)}
        per_root = {}  # root_id -> {name,total,received,opened}
        for g in groups:
            p = g.get('picking_id');
            prod = g.get('product_id')
            if not p or not prod:
                continue
            pid = p[0]
            prod_id = prod[0]
            leaf_id = prod_leaf.get(prod_id)
            if not leaf_id:
                continue
            root_id = root_of_leaf.get(leaf_id)
            if not root_id:
                continue

            key = (pid, root_id)
            if key in seen_pairs:
                continue  # de-dup: count once per (picking × root category)
            seen_pairs.add(key)

            name = root_name.get(root_id, "Uncategorized")
            is_recv, is_open = flags.get(pid, (False, False))

            rec = per_root.setdefault(root_id, {"name": name, "total": 0, "received": 0, "opened": 0})
            rec["total"] += 1
            if is_recv:
                rec["received"] += 1
                if is_open:
                    rec["opened"] += 1

        # 6) flatten (keyed by root_id — no merge-by-name)
        rows = []
        for rid, d in per_root.items():
            total = int(d["total"])
            received = min(int(d["received"]), total)
            opened = min(int(d["opened"]), received)
            rows.append({
                "group_key": f"root:{rid}",  # stable unique key
                "category_name": d["name"],  # ROOT category name
                "total_bales": total,
                "bales_in_transit": max(0, total - received),
                "bales_received": received,
                "bales_opened": opened,
                "bales_not_opened": max(0, received - opened),
                "pending_bales": max(0, total - opened),
            })

        rows.sort(key=lambda r: (r["category_name"] or "").lower())
        return {
            "total_deliveries": len(picking_ids),
            "total_categories": len(rows),
            "rows": rows,
        }

    @api.model
    def transfer_LR_dashboard_summary(self, payload=None, **kwargs):
        kwargs = payload or kwargs or {}
        Company = self.env['res.company']
        Picking = self.env['stock.picking']

        def _to_ids(val):
            if not val:
                return set()
            if isinstance(val, int):
                return {val} if val > 0 else set()
            out = set()
            for x in (val or []):
                if isinstance(x, int) and x > 0:
                    out.add(x)
                elif isinstance(x, str) and x.isdigit() and int(x) > 0:
                    out.add(int(x))
                elif isinstance(x, dict):
                    xid = x.get("id") or x.get("value") or x.get("res_id")
                    if isinstance(xid, int) and xid > 0:
                        out.add(xid)
            return out

        def _to_tokens(val):
            """Accept list[str|{id|name|value}], return unique non-empty strings."""
            if not val:
                return set()
            out = set()
            for x in val:
                if isinstance(x, str) and x.strip():
                    out.add(x.strip())
                elif isinstance(x, dict):
                    s = x.get("name") or x.get("value") or x.get("id")
                    if isinstance(s, str) and s.strip():
                        out.add(s.strip())
            return out

        def _norm_lr(s):
            if not s:
                return None
            s = str(s).strip().upper()
            s = re.sub(r"\s+", " ", s)
            s = s.strip("'\"`")
            return s or None

        # ---- inputs ----
        period_days  = kwargs.get("period_days")
        start_date   = kwargs.get("start_date")
        end_date     = kwargs.get("end_date")
        requested_company_ids = _to_ids(kwargs.get("company_ids"))
        lr_filters_raw        = _to_tokens(kwargs.get("lr_numbers") or kwargs.get("lr_filter"))

        # ---- issuer/main & counterparties ----
        issuer_company_id = self.env.company.id
        all_company_ids   = set(Company.search([]).ids)
        counterparty_company_ids = all_company_ids - {issuer_company_id}
        if requested_company_ids:
            counterparty_company_ids &= requested_company_ids
        if not counterparty_company_ids:
            return {"total_deliveries": 0, "total_categories": 0, "rows": []}

        counterparty_partner_ids = Company.browse(list(counterparty_company_ids)).mapped('partner_id.id')

        # ---- domain on pickings (no moves) ----
        domain = [
            ('state', '=', 'done'),
            ('stock_picking_type', '=', 'delivery'),
            ('company_id', '=', issuer_company_id),
            ('partner_id.commercial_partner_id', 'in', counterparty_partner_ids),
        ]

        # dates
        if start_date and end_date:
            start_dt = fields.Datetime.to_datetime(start_date)
            end_dt   = fields.Datetime.to_datetime(end_date)
            domain += [('date_done', '>=', start_dt), ('date_done', '<=', end_dt)]
        elif period_days:
            today    = fields.Date.context_today(self)
            start_dt = fields.Datetime.to_datetime(today - timedelta(days=int(period_days)))
            domain.append(('date_done', '>=', start_dt))

        # optional LR filter (exact match on raw field)
        if lr_filters_raw:
            domain.append(('lr_number', 'in', list(lr_filters_raw)))

        # ---- fetch pickings (do NOT use limit=0) ----
        rows_read = Picking.search_read(domain, ['id', 'lr_number', 'is_received', 'is_opened'])
        if not rows_read:
            return {"total_deliveries": 0, "total_categories": 0, "rows": []}

        # ---- aggregate: 1 bale per (picking × normalized LR) ----
        seen = set()
        per_lr = {}
        picking_ids = set()
        lr_filters_norm = {_norm_lr(t) for t in lr_filters_raw} if lr_filters_raw else set()

        for r in rows_read:
            pid = r['id']
            lr_norm = _norm_lr(r.get('lr_number')) or "UNSPECIFIED"

            # enforce normalized filter too (avoids casing/spacing dupes)
            if lr_filters_norm and lr_norm not in lr_filters_norm:
                continue

            key = (pid, lr_norm)
            if key in seen:
                continue
            seen.add(key)
            picking_ids.add(pid)

            is_recv = bool(r.get('is_received'))
            is_open = bool(r.get('is_opened'))

            rec = per_lr.setdefault(lr_norm, {"name": lr_norm, "total": 0, "received": 0, "opened": 0})
            rec["total"] += 1
            if is_recv:
                rec["received"] += 1
                if is_open:
                    rec["opened"] += 1

        # ---- build rows ----
        rows = []
        for lr_norm, d in per_lr.items():
            total    = int(d["total"])
            received = min(int(d["received"]), total)
            opened   = min(int(d["opened"]), received)
            rows.append({
                "group_key": f"lr:{lr_norm}",
                "category_name": d["name"],  # shows LR in your first column
                "total_bales": total,
                "bales_in_transit": max(0, total - received),
                "bales_received": received,
                "bales_opened": opened,
                "bales_not_opened": max(0, received - opened),
                "pending_bales": max(0, total - opened),
            })

        rows.sort(key=lambda r: (r["category_name"] or "").lower())
        return {
            "total_deliveries": len(picking_ids),
            "total_categories": len(rows),
            "rows": rows,
        }

    @api.model
    def LR_return_dashboard_summary(self, payload=None, **kwargs):
        kwargs = payload or kwargs or {}
        Company = self.env['res.company']
        Picking = self.env['stock.picking']

        # ----- helpers
        def _to_ids(val):
            if not val:
                return set()
            if isinstance(val, int):
                return {val} if val > 0 else set()
            out = set()
            for x in (val or []):
                if isinstance(x, int) and x > 0:
                    out.add(x)
                elif isinstance(x, str) and x.isdigit() and int(x) > 0:
                    out.add(int(x))
                elif isinstance(x, dict):
                    xid = x.get("id") or x.get("value") or x.get("res_id")
                    if isinstance(xid, int) and xid > 0:
                        out.add(xid)
            return out

        def _to_tokens(val):
            if not val:
                return set()
            out = set()
            for x in val:
                if isinstance(x, str) and x.strip():
                    out.add(x.strip())
                elif isinstance(x, dict):
                    s = x.get("name") or x.get("value") or x.get("id")
                    if isinstance(s, str) and s.strip():
                        out.add(s.strip())
            return out

        def _norm_lr(s):
            if not s:
                return None
            s = str(s).strip().upper()
            s = re.sub(r"\s+", " ", s)
            s = s.strip("'\"`")
            return s or None

        # ----- inputs
        period_days = kwargs.get("period_days")
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        req_company_ids = _to_ids(kwargs.get("company_ids"))  # issuers (non-main)
        lr_filters_raw = _to_tokens(kwargs.get("lr_numbers") or kwargs.get("lr_filter"))

        # ----- roles
        main_company_id = self.env.company.id
        main_partner_id = self.env.company.partner_id.commercial_partner_id.id
        all_company_ids = set(Company.search([]).ids)
        issuer_company_ids = all_company_ids - {main_company_id}  # all except main
        if req_company_ids:
            issuer_company_ids &= req_company_ids
        if not issuer_company_ids:
            return {"total_deliveries": 0, "total_categories": 0, "rows": []}
        # ----- base domain (on pickings)
        domain = [
            ('state', '!=', 'cancel'),
            ('company_id', 'in', list(issuer_company_ids)),  # issuer = non-main
            ('partner_id.commercial_partner_id', '=', main_partner_id),  # counterparty = main
        ]

        # date window (done vs scheduled)
        if start_date and end_date:
            start_dt = fields.Datetime.to_datetime(start_date)
            end_dt = fields.Datetime.to_datetime(end_date)
            domain += [
                '|',
                '&', ('date_done', '!=', False),
                '&', ('date_done', '>=', start_dt), ('date_done', '<=', end_dt),
                '&', ('date_done', '=', False),
                '&', ('scheduled_date', '>=', start_dt), ('scheduled_date', '<=', end_dt),
            ]
        elif period_days:
            today = fields.Date.context_today(self)
            start_dt = fields.Datetime.to_datetime(today - timedelta(days=int(period_days)))
            domain += [
                '|',
                ('date_done', '>=', start_dt),
                '&', ('date_done', '=', False), ('scheduled_date', '>=', start_dt),
            ]

        # LR filter (raw)
        if lr_filters_raw:
            domain.append(('lr_number', 'in', list(lr_filters_raw)))

        # cross-company visibility (issuers + main)
        allowed_ids = list(issuer_company_ids | {main_company_id})
        PickCtx = Picking.with_context(allowed_company_ids=allowed_ids)

        # ----- fetch
        rows_read = PickCtx.search_read(domain, ['id', 'lr_number', 'is_received', 'is_opened'])
        if not rows_read:
            return {"total_deliveries": 0, "total_categories": 0, "rows": []}

        # ----- aggregate (1 bale per picking × normalized LR)
        seen = set()
        per_lr = {}
        picking_ids = set()
        lr_filters_norm = {_norm_lr(t) for t in lr_filters_raw} if lr_filters_raw else set()

        for r in rows_read:
            pid = r['id']
            lr_norm = _norm_lr(r.get('lr_number')) or "UNSPECIFIED"
            if lr_filters_norm and lr_norm not in lr_filters_norm:
                continue

            key = (pid, lr_norm)
            if key in seen:
                continue
            seen.add(key)
            picking_ids.add(pid)

            is_recv = bool(r.get('is_received'))
            is_open = bool(r.get('is_opened'))
            rec = per_lr.setdefault(lr_norm, {"name": lr_norm, "total": 0, "received": 0, "opened": 0})
            rec["total"] += 1
            if is_recv:
                rec["received"] += 1
                if is_open:
                    rec["opened"] += 1

        # ----- rows
        rows = []
        for lr_norm, d in per_lr.items():
            total = int(d["total"])
            received = min(int(d["received"]), total)
            opened = min(int(d["opened"]), received)
            rows.append({
                "group_key": f"lr:{lr_norm}",
                "category_name": d["name"],
                "total_bales": total,
                "bales_in_transit": max(0, total - received),
                "bales_received": received,
                "bales_opened": opened,
                "bales_not_opened": max(0, received - opened),
                "pending_bales": max(0, total - opened),
            })

        rows.sort(key=lambda r: (r["category_name"] or "").lower())
        return {
            "total_deliveries": len(picking_ids),
            "total_categories": len(rows),
            "rows": rows,
        }

    @api.model
    def get_lr_numbers(self, q=None, limit=200):
        """Return distinct LR values for a dropdown."""
        domain = [('lr_number', '!=', False)]
        if q:
            q = q.strip()
            if q:
                domain = ['&'] + domain + [('lr_number', 'ilike', q)]

        # distinct list of lr_number via read_group
        groups = self.read_group(
            domain,
            fields=['lr_number'],
            groupby=['lr_number'],
            orderby='lr_number asc',
            lazy=False,
        )

        # Build multiselect options: id=name=<LR string>
        options = [
            {'id': g['lr_number'], 'name': g['lr_number']}
            for g in groups
            if g.get('lr_number')
        ]

        return {
            'lr_numbers': options,  # [{id:str, name:str}]
            'selected': []  # nothing preselected
        }


class ProductCategory(models.Model):
    _inherit = "product.category"

    @api.model
    def get_parent_product(self):
        rows = self.search_read([('parent_id', '=', False)], ['id', 'name'], order='name asc')
        return {
            'parent_product': rows,  # [{id,name}]
            'parent_list': []  # empty = no preselected filter
        }

    @api.model
    def search_top_categories(self, q="", limit=50):
        domain = [("parent_id", "=", False)]
        if q:
            domain.append(("name", "ilike", q))
        recs = self.search(domain, limit=limit, order="name asc")
        return [{"id": r.id, "name": r.name} for r in recs]


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def get_company_list(self):
        main_id = self.env.company.id
        rows = self.search_read([], ['id', 'name', 'partner_id'], order='name asc')
        return {
            'company_list': [{
                'id': r['id'],
                'name': r['name'],
                'partner_id': r['partner_id'][0] if r['partner_id'] else False,
            } for r in rows],
            'selected_companies': []  # empty => All (i.e., all except main)
        }


    @api.model
    def search_companies(self, q="", limit=50, main_only=True):
        """Typeahead search (used by a searchable multiselect)."""
        domain = []
        if main_only:
            domain.append()
        if q:
            domain.append(('name', 'ilike', q))
        recs = self.search(domain, limit=limit, order='name asc')
        return [{'id': c.id, 'name': c.name} for c in recs]