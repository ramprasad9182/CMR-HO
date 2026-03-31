from odoo import http
from odoo.http import request
import logging


_logger = logging.getLogger(__name__)


class StockInventoryAdjustmentAPI(http.Controller):

    @http.route('/api/stock.adjustment/apply', type='json', auth='public', methods=['POST'], csrf=False)
    def apply_inventory_adjustment(self, **kwargs):
        try:
            data = request.jsonrequest
            line_ids = data.get('ho_line_ids')
            print("!!!!", line_ids)
            # inventory_reason = kwargs.get('inventory_reason')
            inventory_reason = data.get('inventory_adjustment_name', 'Quantity Updated')

            if not line_ids:
                return {
                    "success": False,
                    "message": "Inventory line ids are required"
                }

            # CREATE WIZARD
            wizard = request.env['stock.adjustment.name'].sudo().create({
                'quant_ids': [(6, 0, line_ids)],
                'inventory_adjustment_name': inventory_reason
            })

            # CALL WIZARD FUNCTION
            wizard.action_apply()

            return {
                "success": True,
                "message": "Inventory Adjustment Applied Successfully",
                "wizard_id": wizard.id
            }

        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }