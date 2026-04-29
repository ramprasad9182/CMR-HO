/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, useState } = owl;

export class SaleComparison extends Component {

    setup() {
        this.orm = useService("orm");
        const currentYear = new Date().getFullYear();
        this.state = useState({
            filters: {
                year: currentYear,
                quarter: null,
                month: null,
            },
            headers: {
                current: String(currentYear),
                previous: String(currentYear - 1),
                delta: "Δ",
            },
            rows: [],
            loading: false,
        });
        onWillStart(async () => {
            this.updateHeaders();
            await this.fetchData();
        });
    }

    onPeriodChange(ev) {
        const value = ev.target.value;

        this.state.filters.quarter = null;
        this.state.filters.month = null;

        if (value && value.startsWith("Q")) {
            this.state.filters.quarter = value;
        } else if (value) {
            this.state.filters.month = parseInt(value);
        }

        this.updateHeaders();
        this.fetchData();
    }
    onYearChange(ev) {
        const year = parseInt(ev.target.value);
        if (!year) return;

        this.state.filters.year = year;
        this.updateHeaders();
        this.fetchData();
    }
    updateHeaders() {
        const { year, quarter, month } = this.state.filters;

        if (quarter) {
            this.state.headers.current = `${quarter}/${year}`;
            this.state.headers.previous = `${quarter}/${year - 1}`;
        } else if (month) {
            const m = new Date(year, month - 1)
                .toLocaleString("en", { month: "short" });
            this.state.headers.current = `${m}/${year}`;
            this.state.headers.previous = `${m}/${year - 1}`;
        } else {
            this.state.headers.current = String(year);
            this.state.headers.previous = String(year - 1);
        }
    }

    async fetchData() {
        this.state.loading = true;
        const { year, quarter, month } = this.state.filters;
        const result = await this.orm.call(
            "account.move",
            "get_company_sales_comparison",
            [],
            { year, quarter, month }
        );
        this.state.rows = result || [];
        this.state.loading = false;
    }
}

registry.category("actions").add("cmr_sale_comparison_tag", SaleComparison);
SaleComparison.template = "cmr_customizations.SaleComparison";
