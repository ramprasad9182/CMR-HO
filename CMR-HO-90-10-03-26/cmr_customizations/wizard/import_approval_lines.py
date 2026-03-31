import openpyxl
from odoo import fields, models, _, exceptions
from odoo.exceptions import UserError, ValidationError
import logging
_logger = logging.getLogger(__name__)
import io

try:
    import xlrd
except ImportError:
    _logger.debug('Oops! Cannot `import xlrd`.')
try:
    import csv
except ImportError:
    _logger.debug('Oops! Cannot `import csv`.')
try:
    import base64
except ImportError:
    _logger.debug('Oops! Cannot `import base64`.')

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import base64
import io
import openpyxl

class ImportApprovalLineWizard(models.TransientModel):
    _name = 'import.approval.line.wizard'
    _description = "Import Approval Request Lines"

    approval_line_file = fields.Binary(string="Select File", required=True)
    import_prod_option = fields.Selection([
        ('barcode', 'Barcode'),
        ('name', 'Name'),
        ('code', 'Internal Reference')
    ], string='Import Product By', default='barcode', required=True)

    # 🆕 Additional fields requested


    def import_approval_line(self):
        """Import product approval lines from an Excel file."""
        try:
            wb = openpyxl.load_workbook(
                filename=io.BytesIO(base64.b64decode(self.approval_line_file)), read_only=True
            )
            ws = wb.active
        except Exception:
            raise ValidationError(_("Invalid or corrupt file! Please upload a valid Excel file."))

        approval_request = self.env['approval.request'].browse(self._context.get('active_id'))
        if not approval_request:
            raise ValidationError(_("No approval request found."))

        if approval_request.request_status not in ('new', 'pending'):
            raise UserError(_("You cannot import data into a validated or confirmed request."))

        counter = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue

            product_code = str(row[0]).strip()
            quantity = float(row[1] or 0)
            if quantity <= 0:
                raise ValidationError(_('%s Quantity must be greater than zero.') % product_code)

            # Optional columns (if present)
            unit_price = float(row[2] or 0)
            enter_margin = float(row[3] or 0)
            enter_rsp = float(row[4] or 0)
            nhcl_margin_rsp_type = str(row[5] or '').strip()
            design_category_name = str(row[6] or '').strip()

            print("enter_margin",enter_margin,"enter_rsp",enter_rsp,"nhcl_margin_rsp_type",nhcl_margin_rsp_type)

            # Product lookup
            product = self._find_product(product_code)
            if not product:
                raise ValidationError(_('%s Product not found in the system.') % product_code)

            # --- Validation for nhcl_margin_rsp_type ---
            if nhcl_margin_rsp_type == 'margin':
                if not enter_margin or enter_margin <= 0:
                    raise ValidationError(_("Please enter a valid Margin value for product: %s") % product_code)
                if enter_rsp and enter_rsp > 0:
                    raise ValidationError(
                        _("You selected 'Margin' type. Please enter Margin only, not RSP — Product: %s") % product_code)

            elif nhcl_margin_rsp_type == 'rsp':
                if not enter_rsp or enter_rsp <= 0:
                    raise ValidationError(_("Please enter a valid RSP value for product: %s") % product_code)
                if enter_margin and enter_margin > 0:
                    raise ValidationError(
                        _("You selected 'RSP' type. Please enter RSP only, not Margin — Product: %s") % product_code)

            else:
                raise ValidationError(_("Invalid Margin/RSP Type for product: %s") % product_code)

            # Avoid duplicates
            existing_line = approval_request.product_line_ids.filtered(
                lambda l: l.product_id == product
            )
            if existing_line:
                raise ValidationError(_('%s The product already exists.') % product_code)

            # Get Design Category (optional)
            design_category = False
            if design_category_name:
                design_category = self.env['product.attribute.value'].search(
                    [('name', '=', design_category_name)], limit=1
                )

            approval_line = self.env['approval.product.line'].create({
                'approval_request_id': approval_request.id,
                'product_id': product.id,
                'prod_barcode': product.barcode,
                'description': product.display_name,
                'quantity': quantity,
                'family': product.categ_id.id,
                'category': product.categ_id.parent_id.id,
                'Class': product.categ_id.parent_id.parent_id.id,
                'brick': product.categ_id.parent_id.parent_id.parent_id.id,
                'unit_price': unit_price,
                'enter_rsp_margin': enter_margin,
                'pi_rsp_price': enter_rsp,
                'nhcl_margin_rsp_type': nhcl_margin_rsp_type,
                'design_category_id': design_category.id if design_category else False,
            })

            # ✅ Correct way: call onchange on the record itself
            approval_line.onchange_enter_rsp_margin()
            approval_line.calculate_rsp_margin()
            approval_line.onchange_pi_mrp_price()
            approval_line.onchange_default_rsp_margin()
            approval_line._compute_tax_id()
            approval_line._compute_amount()
            counter += 1

        # Success popup
        view_id = self.env.ref('cmr_customizations.message_wizard_popup')
        context = dict(self._context or {})
        context['message'] = f"{counter} records imported successfully."

        return {
            'name': _('Success'),
            'type': 'ir.actions.act_window',
            'res_model': 'message.wizard',
            'view_mode': 'form',
            'views': [(view_id.id, 'form')],
            'target': 'new',
            'context': context,
        }

    def _find_product(self, code):
        """Helper to find a product based on import option."""
        Product = self.env['product.product']
        Barcode = self.env['product.barcode']

        if self.import_prod_option == 'barcode':
            product = Product.search([('barcode', '=', code)], limit=1)
            if not product:
                alt_barcode = Barcode.search([('barcode', '=', code)], limit=1)
                product = alt_barcode.product_id if alt_barcode else False
        elif self.import_prod_option == 'code':
            product = Product.search([('default_code', '=', code)], limit=1)
        elif self.import_prod_option == 'name':
            product = Product.search([('name', '=', code)], limit=1)
        else:
            product = False
        return product