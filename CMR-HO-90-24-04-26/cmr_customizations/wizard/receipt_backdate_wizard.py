from odoo import models, fields, api
from datetime import datetime


class ReceiptBackdateWizard(models.TransientModel):
    _name = 'receipt.backdate.wizard'
    _description = 'Receipt Backdate Wizard'

    backdate = fields.Datetime(string="Backdate", required=True)

    def action_apply_backdate(self):
        picking_ids = self.env.context.get('active_ids', [])
        pickings = self.env['stock.picking'].browse(picking_ids)

        for picking in pickings:
            backdate = self.backdate

            # 1. Update Picking dates
            picking.write({
                'scheduled_date': backdate,
                'date_done': backdate,
            })

            # 2. Update Stock Moves
            picking.move_ids_without_package.write({
                'date': backdate,
            })

            # 3. Update Move Lines
            picking.move_line_ids.write({
                'date': backdate,
            })

            # # 4. Update Lots / Serials create_date (SQL)
            # lots = picking.move_line_ids.mapped('lot_id')
            # lots.sudo().write({
            #     'create_date': backdate
            # })
            valuation_layers = self.env['stock.valuation.layer'].search([
                ('stock_move_id', 'in', picking.move_ids.ids)
            ])

            valuation_layers.write({
                'create_date': backdate
            })
            valuation_layers.account_move_id.write({
                'date': backdate
            })
            # if lots:
            #     self.env.cr.execute("""
            #         UPDATE stock_production_lot
            #         SET create_date = %s
            #         WHERE id IN %s
            #     """, (backdate, tuple(lots.ids)))
            #
            # # 5. Update Valuation Layers create_date (SQL)
            # valuation_layers = self.env['stock.valuation.layer'].search([
            #     ('stock_move_id', 'in', picking.move_ids_without_package.ids)
            # ])
            # if valuation_layers:
            #     self.env.cr.execute("""
            #         UPDATE stock_valuation_layer
            #         SET create_date = %s
            #         WHERE id IN %s
            #     """, (backdate, tuple(valuation_layers.ids)))
            #
            # # 6. Update Journal Entries from valuation
            # account_moves = valuation_layers.mapped('account_move_id')
            # for move in account_moves:
            #     move.write({'date': backdate})
            #     move.line_ids.write({'date': backdate})

        return {'type': 'ir.actions.act_window_close'}