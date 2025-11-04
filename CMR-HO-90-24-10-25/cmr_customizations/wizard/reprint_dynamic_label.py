import base64
import socket
from odoo import models, fields, api
from odoo.exceptions import UserError


class ReprintDynamicLabel(models.TransientModel):
    _name = 'reprint.dynamic.label'
    _description = 'Reprint Dynamic Label'

    serial_number_line_ids = fields.Many2many(
        'serial.number.lines',
        'reprint_label_serial_line_rel',
        'wizard_id',
        'serial_line_id',
        string='Serial Number Lines',
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

        if active_model == 'reprint.labels' and active_id:
            record = self.env['reprint.labels'].browse(active_id)
            res['serial_number_line_ids'] = [(6, 0, record.serial_number_lines.ids)]
        return res

    def action_print_label(self):
        """Send uploaded ZPL/PRN file to printer for each serial line."""
        self.ensure_one()

        if not self.serial_number_line_ids:
            raise UserError("Please select at least one serial number line.")
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

            # Loop over serial number lines
            for line in self.serial_number_line_ids:
                # Basic fields
                nhcl_name = line.name or ''
                product_name = line.product_id.categ_id.name or ''

                # Category fields (from lot)
                categ_1 = line.lot_id.category_1.name or ''
                categ_2 = line.lot_id.category_2.name or ''
                categ_3 = line.lot_id.category_3.name or ''
                categ_4 = line.lot_id.category_4.name or ''
                categ_5 = line.lot_id.category_5.name or ''
                categ_6 = line.lot_id.category_6.name or ''
                categ_7 = line.lot_id.category_7.name or ''
                categ_8 = line.lot_id.category_8.name or ''

                # Description fields (from lot)
                description_1 = line.lot_id.description_1.name or ''
                description_2 = line.lot_id.description_2.name or ''
                description_3 = line.lot_id.description_3.name or ''
                description_4 = line.lot_id.description_4.name or ''
                description_5 = line.lot_id.description_5.name or ''
                description_6 = line.lot_id.description_6.name or ''
                description_7 = line.lot_id.description_7.name or ''
                description_8 = line.lot_id.description_8.name or ''
                description_9 = line.lot_id.description_9.name or ''

                # Pricing (from lot)
                mr_price = line.lot_id.mr_price or 0
                rs_price = line.lot_id.rs_price or 0

                # Replace placeholders in ZPL
                zpl_content = (
                    zpl_template
                    .replace("{line.nhcl_name}", str(nhcl_name))
                    .replace("{product_name}", str(product_name))
                    .replace("{description_1}", str(description_1))
                    .replace("{description_2}", str(description_2))
                    .replace("{description_3}", str(description_3))
                    .replace("{description_4}", str(description_4))
                    .replace("{description_5}", str(description_5))
                    .replace("{description_6}", str(description_6))
                    .replace("{description_7}", str(description_7))
                    .replace("{description_8}", str(description_8))
                    .replace("{description_9}", str(description_9))
                    .replace("{line.categ_1}", str(categ_1))
                    .replace("{line.categ_2}", str(categ_2))
                    .replace("{line.categ_3}", str(categ_3))
                    .replace("{line.categ_4}", str(categ_4))
                    .replace("{line.categ_5}", str(categ_5))
                    .replace("{line.categ_6}", str(categ_6))
                    .replace("{line.categ_7}", str(categ_7))
                    .replace("{line.categ_8}", str(categ_8))
                    .replace("{int(line.mr_price)}", str(mr_price))
                    .replace("{int(line.rs_price)}", str(rs_price))
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
                'message': f'Printed {self.quantity_labels} label(s) for {len(self.serial_number_line_ids)} serial number line(s)',
                'sticky': False,
            }
        }
