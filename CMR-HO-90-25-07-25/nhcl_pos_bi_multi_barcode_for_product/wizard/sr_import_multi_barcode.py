import base64
from io import BytesIO
import openpyxl
from odoo import models, fields, _
from odoo.exceptions import UserError


class srImportMultipleBarcode(models.TransientModel):
    _name = 'sr.import.multiple.barcode'
    _description = 'Import Multiple Barcode'

    file = fields.Binary('File')
    import_product_by = fields.Selection([('name', 'Name'), ('code', 'Default Code')], string='Import Product By',
                                         default='name')
    import_barcode_for = fields.Selection([('product', 'Products'), ('template', 'Product Template')],
                                          string='Import Barcode For', default='product')

    def _import_barcode(self, line):
        domain = []
        if self.import_product_by == 'name':
            if self.import_barcode_for == 'product':
                product_id = self.env['product.product'].sudo().search([('name', '=', line[0])])
                if product_id:
                    for barcode in line[1].split(','):
                        self.env['product.barcode'].sudo().create({
                            'barcode': barcode,
                            'product_id': product_id.id,
                            'nhcl_inward_qty': line[2],
                            'nhcl_inward_date': line[3],
                            'nhcl_supplier_name': line[4],

                        })
                else:
                    raise UserError(_('%s The product was not found in the system.' % line[0]))
            else:
                product_tmpl_id = self.env['product.template'].sudo().search([('name', '=', line[0])])
                if product_tmpl_id:
                    for barcode in line[1].split(','):
                        self.env['product.barcode'].sudo().create({
                            'barcode': barcode,
                            'product_tmpl_id': product_tmpl_id.id,
                            'nhcl_inward_qty': line[2],
                            'nhcl_inward_date': line[3],
                            'nhcl_supplier_name': line[4],
                        })
                else:
                    raise UserError(_('%s The template was not found in the system.' % line[0]))
        else:
            if self.import_barcode_for == 'product':
                product_id = self.env['product.product'].sudo().search([('default_code', '=', line[0])])
                if product_id:
                    for barcode in line[1].split(','):
                        self.env['product.barcode'].sudo().create({
                            'barcode': barcode,
                            'product_id': product_id.id,
                            'nhcl_inward_qty': line[2],
                            'nhcl_inward_date': line[3],
                            'nhcl_supplier_name': line[4],
                        })
                else:
                    raise UserError(_('%s The default code was not found in the system.' % line[0]))
            else:
                product_tmpl_id = self.env['product.template'].sudo().search([('default_code', '=', line[0])])
                if product_tmpl_id:
                    for barcode in line[1].split(','):
                        self.env['product.barcode'].sudo().create({
                            'barcode': barcode,
                            'product_tmpl_id': product_tmpl_id.id,
                            'nhcl_inward_qty': line[2],
                            'nhcl_inward_date': line[3],
                            'nhcl_supplier_name': line[4],
                        })
                else:
                    raise UserError(_('%s The default code was not found in the system.' % line[0]))

    def import_multiple_barcode(self):
        try:
            wb = openpyxl.load_workbook(
                filename=BytesIO(base64.b64decode(self.file)), read_only=True
            )
            ws = wb.active
            for record in ws.iter_rows(min_row=2, max_row=None, min_col=None,
                                       max_col=None, values_only=True):
                self.sudo()._import_barcode(record)
        except Exception as e:
            raise UserError(_(e))
