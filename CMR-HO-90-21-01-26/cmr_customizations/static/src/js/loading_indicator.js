/* @odoo-module */

import { browser } from "@web/core/browser/browser";
import { LoadingIndicator } from "@web/webclient/loading_indicator/loading_indicator";
import { patch } from "@web/core/utils/patch";

patch(LoadingIndicator.prototype, {
    requestCall({ detail }) {
        if (detail.settings.silent) {
            return;
        }
        if (this.state.count === 0) {
            browser.clearTimeout(this.startShowTimer);
            this.startShowTimer = browser.setTimeout(() => {
                if (this.state.count) {
                    this.state.show = true;
                    this.uiService.block();
                    this.shouldUnblock = true;
                }
            }, 250);
        }
        this.rpcIds.add(detail.data.id);
        this.state.count++;
    }
});