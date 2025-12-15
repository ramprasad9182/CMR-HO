from odoo import models,fields,api,_
from odoo.exceptions import ValidationError
import pytz


import base64
import io


from odoo.exceptions import ValidationError, UserError
from odoo.tools import format_date
import xlsxwriter



class HoAuditReport(models.Model):
    _name = 'ho.audit.report'

    from_date = fields.Datetime('From Date')
    to_date = fields.Datetime('To Date')
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company')
    plan_id = fields.Many2one('stock.inventory', string='Plan', domain=[('state', '=', 'done')])
    # plan_dup = fields.Many2one('stock.inventory',string='Plan Dup',related='plan_id.plan_name')
    ho_audit_report_ids = fields.One2many('ho.audit.report.line', 'ho_audit_report_id')



    def ho_audit_report(self):
        for report in self:
            if not report.nhcl_store_id:
                raise ValidationError("Please select at least one Company")

            # Clear previous lines
            report.ho_audit_report_ids = [(5, 0, 0)]

            # Build domain for stock.inventory
            inventory_domain = []
            if report.plan_id:
                inventory_domain.append(('id', '=', report.plan_id.id))
            if report.from_date and report.to_date:
                inventory_domain += [
                    ('from_date_range', '<=', report.from_date),
                    ('to_date_range', '>=', report.to_date)
                ]

            # Fetch inventories
            inventories = self.env['stock.inventory'].search(inventory_domain)

            if not inventories:
                continue  # No inventories in range

            # Fetch all related lines at once
            inventory_lines = self.env['stock.inventory.line'].search([
                ('inventory_id', 'in', inventories.ids)
            ])

            # Fetch all lot info in one go to reduce load
            lot_names = [line.prod_lot_id.name for line in inventory_lines if line.prod_lot_id]
            lots = {lot.name: lot for lot in self.env['stock.lot'].search([('name', 'in', lot_names)])}

            lines_to_create = []
            for line in inventory_lines:
                inv = line.inventory_id
                product = line.product_id

                # Snap levels
                snap_division = snap_section = snap_department = snap_article = ''
                if product and product.categ_id:
                    levels = []
                    current = product.categ_id
                    while current:
                        levels.append(current.name)
                        current = current.parent_id
                    levels = levels[::-1]  # top → bottom

                    snap_division = levels[0] if len(levels) >= 1 else ''
                    snap_section = levels[1] if len(levels) >= 2 else ''
                    snap_department = levels[2] if len(levels) >= 3 else ''
                    snap_article = levels[3] if len(levels) >= 4 else ''

                # Lot info
                new_desc_five_value = ''
                physical_stock_rsp_value = 0.0
                mrp_value = 0.0
                cp_value = 0.0
                if line.prod_lot_id and line.prod_lot_id.name in lots:
                    lot = lots[line.prod_lot_id.name]
                    new_desc_five_value = lot.description_1.name or ''
                    physical_stock_rsp_value = lot.rs_price or 0.0
                    mrp_value = lot.mr_price or 0.0
                    cp_value = lot.cost_price or 0.0
                    snap_categ1 = lot.category_1.name
                    snap_categ2 = lot.category_2.name
                    snap_categ3 = lot.category_3.name
                    snap_categ4 = lot.category_4.name
                    snap_categ5 = lot.category_5.name
                    snap_categ6 = lot.category_6.name

                # Last inward rate for product
                last_inward_rate = 0.0
                if product:
                    last_lot = self.env['stock.lot'].search(
                        [('product_id', '=', product.id), ('rs_price', '!=', False)],
                        order='create_date desc',
                        limit=1
                    )
                    if last_lot:
                        last_inward_rate = last_lot.rs_price or 0.0

                # Prepare audit line
                lines_to_create.append((0, 0, {
                    'product_id': product.nhcl_display_name if product else False,
                    'audit_site': inv.company_id.name if inv.company_id else '',
                    'stock_point': inv.warehouse_id.name if inv.warehouse_id else '',
                    'audit_plan': inv.plan_name if inv.plan_name else '',
                    'description': inv.plan_name if inv.plan_name else '',
                    'start_date': inv.create_date or '',
                    'remarks': inv.plan_name or '',
                    'barcode': line.prod_lot_id.name if line.prod_lot_id else '',
                    'snap_division': snap_division,
                    'snap_section': snap_section,
                    'snap_department': snap_department,
                    'snap_article': snap_article,
                    'book_stock_qty': line.qty_done or 0.0,
                    'book_stock_rsp': physical_stock_rsp_value,
                    'physical_stock_qty': line.theoretical_qty or 0.0,
                    'physical_stock_rsp': physical_stock_rsp_value,
                    'snapshot_qty': line.qty_done or 0.0,
                    'dif_qty': line.theoretical_qty - line.qty_done ,
                    'snapshot_rsp': physical_stock_rsp_value,
                    'dif_rsp_amount': physical_stock_rsp_value - physical_stock_rsp_value,
                    'new_desc_five': new_desc_five_value,
                    'rsp': physical_stock_rsp_value,
                    'mrp': mrp_value,
                    'cost_price': cp_value,
                    'new_division': snap_division,
                    'new_section': snap_section,
                    'new_department': snap_department,
                    'new_article': snap_article,
                    'item_rate': last_inward_rate,
                    'snap_categ_one': snap_categ1,
                    'snap_categ_two': snap_categ2,
                    'snap_categ_three': snap_categ3,
                    'snap_categ_four': snap_categ4,
                    'snap_categ_five': snap_categ5,
                    'snap_categ_six': snap_categ6,
                    'new_categ_one': snap_categ1,
                    'new_categ_two': snap_categ2,
                    'new_categ_three': snap_categ3,
                    'new_categ_four': snap_categ4,
                    'new_categ_five': snap_categ5,
                    'new_categ_six': snap_categ6,
                    'new_barcode': line.prod_lot_id.name if line.prod_lot_id else '',
                    'book_stock_value': 0.0,


                }))

            # Create all audit lines at once
            report.ho_audit_report_ids = lines_to_create

            # Calculate dif_rsp_amount safely if needed
            for audit_line in report.ho_audit_report_ids:
                audit_line.dif_rsp_amount = (audit_line.physical_stock_rsp or 0.0) - (audit_line.snapshot_rsp or 0.0)

    def action_to_reset(self):
        for report in self:
            self.write({
                'nhcl_store_id': False,
                'plan_id': False,
                'from_date': False,
                'to_date': False
            })
            report.ho_audit_report_ids.unlink()

    def get_excel_sheet(self):
        # Create a file-like buffer to receive the data
        buffer = io.BytesIO()

        # Create an Excel workbook and add a worksheet
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        worksheet = workbook.add_worksheet()

        # Add a bold format to use to highlight cells
        bold = workbook.add_format({'bold': True})

        # Write data headers
        headers = ['Audit site','Stock Point','Audit Plan','Description','Actual Start Date','Remarks','Barcode','Snap Family', 'Snap Category', 'Snap Class', 'Snap Brick',
                   'Snap Categ1', 'Snap Categ2', 'Snap Categ3', 'Snap Categ4', 'Snap Categ5', 'Snap Categ6','Snap Article','Vendor','New Family', 'New Category', 'New Class', 'New Brick',
                   'New Categ1', 'New Categ2', 'New Categ3', 'New Categ4', 'New Categ5', 'New Categ6','New Desc5','New Article',
                   'New Barcode', 'Book Stock Qty', 'Book Stock RSP', 'Physical Stock Qty',
                   'Physical Stock RSP', 'Snapshot Qty', 'Snapshot RSP', 'Difference Qty','MRP','RSP','Cost Price','Differential RSP Amount',
                   'Item Rate (Last Inward)','Book Stock Value(Last Inward)','Physical Stock Value (Last Inward)','Difference Stock Value (Last Inward)','product']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header, bold)

        # Write data rows
        for row_num, line in enumerate(self.ho_audit_report_ids, start=1):
            worksheet.write(row_num, 0, line.audit_site)
            worksheet.write(row_num, 1, line.stock_point)
            worksheet.write(row_num, 2, line.audit_plan)
            worksheet.write(row_num, 3, line.description)
            worksheet.write(row_num, 4, line.start_date and format_date(self.env, line.start_date, date_format='dd-MM-yyyy'))
            worksheet.write(row_num, 5, line.remarks)
            worksheet.write(row_num, 6, line.barcode)
            worksheet.write(row_num, 7, line.snap_division)
            worksheet.write(row_num, 8, line.snap_section)
            worksheet.write(row_num, 9, line.snap_department)
            worksheet.write(row_num, 10, line.snap_article)
            worksheet.write(row_num, 11, line.snap_categ_one)
            worksheet.write(row_num, 12, line.snap_categ_two)
            worksheet.write(row_num, 13, line.snap_categ_three)
            worksheet.write(row_num, 14, line.snap_categ_four)
            worksheet.write(row_num, 15, line.snap_categ_five)
            worksheet.write(row_num, 16, line.snap_categ_six)
            worksheet.write(row_num, 17, line.product_id)
            worksheet.write(row_num, 18, line.vendor)
            worksheet.write(row_num, 19, line.new_division)
            worksheet.write(row_num, 20, line.new_section)
            worksheet.write(row_num, 21, line.new_department)
            worksheet.write(row_num, 22, line.new_article)
            worksheet.write(row_num, 23, line.new_categ_one)
            worksheet.write(row_num, 24, line.new_categ_two)
            worksheet.write(row_num, 25, line.new_categ_three)
            worksheet.write(row_num, 26, line.new_categ_four)
            worksheet.write(row_num, 27, line.new_categ_five)
            worksheet.write(row_num, 28, line.new_categ_six)
            worksheet.write(row_num, 29, line.new_desc_five)
            worksheet.write(row_num, 30, line.new_barcode)
            worksheet.write(row_num, 31, line.book_stock_qty)
            worksheet.write(row_num, 32, line.book_stock_rsp)
            worksheet.write(row_num, 33, line.physical_stock_qty)
            worksheet.write(row_num, 34, line.physical_stock_rsp)
            worksheet.write(row_num, 35, line.snapshot_qty)
            worksheet.write(row_num, 36, line.snapshot_rsp)
            worksheet.write(row_num, 37, line.dif_qty)
            worksheet.write(row_num, 38, line.mrp)
            worksheet.write(row_num, 39, line.rsp)
            worksheet.write(row_num, 40, line.cost_price)
            worksheet.write(row_num, 41, line.dif_rsp_amount)
            worksheet.write(row_num, 42, line.item_rate)
            worksheet.write(row_num, 43, line.book_stock_value)
            worksheet.write(row_num, 44, line.physical_stock_value)
            worksheet.write(row_num, 45, line.dif_stock_value)




            # Close the workbook
        workbook.close()

        # Get the content of the buffer
        buffer.seek(0)
        excel_data = buffer.getvalue()
        buffer.close()

        # Encode the data in base64
        encoded_data = base64.b64encode(excel_data)

        # Create an attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'POS_Audit_Based_Report_{fields.Date.today()}.xlsx',
            'type': 'binary',
            'datas': encoded_data,
            'store_fname': f'POS_Audit_Based_Report_{fields.Date.today()}.xlsx',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        # Return the action to download the file
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }


