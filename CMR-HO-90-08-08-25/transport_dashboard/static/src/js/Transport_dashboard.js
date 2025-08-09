/** @odoo-module */
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";
const { Component , useState } = owl;

export class OwlTransportDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");

        this.menuItems = [
            { id: 1, label: "Transfer", mainParent: "Stock In Transit", subParent: "Sites" },
            { id: 2, label: "Return", mainParent: "Stock In Transit", subParent: "Sites" },
            { id: 3, label: "Transfer", mainParent: "Stock In Transit", subParent: "LR Number" },
            { id: 4, label: "Return", mainParent: "Stock In Transit", subParent: "LR Number" },
        ];

        this.state = useState({
            selected: 1,
            lastMainParent: '',
            lastSubParent: '',
        });

        this.getTypeFromSelected = () => {
            const typeMap = Object.fromEntries(this.menuItems.map(item => [item.id, item.label]));
            return typeMap[this.state.selected] || '';
        };

        this.selectMenu = this.selectMenu.bind(this);
    }
    selectMenu(id) {
        this.state.selected = id;
    }
}
OwlTransportDashboard.template = "owl.OwlTransportDashboard";
registry.category("actions").add("owl.transport_dashboard", OwlTransportDashboard);