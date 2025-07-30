/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart  } from "@odoo/owl";

class BulkTrackingAction extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        // State to store available models and the selected model ID
        this.state = useState({
            models: [],
            failureView: 0,
            pending: {
                account:'',
                tax:'',
                fiscal: '',
                partner: '',
                employee: '',
                template: '',
                category: '',
                product: '',
                users: '',
                attribute: '',
                loyalty: ''
            },
            total: {
                account:'',
                tax: '',
                fiscal: '',
                partner: '',
                employee: '',
                template: '',
                category: '',
                product: '',
                users: '',
                attribute: '',
                loyalty: '',
                liveStore: 'Loading...',
                liveSync: 'Loading...',
                processedEvent: 'Loading...',
                processedToday: 'Loading...',
                transactionEvent:'Loading...',
                transactionToday:'Loading...'
            },
            processed: {
                account: 'Loading...',
                tax: 'Loading...',
                fiscal: 'Loading...',
                partner:'Loading...',
                employee:'Loading...',
                template: 'Loading...',
                category: 'Loading...',
                product: 'Loading...',
                users: 'Loading...',
                attribute: 'Loading...',
                loyalty: 'Loading...'
            },
        });
        this._fetchData();
        // Fetch models from `ir.model` on component load
        onWillStart(async () => {
            try {
                this.isLoading = true;  // Start loading state
                let result = await rpc("/web/action/load", { action_id: action.actionId });
                this.isLoading = false; // End loading state

                const domain = [['model', 'in', ['account.account','res.partner', 'product.product', 'product.template', 'product.category',
                'product.attribute','hr.employee','account.tax','res.users','loyalty.program','account.fiscal.year','nhcl.ho.store.master', 'nhcl.old.store.replication.log','nhcl.transaction.replication.log']]];
                const models = await this.orm.searchRead("ir.model", domain, ["name", "id"]);
                this.state.models = models || [];
            } catch (error) {
                console.error("Failed to fetch models:", error);
                this.state.models = []; // Fallback to an empty array if there's an error
            }
        });
    }
    // failure views
    viewAccountFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Account Failure",
            res_model: "account.account",
            domain: [['update_replication','=',false]],
            views: [[false, 'list'], [false, 'form'], [false, 'search']],
            context: {"search_default_landlord":1,
                        "create": false},
        })
    }
    viewTaxFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Tax Failure",
            res_model: "account.tax",
            domain: [['update_replication','=',false]],
            views: [[false, 'list'], [false, 'form'], [false, 'search']],
            context: {"search_default_landlord":1,
                        "create": false},
        })
    }
    viewFiscalFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Fiscal Year Failure",
            res_model: "account.fiscal.year",
            domain: [['update_replication','=',false]],
            views: [[false, 'list'], [false, 'form'], [false, 'search']],
            context: {"search_default_landlord":1,
                        "create": false},
        })
    }
    viewEmployeeFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Employee Failure",
            res_model: "hr.employee",
            domain: [['update_replication','=',false]],
            views: [[false, 'list'], [false, 'form'], [false, 'search']],
            context: {"search_default_landlord":1,
                        "create": false},
        })
    }
    viewTemplateFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Product Template Failure",
            res_model: "product.template",
            domain: [['update_replication','=',false]],
            views: [[false, 'list'], [false, 'form'], [false, 'search']],
            context: {"search_default_landlord":1,
                        "create": false},
        })
    }viewCategoryFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Product Category Failure",
            res_model: "product.category",
            domain: [['update_replication','=',false]],
            views: [[false, 'list'], [false, 'form'], [false, 'search']],
            context: {"search_default_landlord":1,
                        "create": false},
        })
    }viewUsersFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Users Failure",
            res_model: "res.users",
            domain: [['update_replication','=',false]],
            views: [[false, 'list'], [false, 'form'], [false, 'search']],
            context: {"search_default_landlord":1,
                        "create": false},
        })
    }viewAttributeFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Product Attribute Failure",
            res_model: "product.attribute",
            domain: [['update_replication','=',false]],
            views: [[false, 'list'], [false, 'form'], [false, 'search']],
            context: {"search_default_landlord":1,
                        "create": false},
        })
    }viewPromotionFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Promotion Failure",
            res_model: "loyalty.program",
            domain: [['update_replication','=',false]],
            views: [[false, 'list'], [false, 'form'], [false, 'search']],
            context: {"search_default_landlord":1,
                        "create": false},
        })
    }viewAccountFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Account Failure",
            res_model: "account.account",
            domain: [['update_replication','=',false]],
            views: [[false, 'list'], [false, 'form'], [false, 'search']],
            context: {"search_default_landlord":1,
                        "create": false},
        })
    }viewVariantFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Product Variant Failure",
            res_model: "product.product",
            domain: [['update_replication','=',false]],
            views: [[false, 'list'], [false, 'form'], [false, 'search']],
            context: {"search_default_landlord":1,
                        "create": false},
        })
    }viewContactFailure(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "Contact Failure",
            res_model: "res.partner",
            domain: [['update_replication','=',false]],
            views: [[false, 'list'], [false, 'form'], [false, 'search']],
            context: {"search_default_landlord":1,
                        "create": false},
        })
    }

   async _fetchData() {
    try {
        const [AccountInfo, AccountTotal, AccountProcessed, TaxInfo, TaxTotal, TaxProcessed, FiscalYearInfo, FiscalTotal, FiscalProcessed, ProductTemplateInfo,ProductTemplateTotal,ProductTemplateProcessed,ProductCategoryInfo,ProductCategoryTotal,ProductCategoryProcessed,UsersInfo,UsersTotal,UsersProcessed,ProductAttributeInfo,ProductAttributeTotal,ProductAttributeProcessed,PromotionInfo,PromotionTotal,PromotionProcessed,ProductVariantInfo,ProductVariantTotal,ProductVariantProcessed,EmployeeInfo,EmployeeTotal,EmployeeProcessed, ContactInfo,ContactTotal,ContactProcessed,LiveSync, LiveStore, ProcessedEvent, ProcessedToday, TransactionEvent,TransactionToday] = await Promise.all([
                this.orm.call("account.account", "get_pending_account", {}),
                this.orm.call("account.account", "get_total_account", {}),
                this.orm.call("account.account", "get_processed_account", {}),
                this.orm.call("account.tax", "get_pending_tax", {}),
                this.orm.call("account.tax", "get_total_tax", {}),
                this.orm.call("account.tax", "get_processed_tax", {}),
                this.orm.call("account.fiscal.year", "get_pending_fiscal", {}),
                this.orm.call("account.fiscal.year", "get_total_fiscal", {}),
                this.orm.call("account.fiscal.year", "get_processed_fiscal", {}),
                this.orm.call("product.template", "get_pending_template", {}),
                this.orm.call("product.template", "get_total_template", {}),
                this.orm.call("product.template", "get_processed_template", {}),
                this.orm.call("product.category", "get_pending_category", {}),
                this.orm.call("product.category", "get_total_category", {}),
                this.orm.call("product.category", "get_processed_category", {}),
                this.orm.call("res.users", "get_pending_users", {}),
                this.orm.call("res.users", "get_total_users", {}),
                this.orm.call("res.users", "get_processed_users", {}),
                this.orm.call("product.attribute", "get_pending_attribute", {}),
                this.orm.call("product.attribute", "get_total_attribute", {}),
                this.orm.call("product.attribute", "get_processed_attribute", {}),
                this.orm.call("loyalty.program", "get_pending_loyalty", {}),
                this.orm.call("loyalty.program", "get_total_loyalty", {}),
                this.orm.call("loyalty.program", "get_processed_loyalty", {}),
                this.orm.call("product.product", "get_pending_product", {}),
                this.orm.call("product.product", "get_total_product", {}),
                this.orm.call("product.product", "get_processed_product", {}),
                this.orm.call("hr.employee", "get_pending_employee", {}),
                this.orm.call("hr.employee", "get_total_employee", {}),
                this.orm.call("hr.employee", "get_processed_employee", {}),
                this.orm.call("res.partner", "get_pending_partner", {}),
                this.orm.call("res.partner", "get_total_partner", {}),
                this.orm.call("res.partner", "get_processed_partner", {}),
                this.orm.call("nhcl.ho.store.master", "get_total_liveSync", {}),
                this.orm.call("nhcl.ho.store.master", "get_total_liveStore", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_total_processedEvent", {}),
                this.orm.call("nhcl.old.store.replication.log", "get_total_processedToday", {}),
                this.orm.call("nhcl.transaction.replication.log", "get_total_transactionEvent", {}),
                this.orm.call("nhcl.transaction.replication.log", "get_total_transactionToday", {}),


        ]);

        // Update the state with the fetched data
        this.state.pending.account = AccountInfo.pending_account;
        this.state.total.account = AccountTotal.total_account;
        this.state.processed.account = AccountProcessed.processed_account;
        this.state.pending.tax = TaxInfo.pending_tax;
        this.state.total.tax = TaxTotal.total_tax;
        this.state.processed.tax = TaxProcessed.processed_tax;
        this.state.pending.fiscal = FiscalYearInfo.pending_fiscal;
        this.state.total.fiscal = FiscalTotal.total_fiscal;
        this.state.processed.fiscal = FiscalProcessed.processed_fiscal;
        this.state.pending.template = ProductTemplateInfo.pending_template;
        this.state.total.template = ProductTemplateTotal.total_template;
        this.state.processed.template = ProductTemplateProcessed.processed_template;
        this.state.pending.category = ProductCategoryInfo.pending_category;
        this.state.total.category = ProductCategoryTotal.total_category;
        this.state.processed.category = ProductCategoryProcessed.processed_category;
        this.state.pending.users = UsersInfo.pending_users;
        this.state.total.users = UsersTotal.total_users;
        this.state.processed.users = UsersProcessed.processed_users;
        this.state.pending.attribute = ProductAttributeInfo.pending_attribute;
        this.state.total.attribute = ProductAttributeTotal.total_attribute;
        this.state.processed.attribute = ProductAttributeProcessed.processed_attribute;
        this.state.pending.loyalty = PromotionInfo.pending_loyalty;
        this.state.total.loyalty = PromotionTotal.total_loyalty;
        this.state.processed.loyalty = PromotionProcessed.processed_loyalty;
        this.state.pending.product = ProductVariantInfo.pending_product;
        this.state.total.product = ProductVariantTotal.total_product;
        this.state.processed.product = ProductVariantProcessed.processed_product;
        this.state.pending.employee = EmployeeInfo.pending_employee;
        this.state.total.employee = EmployeeTotal.total_employee;
        this.state.processed.employee = EmployeeProcessed.processed_employee;
        this.state.pending.partner = ContactInfo.pending_partner;
        this.state.total.partner = ContactTotal.total_partner;
        this.state.processed.partner = ContactProcessed.processed_partner;
        this.state.total.liveSync = LiveSync.total_liveSync;
        this.state.total.liveStore = LiveStore.total_liveStore;
        this.state.total.processedEvent = ProcessedEvent.total_processedEvent;
        this.state.total.processedToday = ProcessedToday.total_processedToday;
        this.state.total.transactionEvent = TransactionEvent.total_transactionEvent;
        this.state.total.transactionToday = TransactionToday.total_transactionToday;

    } catch (error) {
        console.error("Error fetching data", error);
    }

    }
}

BulkTrackingAction.template = "nhcl_ho_store_cmr_integration.BulkTracking";
registry.category("actions").add("bulk_tracking_action", BulkTrackingAction);