class HoAuditReportLine(models.Model):
    _name = 'ho.audit.report.line'

    ho_audit_report_id = fields.Many2one("ho.audit.report", string="audits")
    audit_site = fields.Char(string='Audit site')
    stock_point = fields.Char(string="Stock Point")
    audit_plan = fields.Char(string="Audit Plan")
    description = fields.Char(string="Description")
    start_date = fields.Date(string="Actual Start Date")
    remarks = fields.Char(string="Remarks")
    barcode = fields.Char(string="Barcode")
    snap_division = fields.Char(string="Family")
    snap_section = fields.Char(string="Category")
    snap_department = fields.Char(string="Class")
    snap_article = fields.Char(string="Brick")
    snap_categ_one = fields.Char(string="Snap Category1")
    snap_categ_two = fields.Char(string="Snap Category2")
    snap_categ_three = fields.Char(string="Snap Category3")
    snap_categ_four = fields.Char(string="Snap Category4")
    snap_categ_five = fields.Char(string="Snap Category5")
    snap_categ_six = fields.Char(string="Snap Category6")
    vendor = fields.Char(string="Vendor")
    new_division = fields.Char(string="New Family")
    new_section = fields.Char(string="New Category")
    new_department = fields.Char(string="New Class")
    new_article = fields.Char(string="New Brick")
    new_categ_one = fields.Char(string="New Category1")
    new_categ_two = fields.Char(string="New Category2")
    new_categ_three = fields.Char(string="New Category3")
    new_categ_four = fields.Char(string="New Category4")
    new_categ_five = fields.Char(string="New Category5")
    new_categ_six = fields.Char(string="New Category6")
    new_desc_five = fields.Char(string="New Desc5")
    new_barcode = fields.Char(string="New Barcode")
    book_stock_qty = fields.Float(string="Book Stock Qty")
    book_stock_rsp = fields.Float(string="Book Stock RSP")
    physical_stock_qty = fields.Float(string="Physical Stock Qty")
    physical_stock_rsp = fields.Float(string="Physical Stock RSP")
    snapshot_qty = fields.Float(string="Snapshot Qty")
    snapshot_rsp = fields.Float(string="Snapshot RSP")
    dif_qty = fields.Float(string="Difference Qty")
    mrp = fields.Float(string="MRP")
    rsp = fields.Float(string="RSP")
    cost_price = fields.Float(string="Cost Price")
    dif_rsp_amount = fields.Float(string="Differential RSP Amount")
    item_rate = fields.Float(string="Item Rate (Last Inward)")
    book_stock_value = fields.Float(string="Book Stock Value (Last Inward)")
    physical_stock_value = fields.Float(string="Physical Stock Value (Last Inward)")
    dif_stock_value = fields.Float(string="Difference Stock Value (Last Inward)")
    product_id = fields.Char(string="product")
