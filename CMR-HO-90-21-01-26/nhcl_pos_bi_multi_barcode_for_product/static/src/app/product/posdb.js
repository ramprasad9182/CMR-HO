/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { PosDB } from "@point_of_sale/app/store/db";

patch(PosDB.prototype, {

    _product_search_string: function(product){
        var str = product.display_name;
        if (product.barcode) {
            str += '|' + product.barcode;
        }
        if (product.default_code) {
            str += '|' + product.default_code;
        }
        if (product.description) {
            str += '|' + product.description;
        }
        if (product.product_barcodes) {
            str += '|' + product.product_barcodes;
        }
        if (product.description_sale) {
            str += '|' + product.description_sale;
        }
        str  = product.id + ':' + str.replace(/:/g,'') + '\n';
        return str;
    }
    
});