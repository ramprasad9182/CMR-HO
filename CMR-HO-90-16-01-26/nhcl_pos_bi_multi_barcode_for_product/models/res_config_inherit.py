# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

class ResCompany(models.Model):
    _inherit = 'res.company'

    multi_barcode_for_product = fields.Boolean(string="Multi Barcode For Product")


class ConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    multi_barcode_for_product = fields.Boolean(related='company_id.multi_barcode_for_product',string="Multi Barcode For Product", readonly=False)
    zpl_printer_config = fields.Char(string="Zpl Printer Ip", config_parameter="zpl.printer_config")
    zpl_printer_config_port = fields.Char(string="Zpl Printer Port", config_parameter="zpl.printer_config_port")