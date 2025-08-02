/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

const actionRegistry = registry.category("actions");
export class EmptyPage extends Component {

}

EmptyPage.template = "nhcl_ho_store_cmr_integration.EmptyPage";
actionRegistry.add("empty_report", EmptyPage);
