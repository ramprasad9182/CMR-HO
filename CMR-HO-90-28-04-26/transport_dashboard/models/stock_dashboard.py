from odoo import models, api
import logging

_logger = logging.getLogger(__name__)


class Picking(models.Model):
    _inherit = "stock.picking"

    @api.model
    def _get_stock_incoming(self):
        self.env.cr.execute("""
                            SELECT sp.company_id,
                                   rc.name                 AS company_name,
                                   SUM(sm.product_uom_qty) AS total_qty
                            FROM stock_move sm
                                     JOIN stock_picking sp
                                          ON sm.picking_id = sp.id
                                     JOIN stock_picking_type spt
                                          ON sp.picking_type_id = spt.id
                                     JOIN res_company rc
                                          ON sp.company_id = rc.id
                            WHERE spt.code = 'incoming'
                            GROUP BY sp.company_id, rc.name;
                            """)
        return self.env.cr.dictfetchall()

    @api.model
    def _get_stock_deliveies(self):
        self.env.cr.execute("""
                            SELECT sp.company_id,
                                   rc.name                 AS company_name,
                                   SUM(sm.product_uom_qty) AS total_qty
                            FROM stock_move sm
                                     JOIN stock_picking sp
                                          ON sm.picking_id = sp.id
                                     JOIN stock_picking_type spt
                                          ON sp.picking_type_id = spt.id
                                     JOIN res_company rc
                                          ON sp.company_id = rc.id
                            WHERE spt.code = 'outgoing'
                            GROUP BY sp.company_id, rc.name;
                            """)
        return self.env.cr.dictfetchall()

    @api.model
    def _get_pos_exchange(self):
        self.env.cr.execute("""
                            SELECT sp.company_id,
                                   rc.name           AS company_name,
                                   SUM(sml.quantity) AS exchange
                            FROM stock_move_line sml
                                     JOIN stock_picking sp ON sp.id = sml.picking_id
                                     JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
                                     JOIN res_company rc
                                          ON sp.company_id = rc.id
                                              AND spt.stock_picking_type = 'exchange'

                            GROUP BY sp.company_id, rc.name;
                            """)
        return self.env.cr.dictfetchall()

    @api.model
    def _get_pos_deliveries(self):
        self.env.cr.execute("""
                            SELECT sp.company_id,
                                   rc.name           AS company_name,
                                   SUM(sml.quantity) AS deliveries
                            FROM stock_move_line sml
                                     JOIN stock_picking sp ON sp.id = sml.picking_id
                                     JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
                                     JOIN res_company rc
                                          ON sp.company_id = rc.id
                                              AND spt.stock_picking_type = 'pos_order'

                            GROUP BY sp.company_id, rc.name;
                            """)
        return self.env.cr.dictfetchall()

    @api.model
    def _get_store_return(self):
        self.env.cr.execute("""
                            SELECT sp.company_id,
                                   rc.name                 AS company_name,
                                   SUM(sm.product_uom_qty) AS total_qty
                            FROM stock_move sm
                                     JOIN stock_picking sp
                                          ON sm.picking_id = sp.id
                                     JOIN stock_picking_type spt
                                          ON sp.picking_type_id = spt.id
                                     JOIN res_company rc
                                          ON sp.company_id = rc.id
                            WHERE spt.stock_picking_type = 'damage'
                              AND rc.nhcl_company_bool = TRUE
                            GROUP BY sp.company_id, rc.name;
                            """)
        return self.env.cr.dictfetchall()

    @api.model
    def get_stock_report_by_company(self):
        incoming = self._get_stock_incoming()
        outgoing = self._get_stock_deliveies()
        exchange = self._get_pos_exchange()
        deliveries = self._get_pos_deliveries()
        storeReturn = self._get_store_return()

        # Convert lists to maps for easy lookup
        incoming_map = {
            r['company_id']: {
                'company_name': r['company_name'],
                'incoming': r['total_qty']
            }
            for r in incoming
        }

        outgoing_map = {
            r['company_id']: r['total_qty']
            for r in outgoing
        }

        exchange_map = {
            r['company_id']: r['exchange']
            for r in exchange
        }

        deliveries_map = {
            r['company_id']: r['deliveries']
            for r in deliveries
        }

        storeReturn_map = {
            r['company_id']: r['total_qty']
            for r in storeReturn
        }

        # Collect all company IDs
        company_ids = set()
        company_ids |= incoming_map.keys()
        company_ids |= outgoing_map.keys()
        company_ids |= exchange_map.keys()
        company_ids |= deliveries_map.keys()
        company_ids |= storeReturn_map.keys()

        result = []

        for company_id in company_ids:
            incoming_qty = incoming_map.get(company_id, {}).get('incoming', 0) or 0
            outgoing_qty = outgoing_map.get(company_id, 0) or 0
            exchange_qty = exchange_map.get(company_id, 0) or 0
            deliveries_qty = deliveries_map.get(company_id, 0) or 0
            storeReturn_qty = storeReturn_map.get(company_id, 0) or 0

            company_name = (
                    incoming_map.get(company_id, {}).get('company_name')
                    or self.env['res.company'].browse(company_id).name
            )

            result.append({
                'company_id': company_id,
                'company_name': company_name,
                'incoming': incoming_qty,
                'outgoing': outgoing_qty,
                'storeReturn': storeReturn_qty,
                'totalStock': incoming_qty - outgoing_qty,
                'totalClosing': incoming_qty - outgoing_qty + storeReturn_qty,
                'posExchange': exchange_qty,
                'posDeliveries': deliveries_qty,
                'totalInverts': deliveries_qty - exchange_qty,
            })

        return result
