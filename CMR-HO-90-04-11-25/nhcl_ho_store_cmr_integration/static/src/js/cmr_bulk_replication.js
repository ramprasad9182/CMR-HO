/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart } from "@odoo/owl";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { patch } from "@web/core/utils/patch";

class BulkReplicationAction extends Component {
    setup() {
        this.action = useService("action"); // Odoo action service
        this.orm = useService("orm"); // Odoo ORM service

        // State to store available models and the selected model ID
        this.state = useState({

            models: [],
            selectedModelId: null,
            pending: {
                account: 'Loading...',
                tax: 'Loading...',
                fiscal: 'Loading...',
                partner: 'Loading...',
                employee: 'Loading...',
                template: 'Loading...',
                category: 'Loading...',
                product: 'Loading...',
                users: 'Loading...',
                attribute: 'Loading...',
                loyalty: 'Loading...',
            }
        });

        this._fetchData();
        // Fetch models from `ir.model` on component load
        onWillStart(async () => {
            try {
                const domain = [['model', 'in', ['account.account','res.partner', 'product.product', 'product.template', 'product.category',
                'product.attribute','hr.employee','account.tax','res.users','loyalty.program','account.fiscal.year']]];
                const models = await this.orm.searchRead("ir.model", domain, ["name", "id"]);
                this.state.models = models || [];
            } catch (error) {
                console.log("Failed to fetch models:", error);
                this.state.models = []; // Fallback to an empty array if there's an error
            }
        });

    }

    // Store the selected model ID when user selects a model
    onModelSelect(event) {
        this.state.selectedModelId = event.target.value || null;
    }

    // Trigger action to open records of the selected model
    async getRecords() {
        if (!this.state.selectedModelId) return; // Check if a model is selected

        try {
            // Fetch selected model details
            const records = await this.orm.searchRead("ir.model",[["id", "=", this.state.selectedModelId]],["model", "name"]);

            if (records.length) {
                const model = records[0].model;
                const name = records[0].name;

                // Fetch the view ID for the model (tree view is commonly used)
                const viewId = await this.orm.searchRead(
                    "ir.ui.view",
                    [["model", "=", model], ["type", "=", "tree"]],
                    ["id"]
                );

                const view = viewId.length ? viewId[0].id : false; // Default to `false` if no view is found

                // Open the selected model's records in a tree view
                await this.action.doAction({
                    name: name,
                    type: "ir.actions.act_window",
                    target: "current",
                    res_model: model,
                    view_mode: "tree",
                    views: [[view, "tree"]],
                    context: { create: false, delete: false, duplicate: false, edit: false },
                    domain : [['update_replication', '=', false]]
                });
            } else {
                console.warn("No records found for the selected model.");
            }
        } catch (error) {
            console.error("Failed to execute action:", error);
        }
    }

   async _fetchData() {
    try {
        const [AccountInfo, TaxInfo, FiscalYearInfo, ContactInfo, EmployeeInfo, ProductTemplateInfo, ProductCategoryInfo,
            ProductVariantInfo, UsersInfo, ProductAttributeInfo, PromotionInfo] = await Promise.all([
                this.orm.call("account.account", "get_pending_account", {}),
                this.orm.call("account.tax", "get_pending_tax", {}),
                this.orm.call("account.fiscal.year", "get_pending_fiscal", {}),
                this.orm.call("res.partner", "get_pending_partner", {}),
                this.orm.call("hr.employee", "get_pending_employee", {}),
                this.orm.call("product.template", "get_pending_template", {}),
                this.orm.call("product.category", "get_pending_category", {}),
                this.orm.call("product.product", "get_pending_product", {}),
                this.orm.call("res.users", "get_pending_users", {}),
                this.orm.call("product.attribute", "get_pending_attribute", {}),
                this.orm.call("loyalty.program", "get_pending_loyalty", {})
        ]);
        // Update the state with the fetched data
        this.state.pending.account = AccountInfo.pending_account;
        this.state.pending.tax = TaxInfo.pending_tax;
        this.state.pending.fiscal = FiscalYearInfo.pending_fiscal;
        this.state.pending.partner = ContactInfo.pending_partner;
        this.state.pending.employee = EmployeeInfo.pending_employee;
        this.state.pending.template = ProductTemplateInfo.pending_template;
        this.state.pending.category = ProductCategoryInfo.pending_category;
        this.state.pending.product = ProductVariantInfo.pending_product;
        this.state.pending.users = UsersInfo.pending_users;
        this.state.pending.attribute = ProductAttributeInfo.pending_attribute;
        this.state.pending.loyalty = PromotionInfo.pending_loyalty;
    } catch (error) {
        console.error("Error fetching data", error);
    }
    }
}

BulkReplicationAction.template = "nhcl_ho_store_cmr_integration.BulkReplication";
registry.category("actions").add("bulk_replication_action", BulkReplicationAction);
