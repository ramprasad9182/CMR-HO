/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

class StockReportAction extends Component {
    setup() {
        this.orm = useService("orm");

        this.state = useState({
            incoming: [],
        });

        onWillStart(async () => {
            const result = await this.orm.call(
                "stock.picking",
                "get_stock_report_by_company",
                []
            );
            this.state.incoming = result.incoming;
            await this.loadData();

        });

    }


    async loadData() {
        const data = await this.orm.call(
            "stock.picking",
            "get_stock_report_by_company",
            []
        );

        // SAFETY: always ensure array
        this.state.incoming = Array.isArray(data) ? data : [];
    }

}

StockReportAction.template = "cmr_customizations.StockReportTemplate";

registry.category("actions").add("stock_report_action", StockReportAction);
