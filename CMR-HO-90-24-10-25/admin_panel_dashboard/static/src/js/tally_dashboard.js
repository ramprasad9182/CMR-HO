/** @odoo-module */

import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc_service";

const  { Component, useState, onWillStart } = owl;

export class TallyDashboard extends Component {
   setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.rpc = useService("rpc");
        this.menuItems = [
          { id: 1, label: "Accounts", parent: "Master Data From Odoo to Tally" },
          { id: 2, label: "Companies", parent: "Master Data From Odoo to Tally" },
          { id: 3, label: "Contacts", parent: "Master Data From Odoo to Tally" },
          { id: 4, label: "Journal Entries", parent: "Transactions Data From Odoo to Tally" },
        ];
        this.state = useState({
            selected: 1,
            lastParent: '',
            today:0,
            models: [],
            journal:{
                pending:"",
                approved:'Loading..',
                total:"",
            },
            account:{
                pending:"",
                approved:'Loading..',
                total:"",
            },
             company:{
                pending:"",
                approved:'Loading..',
                total:"",
            },
            customer:{
                pending:"",
                approved:'Loading..',
                total:"",
            },
            vendor:{
                pending:"",
                approved:'Loading..',
                total:"",
            },
            group:{
                pending:"",
                approved:'Loading..',
                total:"",
            }
        });
        this.selectMenu = (id) => {
            this.state.selected = id;
        };
        this._fetchData();
        onWillStart(async () => {
            try {
                const domain = [['model', 'in', ['account.move','account.account','res.partner','account.group','res.company']]];
                const models = await this.orm.searchRead("ir.model", domain, ["name", "id"]);
            } catch (error) {
                console.error("Failed to fetch models:", error);
            }
        });
    }
   async _fetchData() {
        try {
            const [Total, Approved , Pending, TotalAccount, ApprovedAccount,PendingAccount, TotalGroup,ApprovedGroup,PendingGroup,TotalCustomer,ApprovedCustomer,PendingCustomer,TotalVendor,ApprovedVendor,PendingVendor,TotalComp,ApprovedComp,PendingComp] = await Promise.all([
                this.orm.call("account.move", "getting_moves_in_dashboard", {}),
                this.orm.call("account.move", "getting_moves_in_dashboard", {}),
                this.orm.call("account.move", "getting_moves_in_dashboard", {}),
                this.orm.call("account.account", "getting_accounts_in_dashboard", {}),
                this.orm.call("account.account", "getting_accounts_in_dashboard", {}),
                this.orm.call("account.account", "getting_accounts_in_dashboard", {}),
                this.orm.call("account.group", "getting_groups_in_dashboard", {}),
                this.orm.call("account.group", "getting_groups_in_dashboard", {}),
                this.orm.call("account.group", "getting_groups_in_dashboard", {}),
                this.orm.call("res.partner", "getting_customers_in_dashboard", {}),
                this.orm.call("res.partner", "getting_customers_in_dashboard", {}),
                this.orm.call("res.partner", "getting_customers_in_dashboard", {}),
                this.orm.call("res.partner", "getting_vendors_in_dashboard", {}),
                this.orm.call("res.partner", "getting_vendors_in_dashboard", {}),
                this.orm.call("res.partner", "getting_vendors_in_dashboard", {}),
                this.orm.call("res.company", "getting_companies_in_dashboard", {}),
                this.orm.call("res.company", "getting_companies_in_dashboard", {}),
                this.orm.call("res.company", "getting_companies_in_dashboard", {}),
             ]);
            // Update the state with the fetched data
            this.state.journal.pending = Pending.pending_records;
            this.state.journal.approved = Approved.processed_records ;
            this.state.journal.total = Total.total_records;
            this.state.account.total = TotalAccount.total_accounts;
            this.state.account.approved = ApprovedAccount.processed_accounts;
            this.state.account.pending = PendingAccount.pending_accounts;
            this.state.group.total = TotalGroup.total_groups;
            this.state.group.approved = ApprovedGroup.processed_groups;
            this.state.group.pending = PendingGroup.pending_groups;
            this.state.customer.total = TotalCustomer.total_customers;
            this.state.customer.approved = ApprovedCustomer.processed_customers;
            this.state.customer.pending = PendingCustomer.pending_customers;
            this.state.vendor.total = TotalVendor.total_vendors;
            this.state.vendor.approved = ApprovedVendor.processed_vendors;
            this.state.vendor.pending = PendingVendor.pending_vendors;
            this.state.company.total = PendingComp.pending_companies;
            this.state.company.approved = ApprovedComp.processed_companies;
            this.state.company.pending = PendingComp.pending_companies;

        }
        catch (error) {
            console.error("Error fetching data", error);
        }
   }
}
TallyDashboard.template = "tally_dashboard";
registry.category("actions").add("admin_dashboard_actions", TallyDashboard);