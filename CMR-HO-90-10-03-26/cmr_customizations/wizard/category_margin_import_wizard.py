from odoo import models, fields
from odoo.exceptions import ValidationError
import base64
import io
import pandas as pd


class CategoryMarginImportWizard(models.TransientModel):
    _name = "category.margin.import.wizard"
    _description = "Category Margin Import Wizard"

    file = fields.Binary(required=True)
    file_name = fields.Char()

    def action_import(self):

        if not self.file:
            raise ValidationError("Please upload file.")

        file_data = base64.b64decode(self.file)
        df = pd.read_excel(io.BytesIO(file_data))

        last_category = False
        last_type = False
        processed_categories = set()

        for index, row in df.iterrows():

            # Handle grouped Category
            if pd.notna(row.get('Category')):
                last_category = row.get('Category')

            # Handle grouped Type
            if pd.notna(row.get('Type')):
                last_type = str(row.get('Type')).strip().upper()

            if not last_category or not last_type:
                raise ValidationError(
                    f"Missing Category or Type at row {index+2}"
                )

            category = self.env['product.category'].search([
                ('name', '=', last_category),
                ('parent_id', '=', False)
            ], limit=1)

            if not category:
                raise ValidationError(
                    f"Category '{last_category}' not found or not parent."
                )

            # Delete existing lines only once per category
            if category.id not in processed_categories:
                self.env['product.category.mrp.line'].search([
                    ('product_category_mrp_id', '=', category.id)
                ]).unlink()

                self.env['product.category.margin.line'].search([
                    ('product_category_margin_id', '=', category.id)
                ]).unlink()

                processed_categories.add(category.id)

            from_range = float(row.get('From Range'))
            to_range = float(row.get('To Range'))
            margin = float(row.get('Margin'))

            if from_range > to_range:
                raise ValidationError(
                    f"Invalid range at row {index+2}"
                )

            if last_type == 'MRP':
                self.env['product.category.mrp.line'].create({
                    'product_category_mrp_id': category.id,
                    'from_range': from_range,
                    'to_range': to_range,
                    'margin': margin,
                })

            elif last_type == 'RSP':
                self.env['product.category.margin.line'].create({
                    'product_category_margin_id': category.id,
                    'from_range': from_range,
                    'to_range': to_range,
                    'margin': margin,
                })

            else:
                raise ValidationError(
                    f"Invalid Type at row {index+2}. Use MRP or RSP."
                )

        return {'type': 'ir.actions.act_window_close'}