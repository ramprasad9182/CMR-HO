/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {

    async _processData(loadedData) {
        await super._processData(loadedData);
        this._loadProductBarcode(loadedData['product.barcode'] || []);
    },

  _loadProductBarcode(barcodes){
        var self=this;
        self.barcode_by_name={};
        barcodes.forEach(function (barcode){
            self.barcode_by_name[barcode.barcode] = barcode;
        });
    }
    
});