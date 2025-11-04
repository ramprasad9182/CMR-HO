
from odoo import api, fields, models


class PiPOGrc(models.Model):
    _name = 'pi.po.grc'
    _auto = False
    _description = "PI - PO - GRC Report"

    product_id = fields.Many2one('product.product', string='Product')
    serial_number_id = fields.Many2one('stock.lot', string='Serial Number')
    approval_reqeuest_id = fields.Many2one('approval.request', string='PI Number')
    approval_create_date = fields.Date(string='Date')
    approval_quantity = fields.Float(string='PI Quantity', group_operator='max')
    po_number = fields.Many2one('purchase.order', string='PO Number')
    po_quantity = fields.Float(string='PO Quantity',group_operator='max')
    receipt_number = fields.Many2one('stock.picking', string='Receipt Number')
    receipt_number_qty = fields.Float(string='Receipt Qty', group_operator='max')
    partner_id = fields.Many2one('res.partner', string='Site')  # Other Odoo company
    sale_transfer_id = fields.Many2one('stock.picking', string='Transfer Number')
    sale_delivery_qty = fields.Float(string='Site Transfer Qty')
    pos_delivery_quantity_in_partner_company = fields.Float(string='Sold Quantity')
    return_quantity_from_partner = fields.Float(string='Return Quantity')
    present_stock_quantity = fields.Float(string="SOH at WH",group_operator='max')
    company_id = fields.Many2one('res.company', string="Company")
    po_origin = fields.Char(string='SO')

    @property
    def _table_query(self):
        return f"""
                {self._select()}
                {self._from()}
                {self._where()}
                {self._group_by()}

            """

    def _select(self):
        return """
                SELECT
                    row_number() OVER () AS id,
                    ar.id AS approval_reqeuest_id,
                    ar.create_date AS approval_create_date,
                    apl.product_id AS product_id,
                    apl.quantity AS approval_quantity,
                    po.id AS po_number,
                    pol.product_qty AS po_quantity,
                    sp.id AS receipt_number,
                    max(sm.quantity) AS receipt_number_qty,
                    transfer.id AS sale_transfer_id,
                    transfer.partner_id AS partner_id,
                    transfer.origin AS po_origin ,

                    sum(transfer_line.quantity)
                   AS sale_delivery_qty,

                SUM(pos_delivery.unique_lot_qty) AS pos_delivery_quantity_in_partner_company,

                  (
                        SELECT COUNT(sl.id)
                         FROM stock_lot sl
                         WHERE sl.product_id = apl.product_id
                         AND sl.company_id = po.company_id
                         AND sl.location_id IN (
                             SELECT id FROM stock_location WHERE usage = 'internal'
                         )
                         AND sl.id IN (
                             SELECT lot_id FROM stock_move_line WHERE picking_id = sp.id
                        )
                    ) AS present_stock_quantity,
                  sum(pos_return.return_unique_lot_qty) AS return_quantity_from_partner,
                 po.company_id AS company_id
            """

    def _from(self):
        return """
                FROM approval_product_line apl
                JOIN approval_request ar ON apl.approval_request_id = ar.id
                LEFT JOIN purchase_order po ON po.origin = ar.name
                LEFT JOIN res_company rc ON po.company_id = rc.id AND rc.nhcl_company_bool = TRUE

                LEFT JOIN purchase_order_line pol ON pol.order_id = po.id AND pol.product_id = apl.product_id
                LEFT JOIN stock_picking sp ON sp.origin = po.name and sp.picking_type_id
                IN (
            SELECT id FROM stock_picking_type WHERE code = 'incoming'
        )
                LEFT JOIN stock_move sm ON sm.picking_id = sp.id AND sm.product_id = apl.product_id
                LEFT JOIN stock_move_line sml ON sml.move_id = sm.id AND sml.product_id = apl.product_id AND sml.company_id='1'



                left join stock_picking transfer on transfer.stock_picking_type = 'delivery'

       join stock_move transfer_move on transfer_move.picking_id = transfer.id

     left join stock_move_line transfer_line on transfer_line.lot_id = sml.lot_id and transfer_move.id= transfer_line.move_id

      left join(SELECT
            smls.lot_name,
            count(distinct smls.lot_name) AS unique_lot_qty
        FROM stock_move_line smls join stock_picking spls on smls.picking_id= spls.id
        WHERE smls.location_dest_id = (
            SELECT id FROM stock_location WHERE name = 'Customers'
        )
        AND smls.company_id <> 1 and spls.stock_picking_type = 'pos_order'
        GROUP BY smls.lot_name
    ) AS pos_delivery ON pos_delivery.lot_name = sml.lot_name

       left join(SELECT
            smlrs.lot_name,
            count(distinct smlrs.lot_name) AS return_unique_lot_qty
        FROM stock_move_line smlrs join stock_picking splrs on smlrs.picking_id= splrs.id
        WHERE smlrs.location_id = (
            SELECT id FROM stock_location WHERE name = 'Customers'
        )
        AND smlrs.company_id <> 1 and splrs.stock_picking_type = 'exchange' and splrs.stock_type='pos_exchange'
        GROUP BY smlrs.lot_name
    ) AS pos_return on pos_return.lot_name=pos_delivery.lot_name 



            """

    def _where(self):
        return """
                WHERE 

                  transfer_line.company_id='1' 
                   AND sml.company_id='1' and transfer.group_id<>po.id and transfer.company_id='1' 

            """

    def _group_by(self):
        return """
                GROUP BY
                    ar.id,
                    ar.create_date,
                    apl.product_id,
                    apl.quantity,
                    po.id,
                    pol.product_qty,
                    sp.id,
                    transfer.id,
                    transfer.partner_id,
                    po.company_id,
                    sm.quantity,
                    transfer_line.reference






            """

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        res = []
        if fields:
            res = super(PiPOGrc, self).read_group(
                domain, fields, groupby, offset=offset,
                limit=limit, orderby=orderby, lazy=lazy
            )
        return res