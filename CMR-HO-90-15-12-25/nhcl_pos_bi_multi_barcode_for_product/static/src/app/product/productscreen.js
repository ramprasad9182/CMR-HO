/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { useService } from "@web/core/utils/hooks";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { Order, Orderline, Payment } from "@point_of_sale/app/store/models";
import { _t } from "@web/core/l10n/translation";
import { ProductInfoPopup } from "@point_of_sale/app/screens/product_screen/product_info_popup/product_info_popup";
import { ErrorBarcodePopup } from "@point_of_sale/app/barcode/error_popup/barcode_error_popup";

patch(ProductScreen.prototype, {
    setup() {
        super.setup();
        this.pos=usePos();
        this.popup = useService("popup");
    },
    /**
     * For accessibility, pressing <space> should be like clicking the product.
     * <enter> is not considered because it conflicts with the barcode.
     *
     * @param {KeyPressEvent} event
     */
   
   async _barcodeProductAction(code) {
    let self = this;
        let selectedOrder = this.pos.get_order();
        let barcode = this.env.services.pos.barcode_by_name[code.base_code];
        if(barcode){
            let products = [];
            if(barcode.product_id){
                let product = this.env.services.pos.db.get_product_by_id(barcode.product_id[0]);
                if(product){
                    selectedOrder.add_product(product,{quantity:1});
                    return true;
                }else{
                    return true;
                }
            }
            else if(barcode.product_tmpl_id){
                let list = self.env.services.pos.db.search_product_in_category(0,code.base_code);
                if(list.length ==1){
                    selectedOrder.add_product(list[0], {quantity:1});
                    return true;
                }else{
                    return false;
                }
            }else{
                return false;
            }
        }else{
            super._barcodeProductAction(code); 
        }
    },

  });

    