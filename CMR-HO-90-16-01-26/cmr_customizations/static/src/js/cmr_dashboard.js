/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const { Component, onWillStart, useState } = owl;
const actionRegistry = registry.category("actions");

export class LogisticDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            // PO counts
            LrWithPO: 0,
            LrWithoutPO: 0,
            loadingPO: true,
            // Status bars
            status: { total: 0, delivered: 0, in_transit: 0, delayed: 0, canceled: 0 },
            loadingStatus: true,
            // state additions
            draft: {today: 0, week: 0, month: 0},  // upcoming (state=draft)
            done: { today: 0, week: 0, month: 0},  // delivered (state=done)
            loadingDelivery: true,
            // state additions (inside setup -> useState initial object)
            partialDelivered: 0,
            loadingPartialDelivered: true,
             // ... your other state ...
            topProducts: { total: 0, max: 0, items: [] },
            loadingTopProducts: true,
            //1-3
            basementDelivery:{ delivered_total:0, basement:0,},
            loadingBasementDelivery: true,
            // 1) state additions (in useState initial object)
            roleSplit: { agent: 0, transporter: 0, vendor: 0 },
            loadingRoleSplit: true,
            // 1) state additions (in your useState initial object)
            openParcel: { draft: 0, done: 0, total: 0 },
            loadingOpenParcel: true,
            // 1) state additions (in your useState initial object)
            openParcel: { draft: 0, done: 0},
            loadingOpenParcel: true,
            // state additions
            chargesTotals: { draft_rupees: 0, done_rupees: 0, total_rupees: 0 },
            loadingChargesTotals: true,
            // top unopened zones
             unopenedZone: { total: 0, items: [] },
             loadingUnopenedZone: true,
             // top unopened divisions
             unopenedDivision: { total: 0, items: [] },
             loadingUnopenedDivision: true,
             // top divisions - bales
             unopenedDivisionBales: { total: 0, items: [] },
             loadingUnopenedDivisionBales: true,
             // Zone Summary
             unopenedZoneSummary: { total_zones: 0, total_lrs: 0, top_zones: [] },
             loadingUnopenedZoneSummary: true,

        });

        // % of total (for horizontal bars)
        this.pct = (n, total) => {
          const t = Number(total || 0), v = Number(n || 0);
          if (!t) return 0;
          return Math.max(0, Math.min(100, Math.round((v * 100) / t)));
        };

        // height % vs max (for columns)
        this.hPct = (v) => {
          const m = Number(this.state.topProducts.max || 0);
          const n = Number(v || 0);
          if (!m) return 0;
          return Math.round((n * 100) / m);
         };
        onWillStart(async () => {
            await Promise.all([
                this.fetchLRvsPO(),
                this.fetchLRStatus(),
                this.fetchDeliveryPeriods(),
                this.fetchPartialDelivered(),
                this.fetchTop5Products(),
                this.fetchBasementDelivery(),
                this.fetchRoleSplit(),
                this.fetchOpenParcelCounts(),
                this.fetchChargesTotals({ screen: "Logistic Entry Check" }),
                this.fetchUnopenedZones(),
                this.fetchUnopenedDivision(),
                this.fetchDivisionBales(),
                this.fetchZoneSummary(),
            ]);
        });
    }
    async fetchZoneSummary(filters = {}) {
      try {
        this.state.loadingUnopenedZoneSummary = true;

        const res = await this.orm.call(
          "logistic.screen.data",
          "get_zone_summary_and_top5",
          [5],
          { kwargs: filters }
        );

        if (res && typeof res === 'object' && !Array.isArray(res)) {
          const total_zones = Number(res.total_zones || 0);
          const total_lrs = Number(res.total_lrs || 0);
          const top_zones = Array.isArray(res.top_zones) ? res.top_zones : [];

          // keep the exact ids returned by the server for exact-open actions
          const lr_ids = Array.isArray(res.lr_ids) ? res.lr_ids : [];
          const zone_lr_ids = (res.zone_lr_ids && typeof res.zone_lr_ids === 'object') ? res.zone_lr_ids : {};

          this.state.unopenedZoneSummary = { total_zones, total_lrs, top_zones, lr_ids, zone_lr_ids };
        } else {
          this.state.unopenedZoneSummary = { total_zones: 0, total_lrs: 0, top_zones: [], lr_ids: [], zone_lr_ids: {} };
        }

      } catch (e) {
        console.error("Unopened Zone Summary fetch failed:", e);
        this.notification.add("Failed to load unopened zone summary.", { type: "danger" });
        this.state.unopenedZoneSummary = { total_zones: 0, total_lrs: 0, top_zones: [], lr_ids: [], zone_lr_ids: {} };
      } finally {
        this.state.loadingUnopenedZoneSummary = false;
      }
    }


    getTopZones() {
      return (this.state.unopenedZoneSummary && this.state.unopenedZoneSummary.top_zones) || [];
    }
    async fetchDivisionBales(filters = {}) {
      try {
        this.state.loadingUnopenedDivisionBales = true;
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_divisionwise_bale_totals",
          [5],
          { kwargs: filters }
        );
        const items = Array.isArray(res.results) ? res.results : [];
        this.state.unopenedDivisionBales = {
          total: items.length,
          items,
          delivery_ids: Array.isArray(res.delivery_ids) ? res.delivery_ids : [],
          division_delivery_ids: (res.division_delivery_ids && typeof res.division_delivery_ids === 'object') ? res.division_delivery_ids : {},
        };
      } catch (e) {
        console.error("Unopened division bales fetch failed:", e);
        this.notification.add("Failed to load unopened division bales counts.", { type: "danger" });
        this.state.unopenedDivisionBales = { total: 0, items: [], delivery_ids: [], division_delivery_ids: {} };
      } finally {
        this.state.loadingUnopenedDivisionBales = false;
      }
    }

    async fetchUnopenedZones(filters = {}) {
      try {
        this.state.loadingUnopenedZone = true;
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_unopened_zone_counts",
          [5],
          { kwargs: filters }
        );

        const items = Array.isArray(res.results) ? res.results : [];
        this.state.unopenedZone = {
          total: items.length,
          items,
          lr_ids: Array.isArray(res.lr_ids) ? res.lr_ids : [],
          placement_lr_ids: (res.placement_lr_ids && typeof res.placement_lr_ids === 'object') ? res.placement_lr_ids : {},
        };
      } catch (e) {
        console.error("Unopened Zone fetch failed:", e);
        this.notification.add("Failed to load unopened zone counts.", { type: "danger" });
        this.state.unopenedZone = { total: 0, items: [], lr_ids: [], placement_lr_ids: {} };
      } finally {
        this.state.loadingUnopenedZone = false;
      }
    }

    async fetchUnopenedDivision(filters = {}) {
      try {
        this.state.loadingUnopenedDivision = true;

        const res = await this.orm.call(
          "logistic.screen.data",        // model name where we added the server method
          "get_unopened_division_counts",    // method name we just wrote
          [5],                           // top N zones
          { kwargs: filters }
        );

        const items = Array.isArray(res) ? res : [];
        this.state.unopenedDivision = { total: items.length, items };

      } catch (e) {
        console.error("Unopened division fetch failed:", e);
        this.notification.add("Failed to load unopened division counts.", { type: "danger" });
        this.state.unopenedDivision = { total: 0, items: [] };
      } finally {
        this.state.loadingUnopenedDivision = false;
      }
    }
    async fetchTop5Products(filters = {}) {
      try {
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_top5_products_delivered",
          [],
          { kwargs: filters }
        );
        const total = (res && res.total) || 0;
        const max   = (res && res.max)   || 0;
        const items = (res && Array.isArray(res.items)) ? res.items : [];
        this.state.topProducts = { total: Number(total), max: Number(max), items };
      } catch (e) {
        console.error("Top 5 products fetch failed:", e);
        this.notification.add("Failed to load Top 5 Delivered Products.", { type: "danger" });
      } finally {
        this.state.loadingTopProducts = false;
      }
    }
    async fetchLRStatus() {
      try {
        const [a, b] = await Promise.all([
          this.orm.call("logistic.screen.data", "get_status_delivered", [], {}),
          this.orm.call("logistic.screen.data", "get_status_transit_delayed", [], {}),
        ]);

        const delivered  = Number((a && a.delivered) || 0);
        const in_transit = Number((b && b.in_transit) || 0);
        const delayed    = Number((b && b.delayed) || 0);
        const canceled   = Number((b && b.canceled) || 0); // 0 for now

        const total = delivered + in_transit + delayed + canceled;
        this.state.status = { total, delivered, in_transit, delayed, canceled };
      } catch (e) {
        console.error("Status fetch failed:", e);
        this.notification.add("Failed to load LR status.", { type: "danger" });
      } finally {
        this.state.loadingStatus = false;
      }
    }
    async fetchPartialDelivered(filters = {}) {
      try {
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_partial_delivered_count",
          [],
          { kwargs: filters }
        );
        const v = (res && res.partial_delivered) || 0;
        this.state.partialDelivered = Number(v);
      } catch (e) {
        console.error("Partial delivered fetch failed:", e);
        this.notification.add("Failed to load Partial Delivered LRs.", { type: "danger" });
      } finally {
        this.state.loadingPartialDelivered = false;
      }
    }
    async fetchDeliveryPeriods(filters = {}) {
      try {
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_delivery_period_counts",
          [],
          { kwargs: filters }
        );

        const d = (res && res.draft) || {};
        const dn = (res && res.done)  || {};

        this.state.draft = {
          today: Number(d.today || 0),
          week:  Number(d.week  || 0),
          month: Number(d.month || 0),
        };
        this.state.done = {
          today: Number(dn.today || 0),
          week:  Number(dn.week  || 0),
          month: Number(dn.month || 0),
        };
      } catch (e) {
        console.error("Delivery period counts fetch failed:", e);
        this.notification.add("Failed to load Upcoming/Delivered counts.", { type: "danger" });
      } finally {
        this.state.loadingDelivery = false;
      }
    }
    async fetchLRvsPO(filters = {}) {
      try {
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_lr_po_counts",
          [],
          { kwargs: filters }
        );
        const withPO    = (res && res.lr_with_po)    || 0;
        const withoutPO = (res && res.lr_without_po) || 0;
        this.state.LrWithPO    = Number(withPO);
        this.state.LrWithoutPO = Number(withoutPO);
      } catch (err) {
        console.error("LR vs PO fetch failed:", err);
        this.notification.add("Failed to load LR vs PO numbers.", { type: "danger" });
      } finally {
        this.state.loadingPO = false;
      }
    }
    async fetchBasementDelivery(filters = {}) {
      try {
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_basement_and_delivery_counts",
          [],
          { kwargs: filters }
        );
        const basement = Number((res && res.basement) || 0);
        const delivered_total = Number((res && res.delivered_total) || 0);
        this.state.basementDelivery = { basement, delivered_total };
      } catch (e) {
        console.error("Basement/Delivered fetch failed:", e);
        this.notification.add("Failed to load Delivered & Basement totals.", { type: "danger" });
      } finally {
        this.state.loadingBasementDelivery = false;
      }
    }
    async fetchRoleSplit(filters = {}) {
      try {
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_owner_role_split",
          [],
          { kwargs: filters }
        );
        const agent        = Number((res && res.agent) || 0);
        const transporter  = Number((res && res.transporter) || 0);
        const vendor       = Number((res && res.vendor) || 0);
        const total        = Number((res && res.total) || (agent + transporter + vendor));
        this.state.roleSplit = { agent, transporter, vendor };
      } catch (e) {
        console.error("Owner role split fetch failed:", e);
        this.notification.add("Failed to load Agent / Transporter / Vendor split.", { type: "danger" });
      } finally {
        this.state.loadingRoleSplit = false;
      }
    }
    async fetchOpenParcelCounts(filters = {}) {
      try {
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_open_parcel_state_counts",
          [],
          { kwargs: filters }
        );
        const draft = Number((res && res.draft) || 0);
        const done  = Number((res && res.done)  || 0);
        this.state.openParcel = { draft, done };
      } catch (e) {
        console.error("Open parcel counts fetch failed:", e);
        this.notification.add("Failed to load Open Parcel counts.", { type: "danger" });
      } finally {
        this.state.loadingOpenParcel = false;
      }
    }
    async fetchChargesTotals(filters = {}) {
      try {
        const res = await this.orm.call(
          "logistic.screen.data",
          "get_charges_totals",
          [],
          { kwargs: filters }
        );
        const r = res || {};
        this.state.chargesTotals = {
          draft_rupees: Number(r.draft_rupees || 0),
          done_rupees:  Number(r.done_rupees  || 0),
          total_rupees: Number(r.total_rupees || 0),
        };
      } catch (e) {
        console.error("Charges totals fetch failed:", e);
        this.notification.add("Failed to load Charges totals.", { type: "danger" });
      } finally {
        this.state.loadingChargesTotals = false;
      }
    }

    fmtINR(n) { return Number(n || 0).toLocaleString('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }); }
    fmt(n) { return Number(n || 0).toLocaleString(); }
    barPx(count, chartH = 140) {
      const max = Number(this.state.topProducts.max || 0);
      const c = Number(count || 0);
      if (!max) return 4;                        // tiny stub if no data
      return Math.max(4, Math.round((c * chartH) / max));
    }

// view action
    openLrWithPO = () => {
      const action = {
        type: "ir.actions.act_window",
        name: "LRs with PO",
        res_model: "logistic.screen.data",
        view_mode: "tree,form",
        views: [[false, "tree"], [false, "form"]],
        domain: [['logistic_entry_types', '=', 'automatic'], ['state', '=', 'done']],
        target: "current",
      };
      const actionSvc = this.env?.services?.action || this.action;
      if (actionSvc && actionSvc.doAction) {
        actionSvc.doAction(action);
      } else if (this.trigger) {
        this.trigger("do-action", action);
      } else {
        console.warn("No action service available", action);
      }
    };

    openLrWithoutPO = () => {
      const action = {
        type: "ir.actions.act_window",
        name: "LRs without PO",
        res_model: "logistic.screen.data",
        view_mode: "tree,form",
        views: [[false, "tree"], [false, "form"]],
        domain: [['logistic_entry_types', '=', 'manual'], ['state', '=', 'done']],
        target: "current",
      };
      const actionSvc = this.env?.services?.action || this.action;
      if (actionSvc && actionSvc.doAction) {
        actionSvc.doAction(action);
      } else if (this.trigger) {
        this.trigger("do-action", action);
      } else {
        console.warn("No action service available", action);
      }
    };

    openBasement = () => {
      const action = {
        type: "ir.actions.act_window",
        name: "Basement LRs",
        res_model: "logistic.screen.data",
        view_mode: "tree,form",
        views: [[false, "tree"], [false, "form"]],
        domain: [['state', '=', 'draft'], ['placements', '=', 'Basement']],
        target: "current",
      };
      const actionSvc = this.env?.services?.action || this.action;
      if (actionSvc && actionSvc.doAction) {
        actionSvc.doAction(action);
      } else if (this.trigger) {
        this.trigger("do-action", action);
      } else {
        console.warn("No action service available to open Basement action", action);
      }
    };

    openDelivered = () => {
      const action = {
        type: "ir.actions.act_window",
        name: "Delivered checks",
        res_model: "delivery.check",
        view_mode: "tree,form",
        views: [[false, "tree"], [false, "form"]],
        // robust domain to accept either state value
        domain: ['|', ['state', '=', 'delivered'], ['state', '=', 'delivery']],
        target: "current",
      };
      const actionSvc = this.env?.services?.action || this.action;
      if (actionSvc && actionSvc.doAction) {
        actionSvc.doAction(action);
      } else if (this.trigger) {
        this.trigger("do-action", action);
      } else {
        console.warn("No action service available to open Delivered action", action);
      }
    };

    openPartialDelivered = () => {
      const action = {
        type: "ir.actions.act_window",
        name: "Partial Delivered",
        res_model: "delivery.check",
        view_mode: "tree,form",
        views: [[false, "tree"], [false, "form"]],
        domain: [
          ['delivery_entry_types', '=', 'automatic'],
          ['overall_remaining_bales', '>=', 1],
          ['state', '=', 'delivery']
        ],
        target: "current",
      };

      const actionSvc = this.env?.services?.action || this.action;
      if (actionSvc && actionSvc.doAction) {
        actionSvc.doAction(action);
      } else if (this.trigger) {
        this.trigger("do-action", action);
      } else {
        console.warn("No action service available to open Partial Delivered action", action);
      }
    };

    // helper to dispatch the action (modern service with fallback)
    _doAction = (action) => {
      const actionSvc = this.env?.services?.action || this.action;
      if (actionSvc && actionSvc.doAction) {
        return actionSvc.doAction(action);
      } else if (this.trigger) {
        return this.trigger("do-action", action);
      } else {
        console.warn("No action service available", action);
        return Promise.resolve();
      }
    };

    // Delivered: matches get_status_delivered (automatic + state = 'delivery')
    openStatusDelivered = () => {
      const action = {
        type: "ir.actions.act_window",
        name: "Delivered checks",
        res_model: "delivery.check",
        view_mode: "tree,form",
        views: [[false, "tree"], [false, "form"]],
        domain: [
          ['delivery_entry_types', '=', 'automatic'],
          ['state', '=', 'delivery'],
        ],
        target: "current",
      };
      this._doAction(action);
    };

    // In Transit: matches get_status_transit_delayed in_transit (automatic + state = 'draft')
    openStatusInTransit = () => {
      const action = {
        type: "ir.actions.act_window",
        name: "In Transit checks",
        res_model: "delivery.check",
        view_mode: "tree,form",
        views: [[false, "tree"], [false, "form"]],
        domain: [
          ['delivery_entry_types', '=', 'automatic'],
          ['state', '=', 'draft'],
        ],
        target: "current",
      };
      this._doAction(action);
    };

    // Delayed: matches get_status_transit_delayed delayed
    // Uses today's date (YYYY-MM-DD) computed client-side to match ('logistic_date', '>', today)
    openStatusDelayed = () => {
      // compute today's date in YYYY-MM-DD
      const today = new Date();
      const yyyy = today.getFullYear();
      const mm = String(today.getMonth() + 1).padStart(2, '0');
      const dd = String(today.getDate()).padStart(2, '0');
      const todayStr = `${yyyy}-${mm}-${dd}`;

      const action = {
        type: "ir.actions.act_window",
        name: "Delayed checks",
        res_model: "delivery.check",
        view_mode: "tree,form",
        views: [[false, "tree"], [false, "form"]],
        domain: [
          ['delivery_entry_types', '=', 'automatic'],
          ['state', '=', 'done'],
          ['logistic_date', '>', todayStr],
        ],
        target: "current",
      };
      this._doAction(action);
    };

    // Canceled: matches get_status_transit_delayed canceled
    openStatusCanceled = () => {
      const action = {
        type: "ir.actions.act_window",
        name: "Canceled checks",
        res_model: "delivery.check",
        view_mode: "tree,form",
        views: [[false, "tree"], [false, "form"]],
        domain: [
          ['delivery_entry_types', '=', 'automatic'],
          ['state', '=', 'cancel'],
        ],
        target: "current",
      };
      this._doAction(action);
    };

    // Draft (upcoming)
    openDraftToday = () => {
      const today = new Date();
      const y = today.getFullYear(), m = String(today.getMonth() + 1).padStart(2,'0'), d = String(today.getDate()).padStart(2,'0');
      const start = `${y}-${m}-${d} 00:00:00`, end = `${y}-${m}-${d} 23:59:59`;
      const domain = [
        ['delivery_entry_types', '=', 'automatic'],
        ['state', '=', 'draft'],
        ['logistic_date', '>=', start],
        ['logistic_date', '<=', end],
      ];
      this._doAction({
        type: 'ir.actions.act_window',
        name: 'Upcoming — Today',
        res_model: 'delivery.check',
        view_mode: 'tree,form',
        views: [[false,'tree'],[false,'form']],
        domain,
        target: 'current',
      });
    };

    openDraftWeek = () => {
      const today = new Date();
      const weekStart = new Date(); weekStart.setDate(today.getDate() - 6);
      const a = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')} 23:59:59`;
      const b = `${weekStart.getFullYear()}-${String(weekStart.getMonth()+1).padStart(2,'0')}-${String(weekStart.getDate()).padStart(2,'0')} 00:00:00`;
      const domain = [
        ['delivery_entry_types', '=', 'automatic'],
        ['state', '=', 'draft'],
        ['logistic_date', '>=', b],
        ['logistic_date', '<=', a],
      ];
      this._doAction({
        type: 'ir.actions.act_window',
        name: 'Upcoming — Week',
        res_model: 'delivery.check',
        view_mode: 'tree,form',
        views: [[false,'tree'],[false,'form']],
        domain,
        target: 'current',
      });
    };

    openDraftMonth = () => {
      const today = new Date();
      const monthStart = new Date(); monthStart.setDate(today.getDate() - 29);
      const a = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')} 23:59:59`;
      const b = `${monthStart.getFullYear()}-${String(monthStart.getMonth()+1).padStart(2,'0')}-${String(monthStart.getDate()).padStart(2,'0')} 00:00:00`;
      const domain = [
        ['delivery_entry_types', '=', 'automatic'],
        ['state', '=', 'draft'],
        ['logistic_date', '>=', b],
        ['logistic_date', '<=', a],
      ];
      this._doAction({
        type: 'ir.actions.act_window',
        name: 'Upcoming — Month',
        res_model: 'delivery.check',
        view_mode: 'tree,form',
        views: [[false,'tree'],[false,'form']],
        domain,
        target: 'current',
      });
    };

    // Done (delivered)
    openDoneToday = () => {
      const today = new Date();
      const y = today.getFullYear(), m = String(today.getMonth()+1).padStart(2,'0'), d = String(today.getDate()).padStart(2,'0');
      const start = `${y}-${m}-${d} 00:00:00`, end = `${y}-${m}-${d} 23:59:59`;
      const domain = [
        ['delivery_entry_types', '=', 'automatic'],
        ['state', 'in', ['delivered','delivery','done']],
        ['logistic_date', '>=', start],
        ['logistic_date', '<=', end],
      ];
      this._doAction({
        type: 'ir.actions.act_window',
        name: 'Delivered — Today',
        res_model: 'delivery.check',
        view_mode: 'tree,form',
        views: [[false,'tree'],[false,'form']],
        domain,
        target: 'current',
      });
    };

    openDoneWeek = () => {
      const today = new Date();
      const weekStart = new Date(); weekStart.setDate(today.getDate() - 6);
      const a = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')} 23:59:59`;
      const b = `${weekStart.getFullYear()}-${String(weekStart.getMonth()+1).padStart(2,'0')}-${String(weekStart.getDate()).padStart(2,'0')} 00:00:00`;
      const domain = [
        ['delivery_entry_types', '=', 'automatic'],
        ['state', 'in', ['delivered','delivery','done']],
        ['logistic_date', '>=', b],
        ['logistic_date', '<=', a],
      ];
      this._doAction({
        type: 'ir.actions.act_window',
        name: 'Delivered — Week',
        res_model: 'delivery.check',
        view_mode: 'tree,form',
        views: [[false,'tree'],[false,'form']],
        domain,
        target: 'current',
      });
    };

    openDoneMonth = () => {
      const today = new Date();
      const monthStart = new Date(); monthStart.setDate(today.getDate() - 29);
      const a = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')} 23:59:59`;
      const b = `${monthStart.getFullYear()}-${String(monthStart.getMonth()+1).padStart(2,'0')}-${String(monthStart.getDate()).padStart(2,'0')} 00:00:00`;
      const domain = [
        ['delivery_entry_types', '=', 'automatic'],
        ['state', 'in', ['delivered','delivery','done']],
        ['logistic_date', '>=', b],
        ['logistic_date', '<=', a],
      ];
      this._doAction({
        type: 'ir.actions.act_window',
        name: 'Delivered — Month',
        res_model: 'delivery.check',
        view_mode: 'tree,form',
        views: [[false,'tree'],[false,'form']],
        domain,
        target: 'current',
      });
    };

    openTopProduct = (categoryKey) => {
      if (!categoryKey) {
        this.notification?.add?.("No product category selected.", { type: "warning" });
        return;
      }

      // Simple, robust domain: match the parsed category text inside item_details (case-insensitive)
      const domain = [['item_details', 'ilike', categoryKey]];

      // Optionally: if you want to restrict to delivered entries only, add:
      // domain.push(['state', 'in', ['delivered','delivery','done']]);

      const action = {
        type: 'ir.actions.act_window',
        name: `Products: ${categoryKey}`,
        res_model: 'delivery.check',
        view_mode: 'tree,form',
        views: [[false, 'tree'], [false, 'form']],
        domain,
        target: 'current',
      };

      // call your existing helper
      this._doAction(action);
    };

    openTotalZones = () => {
      const summary = this.state.unopenedZoneSummary || {};
      // preferred: use the server-provided mapping placement_id -> [lr ids]
      const zoneMap = summary.zone_lr_ids || summary.zone_lr_ids === null ? summary.zone_lr_ids : null;

      let zoneIds = [];
      if (zoneMap && typeof zoneMap === 'object') {
        // keys may be strings or numbers — normalize to numbers and filter falsy
        zoneIds = Object.keys(zoneMap).map(k => Number(k)).filter(Boolean);
      }

      // fallback: if server mapping missing, try the top_zones list
      if (!zoneIds.length) {
        const top = Array.isArray(summary.top_zones) ? summary.top_zones : [];
        zoneIds = top.map(z => Number(z.zone_id)).filter(Boolean);
      }

      // final fallback: open all placements if we still have nothing
      const domain = zoneIds.length ? [['id', 'in', zoneIds]] : [];

      const action = {
        type: 'ir.actions.act_window',
        name: 'Zones (Placements)',
        res_model: 'placement.master.data',
        view_mode: 'tree,form',
        views: [[false, 'tree'], [false, 'form']],
        domain,
        target: 'current',
      };
      return this._doAction ? this._doAction(action) : this._fallbackDoAction(action);
    };


    openTotalLrs = () => {
      const ids = (this.state.unopenedZoneSummary && this.state.unopenedZoneSummary.lr_ids) || [];
      if (!Array.isArray(ids) || !ids.length) {
        this.notification?.add?.("No LR ids available to open.", { type: "warning" });
        // fallback: open delivery.check with logistic_lr_number != False
        const fallback = {
          type: 'ir.actions.act_window',
          name: 'LRs (All)',
          res_model: 'delivery.check',
          view_mode: 'tree,form',
          views: [[false, 'tree'], [false, 'form']],
          domain: [['logistic_lr_number', '!=', false]],
          target: 'current',
        };
        return this._doAction ? this._doAction(fallback) : this._fallbackDoAction(fallback);
      }
      const action = {
        type: 'ir.actions.act_window',
        name: 'Summary LRs',
        res_model: 'delivery.check',
        view_mode: 'tree,form',
        views: [[false, 'tree'], [false, 'form']],
        domain: [['id', 'in', ids]],
        target: 'current',
      };
      return this._doAction ? this._doAction(action) : this._fallbackDoAction(action);
    };

    openZone = (zoneId) => {
      if (!zoneId) {
        this.notification?.add?.("No zone selected.", { type: "warning" });
        return;
      }
      const map = (this.state.unopenedZoneSummary && this.state.unopenedZoneSummary.zone_lr_ids) || {};
      // server keys may be numbers or strings
      const ids = map[zoneId] || map[String(zoneId)] || [];
      if (Array.isArray(ids) && ids.length) {
        const action = {
          type: 'ir.actions.act_window',
          name: `LRs — Zone ${zoneId}`,
          res_model: 'delivery.check',
          view_mode: 'tree,form',
          views: [[false, 'tree'], [false, 'form']],
          domain: [['id', 'in', ids]],
          target: 'current',
        };
        return this._doAction ? this._doAction(action) : this._fallbackDoAction(action);
      }
      // fallback domain if server mapping missing
      const fallback = {
        type: 'ir.actions.act_window',
        name: `LRs — Zone ${zoneId}`,
        res_model: 'delivery.check',
        view_mode: 'tree,form',
        views: [[false, 'tree'], [false, 'form']],
        domain: [['placements', '=', Number(zoneId)], ['logistic_lr_number', '!=', false]],
        target: 'current',
      };
      return this._doAction ? this._doAction(fallback) : this._fallbackDoAction(fallback);
    };




    openDivisionDeliveries = (divisionName) => {
      if (!divisionName) {
        this.notification?.add?.("No division selected.", { type: "warning" });
        return;
      }

      // Try exact ids returned by server first (recommended)
      const map = (this.state.unopenedDivision && this.state.unopenedDivision.division_delivery_ids) || {};
      const ids = map[divisionName] || map[String(divisionName)] || [];

      let action;
      if (Array.isArray(ids) && ids.length) {
        action = {
          type: 'ir.actions.act_window',
          name: `Deliveries — ${divisionName}`,
          res_model: 'delivery.check',
          view_mode: 'tree,form',
          views: [[false, 'tree'], [false, 'form']],
          domain: [['id', 'in', ids]],
          target: 'current',
        };
      } else {
        // Fallback: simple ilike search on item_details so the click still shows relevant records
        action = {
          type: 'ir.actions.act_window',
          name: `Deliveries — ${divisionName}`,
          res_model: 'delivery.check',
          view_mode: 'tree,form',
          views: [[false, 'tree'], [false, 'form']],
          domain: [['item_details', 'ilike', divisionName]],
          target: 'current',
        };
      }

      this._doAction(action);
    };


    openUnopenedZone = (placementId) => {
      if (!placementId) {
        this.notification?.add?.("No zone selected.", { type: "warning" });
        return;
      }

      const map = (this.state.unopenedZone && this.state.unopenedZone.placement_lr_ids) || {};
      // server maps placement_id -> array of delivery ids
      const ids = map[placementId] || map[String(placementId)] || [];

      if (Array.isArray(ids) && ids.length) {
        // open the exact delivery.check ids used for the count
        const action = {
          type: 'ir.actions.act_window',
          name: `Unopened LRs — Zone ${placementId}`,
          res_model: 'delivery.check',
          view_mode: 'tree,form',
          views: [[false, 'tree'], [false, 'form']],
          domain: [['id', 'in', ids]],
          target: 'current',
        };
        return this._doAction ? this._doAction(action) : this._fallbackDoAction(action);
      }

      // fallback: open by placement domain (less precise)
      const domain = [
        ['placements', '=', Number(placementId)],
        ['state', '=', 'draft'],
        ['logistic_lr_number', '!=', false],
      ];
      const action = {
        type: 'ir.actions.act_window',
        name: `Unopened LRs — Zone ${placementId}`,
        res_model: 'delivery.check',
        view_mode: 'tree,form',
        views: [[false, 'tree'], [false, 'form']],
        domain,
        target: 'current',
      };
      return this._doAction ? this._doAction(action) : this._fallbackDoAction(action);
    };


    openAgent = () => {
      const ids = (this.state.roleSplitIds && this.state.roleSplitIds.agent) || [];
      if (Array.isArray(ids) && ids.length) {
        this._doAction({
          type: 'ir.actions.act_window',
          name: 'Agent - Records',
          res_model: 'logistic.screen.data',
          view_mode: 'tree,form',
          views: [[false,'tree'],[false,'form']],
          domain: [['id', 'in', ids]],
          target: 'current',
        });
        return;
      }
      // fallback domain (best-effort)
      this._doAction({
        type: 'ir.actions.act_window',
        name: 'Agent - Records',
        res_model: 'logistic.screen.data',
        view_mode: 'tree,form',
        views: [[false,'tree'],[false,'form']],
        domain: [['logistic_vendor', '!=', false]],
        target: 'current',
      });
    };

    openTransporter = () => {
      const ids = (this.state.roleSplitIds && this.state.roleSplitIds.transporter) || [];
      if (Array.isArray(ids) && ids.length) {
        this._doAction({
          type: 'ir.actions.act_window',
          name: 'Transporter - Records',
          res_model: 'logistic.screen.data',
          view_mode: 'tree,form',
          views: [[false,'tree'],[false,'form']],
          domain: [['id', 'in', ids]],
          target: 'current',
        });
        return;
      }
      // fallback domain matching server logic (transporter present and agent empty)
      this._doAction({
        type: 'ir.actions.act_window',
        name: 'Transporter - Records',
        res_model: 'logistic.screen.data',
        view_mode: 'tree,form',
        views: [[false,'tree'],[false,'form']],
        domain: [
          ['transporter', '!=', false],
          ['logistic_vendor', '=', false],
        ],
        target: 'current',
      });
    };

    openVendor = async () => {
      try {
        // 1) Try cached ids first (fast, exact if previously fetched)
        const cached = (this.state.roleSplitIds && Array.isArray(this.state.roleSplitIds.vendor)) ? this.state.roleSplitIds.vendor : [];
        let ids = Array.isArray(cached) ? cached.slice() : [];

        // 2) If no cached ids (or you want freshest data), ask server for exact vendor ids
        if (!ids.length) {
          try {
            const res = await this.orm.call('logistic.screen.data', 'get_vendor_ids', [], { kwargs: {} });
            ids = Array.isArray(res && res.vendor_ids) ? res.vendor_ids : [];
            // store in state for future clicks (optional)
            this.state.roleSplitIds = this.state.roleSplitIds || {};
            this.state.roleSplitIds.vendor = ids;
          } catch (rpcErr) {
            // log but continue to fallback domain below
            console.warn('get_vendor_ids RPC failed:', rpcErr);
          }
        }

        // 3) If we have exact ids -> open by ids (guaranteed match)
        if (Array.isArray(ids) && ids.length) {
          const action = {
            type: 'ir.actions.act_window',
            name: 'Vendor - Records',
            res_model: 'logistic.screen.data',
            view_mode: 'tree,form',
            views: [[false, 'tree'], [false, 'form']],
            domain: [['id', 'in', ids]],
            target: 'current',
          };
          return this._doAction ? this._doAction(action) : this._fallbackDoAction(action);
        }

        // 4) Fallback: best-effort domain that approximates server logic
        const fallbackAction = {
          type: 'ir.actions.act_window',
          name: 'Vendor - Records',
          res_model: 'logistic.screen.data',
          view_mode: 'tree,form',
          views: [[false, 'tree'], [false, 'form']],
          // vendor present OR none of the three present (approx)
          domain: [
            '|',
              ['vendor', '!=', false],
              '&',
                ['logistic_vendor', '=', false],
                '&',
                  ['transporter', '=', false],
                  ['vendor', '=', false],
          ],
          target: 'current',
        };
        return this._doAction ? this._doAction(fallbackAction) : this._fallbackDoAction(fallbackAction);

      } catch (err) {
        console.error("openVendor failed:", err);
        this.notification?.add?.("Unable to open Vendor records.", { type: "danger" });
      }
};



    // Optional fallback if you didn't keep this._doAction in the component
    _fallbackDoAction = (action) => {
      const svc = (this.env && this.env.services && this.env.services.action) || this.action;
      if (svc && svc.doAction) {
        return svc.doAction(action);
      } else if (this.trigger) {
        return this.trigger('do-action', action);
      } else {
        console.warn('No action service available', action);
        this.notification?.add?.("Cannot open records (no action service).", { type: "danger" });
      }
    };

    // Open parcels with state = 'done'
    openOpenParcels = () => {
      const action = {
        type: 'ir.actions.act_window',
        name: 'Open Parcels (done)',
        res_model: 'open.parcel',
        view_mode: 'tree,form',
        views: [[false, 'tree'], [false, 'form']],
        domain: [['state', '=', 'done']],
        target: 'current',
      };
      if (this._doAction) {
        this._doAction(action);
      } else {
        const svc = this.env?.services?.action || this.action;
        if (svc && svc.doAction) svc.doAction(action);
        else if (this.trigger) this.trigger('do-action', action);
        else this.notification?.add?.("Cannot open parcels (no action service).", { type: "danger" });
      }
    };

    // Open parcels with state = 'draft'
    openUnopenParcels = () => {
      const action = {
        type: 'ir.actions.act_window',
        name: 'Unopened Parcels (draft)',
        res_model: 'open.parcel',
        view_mode: 'tree,form',
        views: [[false, 'tree'], [false, 'form']],
        domain: [['state', '=', 'draft']],
        target: 'current',
      };
      if (this._doAction) {
        this._doAction(action);
      } else {
        const svc = this.env?.services?.action || this.action;
        if (svc && svc.doAction) svc.doAction(action);
        else if (this.trigger) this.trigger('do-action', action);
        else this.notification?.add?.("Cannot open parcels (no action service).", { type: "danger" });
      }
    };

    // Open deliveries for a single division using exact ids returned by server
    openDivisionDeliveries = (divisionName) => {
      if (!divisionName) {
        this.notification?.add?.("No division selected.", { type: "warning" });
        return;
      }
      const map = (this.state.unopenedDivisionBales && this.state.unopenedDivisionBales.division_delivery_ids) || {};
      const ids = map[divisionName] || map[String(divisionName)] || [];

      // If server returned exact ids, open by id in — guaranteed to match numbers.
      if (Array.isArray(ids) && ids.length) {
        const action = {
          type: 'ir.actions.act_window',
          name: `Deliveries — ${divisionName}`,
          res_model: 'delivery.check',
          view_mode: 'tree,form',
          views: [[false, 'tree'], [false, 'form']],
          domain: [['id', 'in', ids]],
          target: 'current',
        };
        this._doAction ? this._doAction(action) : this._fallbackDoAction(action);
        return;
      }

      // Fallback: text search on item_details (works if server didn't return ids)
      const action = {
        type: 'ir.actions.act_window',
        name: `Deliveries — ${divisionName}`,
        res_model: 'delivery.check',
        view_mode: 'tree,form',
        views: [[false, 'tree'], [false, 'form']],
        domain: [['item_details', 'ilike', divisionName]],
        target: 'current',
      };
      this._doAction ? this._doAction(action) : this._fallbackDoAction(action);
    };

    // Open the union of all delivery ids used to compute the division totals
    openTotalDivisionDeliveries = () => {
      const ids = (this.state.unopenedDivisionBales && this.state.unopenedDivisionBales.delivery_ids) || [];
      if (!Array.isArray(ids) || !ids.length) {
        this.notification?.add?.("No deliveries found for totals.", { type: "warning" });
        return;
      }
      const action = {
        type: 'ir.actions.act_window',
        name: 'Division — Deliveries (All)',
        res_model: 'delivery.check',
        view_mode: 'tree,form',
        views: [[false, 'tree'], [false, 'form']],
        domain: [['id', 'in', ids],['logistic_entry_types', '=', 'manual']],
        target: 'current',
      };
      this._doAction ? this._doAction(action) : this._fallbackDoAction(action);
    };

    // Optional fallback if you don't have this._doAction
    _fallbackDoAction = (action) => {
      const svc = (this.env && this.env.services && this.env.services.action) || this.action;
      if (svc && svc.doAction) {
        return svc.doAction(action);
      } else if (this.trigger) {
        return this.trigger('do-action', action);
      } else {
        console.warn('No action service available', action);
        this.notification?.add?.("Cannot open records (no action service).", { type: "danger" });
      }
    };


}

LogisticDashboard.template = "cmr_customizations.LogisticDashboard";
actionRegistry.add("cmr_dashboard_tag", LogisticDashboard);
