/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

const actionRegistry = registry.category("actions");

export class LogisticDashboard extends Component {
    setup() {
        super.setup();
        this.orm = useService('orm');
        this._fetchData();
    }

    async _fetchData() {
        try {
            const [logisticInfo, DeliveryCheckInfo,TransportCheckInfo,OpenParcelInfo] = await Promise.all([
                this.orm.call("logistic.screen.data", "get_logistic_info", {}),
                this.orm.call("delivery.check", "get_delivery_check_info", {}),
                this.orm.call("transport.check", "get_transport_check_info", {}),
                this.orm.call("open.parcel", "get_open_parcel_info", {})
            ]);
            // Update the UI with logistic info
            this._updateLogisticInfo(logisticInfo);
            this._updateDeliveryCheckInfo(DeliveryCheckInfo);
            this._updateTransportCheckInfo(TransportCheckInfo);
            this._updateOpenParcelInfo(OpenParcelInfo);
        } catch (error) {
            console.error("Error fetching data", error);
        }
    }

    _updateLogisticInfo(logisticInfo) {
        $('#total_log_count').text('' + logisticInfo.total_logistic + '');
    }

    _updateDeliveryCheckInfo(DeliveryCheckInfo) {
        $('#total_delivery_count').text('' + DeliveryCheckInfo.delivery_count + '');
        $('#total_shortage_count').text('' + DeliveryCheckInfo.shortage_count + '');
        $('#total_transferred_bales').text('' + DeliveryCheckInfo.transferred_bales + '');
    }
    _updateTransportCheckInfo(TransportCheckInfo) {
        $('#total_upcoming_lr_count').text('' + TransportCheckInfo.upcoming_lr_count + '');
    }
    _updateOpenParcelInfo(OpenParcelInfo) {
        $('#total_open_parcel').text('' + OpenParcelInfo.open_parcel + '');
    }
}

LogisticDashboard.template = "cmr_customizations.LogisticDashboard";
actionRegistry.add("cmr_dashboard_tag", LogisticDashboard);
