/** @odoo-module */
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";
import { MultiSelect } from "./multiselect";

const { Component, useState } = owl;

export class OwlLRDashboard extends Component {
    static components = { MultiSelect };
    // --- helpers (add as class methods) ---
    _flatIds(list) {
      const arr = Array.isArray(list) ? list : [];
      const out = [];
      for (const x of arr) {
        let v = typeof x === "object" ? (x.id ?? x.value ?? x.res_id) : x;
        v = Number(v);
        if (Number.isFinite(v) && v > 0) out.push(v);
      }
      return [...new Set(out)];
    }
    _normAllCompanies(list) {
      // 0 = All → send [] to backend (means all non-main issuers)
      const arr = Array.isArray(list) ? list : [];
      if (arr.includes(0)) return [];
      return this._flatIds(arr);
    }
    _tokensFromMulti(val) {
      // LR values are strings; [] means "All LRs"
      const arr = Array.isArray(val) ? val : [];
      const out = [];
      for (const x of arr) {
        let s = x && typeof x === "object" ? (x.name ?? x.value ?? x.id) : x;
        if (s === 0 || s === "0" || s === null || s === undefined) continue; // ignore a 0 sentinel if present
        s = String(s ?? "").trim();
        if (s) out.push(s);
      }
      return [...new Set(out)];
    }

    _normalizeCompaniesForAll(val) {
      // keep 0=All for companies; [] -> backend treats as "all non-main"
      const arr = Array.isArray(val) ? val : [];
      const nums = [];
      for (const x of arr) {
        let v = x && typeof x === "object" ? (x.id ?? x.value) : x;
        v = Number(v);
        if (Number.isFinite(v)) nums.push(v);
      }
      const positives = nums.filter((n) => n > 0);
      return positives.length ? [...new Set(positives)] : [];
    }

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.menuItems = [
            { id: 1, label: "Transfer", mainParent: "Stock In Transit", subParent: "LR Number" },
            { id: 2, label: "Return", mainParent: "Stock In Transit", subParent: "LR Number" },
        ];
        // 1) defaults in state
        this.state = useState({
          selected: 1,
          selectedCompanyIds: [0],
          LrNumbersIds: [0],
          companyOptions: [],
          LrNumbersOptions: [],
          loading: true,
          selectedPeriod:90,
         // Return LR (separate!)
          LrReturn: [],
          TotalLrReturn: 0,
          TotalDeliveryReturn: 0,
          loadingReturn: false,
            // Return filters (separate!)
          rCompanyIds: [0],   // 0 = All (backend: all non-main issuers)
          rLrNumbers: [0],     // strings or {name}
          rPeriod: 90,

        });
        // If you want to be extra-safe with binding:
        this.onPeriodChange = this.onPeriodChange.bind(this);
        this.selectMenu = (id) => {
            this.state.selected = id;
        };
        onWillStart(async () => {
            await this._loadFilterOptions();
            await Promise.all([this.lrSummary(),this.lrReturnSummary()]);
        });
    }

    //  load filters
    async _loadFilterOptions() {
      try {
        // LR list (distinct strings)
        const lrRes = await this.orm.call("stock.picking", "get_lr_numbers", [], {});
        const lrOpts = lrRes?.lr_numbers || []; // [{id: "LR-001", name: "LR-001"}]
        this.state.LrNumbersOptions = lrOpts;
        this.state.LrNumbersIds = [];  // empty = All

        // Companies (you can keep your existing call)
        const compRes = await this.orm.call("res.company", "get_company_list", [], {});
        const compRows = compRes?.company_list || compRes?.companies || [];
        this.state.companyOptions = [{ id: 0, name: "All Companies" }, ...compRows];
        this.state.selectedCompanyIds = [];
      } catch (e) {
        console.error("Error fetching filters:", e);
        this.state.LrNumbersOptions = []; // empty means “All” is allowed
        this.state.companyOptions = [{ id: 0, name: "All Companies" }];
      }
    }

    // Transfer
    async lrSummary() {
      this.state.loading = true;
      try {
        const company_ids = this._normalizeCompaniesForAll(this.state.selectedCompanyIds); // [] => All non-main
        const lr_numbers  = this._tokensFromMulti(this.state.LrNumbersIds);               // [] => All LRs
        const period_days = this.state.selectedPeriod || false;
        const res = await this.orm.call("stock.picking", "transfer_LR_dashboard_summary", [{
          company_ids,
          lr_numbers,    // <-- correct key the backend expects
          period_days,
        }]);

        this.state.totalLrDelivery = res?.total_deliveries || 0;
        this.state.TotalLrTransfer = res?.total_categories || 0;
        this.state.LrTransfer      = Array.isArray(res?.rows) ? res.rows : [];
      } catch (e) {
        console.error("lrSummary failed:", e);
        this.state.totalLrDelivery = 0;
        this.state.TotalLrTransfer = 0;
        this.state.LrTransfer = [];
      } finally {
        this.state.loading = false;
      }
    }
    async onPeriodChange(ev) {
        const raw = ev?.target?.value;
        const n = Number(raw);
        this.state.selectedPeriod = Number.isFinite(n) && n > 0 ? n : null;
        await Promise.all([this.lrSummary()]);
    }
    async onLrNumbersChange(vals) {
      this.state.LrNumbersIds = vals;   // strings array or objects with {id/name}
      await this.lrSummary();
    }
    async onCompaniesChange(ids) {
      this.state.selectedCompanyIds = ids.includes(0) ? [0] : ids;
      await Promise.all([this.lrSummary()]);
    }
    // RETURN
    async lrReturnSummary() {
      this.state.loadingReturn = true;
      try {
        const company_ids = this._normAllCompanies(this.state.rCompanyIds);
        const lr_numbers  = this._tokensFromMulti(this.state.rLrNumbers);
        const period_days = this.state.selectedPeriod || false;
        const res = await this.orm.call( "stock.picking","LR_return_dashboard_summary", [{
         company_ids,
         lr_numbers,
         period_days,
        }]);
        this.state.TotalDeliveryReturn = res?.total_deliveries || 0;
        this.state.TotalLrReturn       = res?.total_categories || 0;
        this.state.LrReturn            = Array.isArray(res?.rows) ? res.rows : [];
      } catch (e) {
        console.error("lrReturnSummary failed:", e);
        this.state.TotalDeliveryReturn = 0;
        this.state.TotalLrReturn       = 0;
        this.state.LrReturn            = [];
      } finally {
        this.state.loadingReturn = false;
      }
    }

    async onCompaniesReturnChange(ids) {
      this.state.rCompanyIds = ids;
      await this.lrReturnSummary();
    }
    async onLrNumbersReturnChange(vals) {
      this.state.rLrNumbers = vals || [];
      await this.lrReturnSummary();
    }
    async onReturnPeriodChange(ev) {
      const n = Number(ev?.target?.value);
      this.state.rPeriod = Number.isFinite(n) && n > 0 ? n : null;
      await this.lrReturnSummary();
    }

}


OwlLRDashboard.template = "owl.OwlLRDashboard";
registry.category("actions").add("owl.lr_dashboard", OwlLRDashboard);
