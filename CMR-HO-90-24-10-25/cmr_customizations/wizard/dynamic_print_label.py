import base64
import socket

import requests

from odoo import models, fields, api
from odoo.exceptions import UserError


class DynamicPrintLabel(models.TransientModel):
    _name = 'dynamic.print.label'
    _description = 'Dynamic Print Label'

    # label_type = fields.Selection([
    #     ('brand', 'Brand'),
    #     ('ready_made', 'Ready Made'),
    #     ('general', 'General'),
    #     ('offer', 'Offer'),
    #     # ('combo_3', 'Combo 3'),
    #     ('single_rate', 'Single rate Sarees'),
    #     ('cosmetics', 'Cosmetics'),
    #     ('discount_sarees', 'Discount Sarees'),
    #     ('discount_general', 'Discount General'),
    #     ('double_rate', 'Double rate Sarees'),
    #     ('single_general_rate', 'Single rate general'),
    #     ('double_general_rate', 'Double rate general')
    # ], string="Label Type", required=True)
    # move_line_ids = fields.Many2many(
    #     'stock.move.line',
    #
    #     'wizard_id',
    #     'move_line_id',
    #     string='Move Lines',
    # )
    move_line_ids = fields.Many2many(
        'stock.move.line',
        'dynamic_print_label_move_line_rel',  # relation table name
        'wizard_id',  # column for wizard
        'move_line_id',  # column for move line
        string='Move Lines',
    )

    file = fields.Binary(string='PRN / ZPL File', required=True)
    file_name = fields.Char(string='File Name')
    printer_ip = fields.Char(string='Printer IP', required=True, default='192.168.168.100')
    printer_port = fields.Integer(string='Port', default=9100)
    quantity_labels = fields.Integer(string='Quantity')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        active_model = self.env.context.get('active_model')

        if active_model == 'stock.picking' and active_id:
            picking = self.env['stock.picking'].browse(active_id)
            res['move_line_ids'] = [(6, 0, picking.move_line_ids.ids)]
        return res

    def action_print_label(self):
        """Send the uploaded ZPL/PRN file to the printer for each move line and quantity."""
        self.ensure_one()

        if not self.move_line_ids:
            raise UserError("Please select at least one move line.")
        if not self.printer_ip:
            raise UserError("Please enter printer IP.")
        if not self.file:
            raise UserError("Please upload a ZPL/PRN file.")
        if not self.quantity_labels or self.quantity_labels < 1:
            raise UserError("Quantity must be at least 1.")

        try:
            # Open socket to printer
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.printer_ip, self.printer_port))

            # Decode PRN/ZPL template
            zpl_template = base64.b64decode(self.file).decode('utf-8')

            # Loop over move lines
            for move_line in self.move_line_ids:
                # Basic fields
                nhcl_name = move_line.lot_id.name or ''
                product_name = move_line.product_id.categ_id.name or ''
                print("erwe",product_name)

                # Category fields (no 'or ''')
                categ_1 = move_line.categ_1.name
                categ_2 = move_line.categ_2.name
                categ_3 = move_line.categ_3.name
                categ_4 = move_line.categ_4.name
                categ_5 = move_line.categ_5.name
                categ_6 = move_line.categ_6.name
                categ_7 = move_line.categ_7.name
                categ_8 = move_line.categ_8.name

                # Description fields (with 'or ''')
                description_1 = move_line.descrip_1.name or ''
                description_2 = move_line.descrip_2.name or ''
                description_3 = move_line.descrip_3.name or ''
                description_4 = move_line.descrip_4.name or ''
                description_5 = move_line.descrip_5.name or ''
                description_6 = move_line.descrip_6.name or ''
                description_7 = move_line.descrip_7.name or ''
                description_8 = move_line.descrip_8.name or ''
                description_9 = move_line.descrip_9.name or ''

                # Other fields

                mr_price = move_line.mr_price or 0
                rs_price = move_line.rs_price or 0

                # Replace placeholders in ZPL
                zpl_content = (
                    zpl_template
                    .replace("{line.nhcl_name}", str(move_line.lot_id.name or ''))
                    .replace("{product_name}", str(move_line.product_id.categ_id.name or ''))
                    .replace("{description_1}", str(move_line.descrip_1.name or ''))
                    .replace("{description_2}", str(move_line.descrip_2.name or ''))
                    .replace("{description_3}", str(move_line.descrip_3.name or ''))
                    .replace("{description_4}", str(move_line.descrip_4.name or ''))
                    .replace("{description_5}", str(move_line.descrip_5.name or ''))
                    .replace("{description_6}", str(move_line.descrip_6.name or ''))
                    .replace("{description_7}", str(move_line.descrip_7.name or ''))
                    .replace("{description_8}", str(move_line.descrip_8.name or ''))
                    .replace("{description_9}", str(move_line.descrip_9.name or ''))
                    .replace("{line.categ_1}", str(move_line.categ_1.name or ''))
                    .replace("{line.categ_2}", str(move_line.categ_2.name or ''))
                    .replace("{line.categ_3}", str(move_line.categ_3.name or ''))
                    .replace("{line.categ_4}", str(move_line.categ_4.name or ''))
                    .replace("{line.categ_5}", str(move_line.categ_5.name or ''))
                    .replace("{line.categ_6}", str(move_line.categ_6.name or ''))
                    .replace("{line.categ_7}", str(move_line.categ_7.name or ''))
                    .replace("{line.categ_8}", str(move_line.categ_8.name or ''))

                    .replace("{int(line.mr_price)}", str(move_line.mr_price or 0))
                    .replace("{int(line.rs_price)}", str(move_line.rs_price or 0))
                )

                # Send to printer according to quantity
                for _ in range(self.quantity_labels):
                    s.send(zpl_content.encode('utf-8'))

            s.close()

        except Exception as e:
            raise UserError(f"Failed to send labels to printer: {e}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'Printed {self.quantity_labels} label(s) for {len(self.move_line_ids)} move line(s)',
                'sticky': False,
            }
        }

