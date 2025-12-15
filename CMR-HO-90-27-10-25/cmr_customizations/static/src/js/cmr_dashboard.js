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
          "logistic.screen.data",        // server model
          "get_zone_summary_and_top5",   // server method
          [5],                           // top_n
          { kwargs: filters }
        );

        // res is expected to be an object:
        // { total_zones: int, total_lrs: int, top_zones: [{zone_id,zone_name,zone_count}, ...] }
        if (res && typeof res === 'object' && !Array.isArray(res)) {
          // normalize to ensure shape
          const total_zones = Number(res.total_zones || 0);
          const total_lrs = Number(res.total_lrs || 0);
          const top_zones = Array.isArray(res.top_zones) ? res.top_zones : [];
          this.state.unopenedZoneSummary = { total_zones, total_lrs, top_zones };
        } else {
          // fallback safe empty shape
          this.state.unopenedZoneSummary = { total_zones: 0, total_lrs: 0, top_zones: [] };
        }

      } catch (e) {
        console.error("Unopened Zone Summary fetch failed:", e);
        this.notification.add("Failed to load unopened zone summary.", { type: "danger" });
        this.state.unopenedZoneSummary = { total_zones: 0, total_lrs: 0, top_zones: [] };
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
          "logistic.screen.data",        // model name where we added the server method
          "get_divisionwise_bale_totals",    // method name we just wrote
          [5],                           // top N zones
          { kwargs: filters }
        );
        const items = Array.isArray(res) ? res : [];
        this.state.unopenedDivisionBales = { total: items.length, items };
      } catch (e) {
        console.error("Unopened division bales fetch failed:", e);
        this.notification.add("Failed to load unopened division bales counts.", { type: "danger" });
        this.state.unopenedDivisionBales = { total: 0, items: [] };
      } finally {
        this.state.loadingUnopenedDivisionBales = false;
      }
    }
    async fetchUnopenedZones(filters = {}) {
      try {
        this.state.loadingUnopenedZone = true;

        const res = await this.orm.call(
          "logistic.screen.data",        // model name where we added the server method
          "get_unopened_zone_counts",    // method name we just wrote
          [5],                           // top N zones
          { kwargs: filters }
        );

        const items = Array.isArray(res) ? res : [];
        this.state.unopenedZone = { total: items.length, items };

      } catch (e) {
        console.error("Unopened Zone fetch failed:", e);
        this.notification.add("Failed to load unopened zone counts.", { type: "danger" });
        this.state.unopenedZone = { total: 0, items: [] };
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
}

LogisticDashboard.template = "cmr_customizations.LogisticDashboard";
actionRegistry.add("cmr_dashboard_tag", LogisticDashboard);
