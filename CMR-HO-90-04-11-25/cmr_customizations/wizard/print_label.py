import base64

import requests

from odoo import models, fields, api
from odoo.exceptions import UserError

class PrintLabel(models.TransientModel):
    _name = 'print.label'
    _description = 'Print Label'

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

    label_type = fields.Selection([

        ('ready_made', 'Ready Made'),
        ('single_rate', 'Single rate Sarees'),
        ('double_rate', 'Double rate Sarees'),
        ('discount_sarees', 'Dis sarees with double rate'),
        ('single_general_rate', 'Single rate general'),
        ('double_general_rate', 'Double rate general'),
        ('cosmetics', 'Cosmetics'),
        ('discount_general', 'Dis double rate general'),
        ('offer', 'Offer'),
        ('cosmetics', 'Cosmetics'),
    ('offer_sarees', 'Offer Sarees'),

    ], string="Label Type", required=True)

    picking_id = fields.Many2one('stock.picking', string="Picking", required=True)
    preview_pdf = fields.Binary("Preview PDF")

    def action_print_label(self):
        if not self.picking_id:
            raise UserError("No Picking record linked.")
        # if self.label_type == 'brand':
        #     return self.picking_id.print_barcodes_direct()
        elif self.label_type == 'ready_made':
            return self.picking_id.print_ready_made_barcodes_direct()
        # elif self.label_type == 'general':
        #     return self.picking_id.print_dymo_direct()
        elif self.label_type == 'offer':
            return self.picking_id.print_offer_direct()
        # elif self.label_type == 'combo_3':
        #     return self.picking_id.print_combo_3()
        elif self.label_type == 'single_rate':
            return self.picking_id.print_single_rate_barcodes_direct()
        elif self.label_type == 'double_rate':
            return self.picking_id.print_double_rate_barcodes_direct()
        elif self.label_type == 'single_general_rate':
            return self.picking_id.print_single_rate_barcodes_general_direct()
        elif self.label_type == 'double_general_rate':
            return self.picking_id.print_double_rate_barcodes_general_direct()
        elif self.label_type == 'discount_sarees':
            return self.picking_id.print_discount_sarees_direct()
        elif self.label_type == 'discount_general':
            return self.picking_id.print_discount_general_direct()
        elif self.label_type == 'cosmetics':
            return self.picking_id.print_cosmetics_direct()
        elif self.label_type == 'offer_sarees':
            return self.picking_id.print_offer_sarees_direct()
        else:
            raise UserError("Unknown label type.")

    def action_preview_label(self):
        self.ensure_one()
        if not self.picking_id:
            raise UserError("No Picking record linked.")

        # 1. Generate ZPL from stock.picking methods
        if self.label_type == "ready_made":
            zpl_data = self.picking_id.print_ready_made_barcodes()
        elif self.label_type == "offer":
            zpl_data = self.picking_id.print_offer()
        elif self.label_type == "single_rate":
            zpl_data = self.picking_id.print_single_rate_barcodes()
        elif self.label_type == "double_rate":
            zpl_data = self.picking_id.print_double_rate_barcodes()
        elif self.label_type == "single_general_rate":
            zpl_data = self.picking_id.print_single_rate_barcodes_general()
        elif self.label_type == "double_general_rate":
            zpl_data = self.picking_id.print_double_rate_barcodes_general()
        elif self.label_type == "discount_sarees":
            zpl_data = self.picking_id.print_discount_sarees()
        elif self.label_type == "discount_general":
            zpl_data = self.picking_id.print_discount_general()
        elif self.label_type == "cosmetics":
            zpl_data = self.picking_id.print_cosmetics()
        elif self.label_type == "offer_sarees":
            zpl_data = self.picking_id.print_offer_sarees()
        else:
            raise UserError("Unknown label type.")

        if not zpl_data:
            raise UserError("No ZPL data generated.")

        # 2. Take max 50 labels for preview
        labels = [lbl for lbl in zpl_data.split("^XZ") if lbl.strip()]
        preview_zpl = "^XZ".join(labels[:50]) + "^XZ"

        # 3. Convert with Labelary API to PDF
        url = "http://api.labelary.com/v1/printers/8dpmm/labels/4x6/0/"
        headers = {"Accept": "application/pdf"}
        response = requests.post(url, headers=headers, data=preview_zpl.encode("utf-8"))

        if response.status_code != 200:
            raise UserError(f"Labelary Error: {response.text}")

        # 4. Save result to wizard field
        self.preview_pdf = base64.b64encode(response.content)

        # 5. Refresh wizard form (to show preview)
        return {
            "type": "ir.actions.act_window",
            "res_model": "print.label",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
