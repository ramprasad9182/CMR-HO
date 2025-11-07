from odoo import models,fields,api,_
from odoo.exceptions import ValidationError


class HoAuditReport(models.Model):
    _name = 'ho.audit.report'

    from_date = fields.Datetime('From Date')
    to_date = fields.Datetime('To Date')
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company')
    plan_id = fields.Many2one('stock.inventory', string='Plan')
    # plan_dup = fields.Many2one('stock.inventory',string='Plan Dup',related='plan_id.plan_name')
    ho_audit_report_ids = fields.One2many('ho.audit.report.line', 'ho_audit_report_id')



    # def ho_audit_report(self):
    #     for report in self:
    #         if not report.nhcl_store_id:
    #             raise ValidationError("Please select at least one Company")
    #
    #         # Clear previous lines
    #         report.ho_audit_report_ids = [(5, 0, 0)]
    #
    #         # Build domain for stock.inventory
    #         inventory_domain = []
    #         if report.plan_id:
    #             inventory_domain.append(('id', '=', report.plan_id.id))
    #         if report.from_date and report.to_date:
    #             inventory_domain += [
    #                 ('from_date_range', '<=', report.from_date),
    #                 ('to_date_range', '>=', report.to_date)
    #             ]
    #
    #         # Fetch inventories
    #         inventories = self.env['stock.inventory'].search(inventory_domain)
    #
    #         if not inventories:
    #             continue  # No inventories in range
    #
    #         # Fetch all related lines at once
    #         inventory_lines = self.env['stock.inventory.line'].search([
    #             ('inventory_id', 'in', inventories.ids)
    #         ])
    #
    #         # Fetch all lot info in one go to reduce load
    #         lot_names = [line.prod_lot_id.name for line in inventory_lines if line.prod_lot_id]
    #         lots = {lot.name: lot for lot in self.env['stock.lot'].search([('name', 'in', lot_names)])}
    #
    #         lines_to_create = []
    #         for line in inventory_lines:
    #             inv = line.inventory_id
    #             product = line.product_id
    #
    #             # Snap levels
    #             snap_division = snap_section = snap_department = snap_article = ''
    #             if product and product.categ_id:
    #                 levels = []
    #                 current = product.categ_id
    #                 while current:
    #                     levels.append(current.name)
    #                     current = current.parent_id
    #                 levels = levels[::-1]  # top → bottom
    #
    #                 snap_division = levels[0] if len(levels) >= 1 else ''
    #                 snap_section = levels[1] if len(levels) >= 2 else ''
    #                 snap_department = levels[2] if len(levels) >= 3 else ''
    #                 snap_article = levels[3] if len(levels) >= 4 else ''
    #
    #             # Lot info
    #             new_desc_five_value = ''
    #             physical_stock_rsp_value = 0.0
    #             mrp_value = 0.0
    #             cp_value = 0.0
    #             if line.prod_lot_id and line.prod_lot_id.name in lots:
    #                 lot = lots[line.prod_lot_id.name]
    #                 new_desc_five_value = lot.description_1.name or ''
    #                 physical_stock_rsp_value = lot.rs_price or 0.0
    #                 mrp_value = lot.mr_price or 0.0
    #                 cp_value = lot.cost_price or 0.0
    #
    #             # Last inward rate for product
    #             last_inward_rate = 0.0
    #             if product:
    #                 last_lot = self.env['stock.lot'].search(
    #                     [('product_id', '=', product.id), ('rs_price', '!=', False)],
    #                     order='create_date desc',
    #                     limit=1
    #                 )
    #                 if last_lot:
    #                     last_inward_rate = last_lot.rs_price or 0.0
    #
    #             # Prepare audit line
    #             lines_to_create.append((0, 0, {
    #                 'product_id': product.nhcl_display_name if product else False,
    #                 'audit_site': inv.company_id.name if inv.company_id else '',
    #                 'stock_point': inv.warehouse_id.name if inv.warehouse_id else '',
    #                 'audit_plan': inv.plan_name if inv.plan_name else '',
    #                 'description': inv.plan_name if inv.plan_name else '',
    #                 'start_date': inv.create_date or '',
    #                 'remarks': inv.plan_name or '',
    #                 'barcode': line.prod_lot_id.name if line.prod_lot_id else '',
    #                 'snap_division': snap_division,
    #                 'snap_section': snap_section,
    #                 'snap_department': snap_department,
    #                 'snap_article': snap_article,
    #                 'physical_stock_qty': line.theoretical_qty or 0.0,
    #                 'snapshot_qty': line.qty_done or 0.0,
    #                 'dif_qty': line.difference_qty or 0.0,
    #                 'physical_stock_rsp': physical_stock_rsp_value,
    #                 'snapshot_rsp': physical_stock_rsp_value,
    #                 'dif_rsp_amount': physical_stock_rsp_value - physical_stock_rsp_value,
    #                 'new_desc_five': new_desc_five_value,
    #                 'rsp': physical_stock_rsp_value,
    #                 'mrp': mrp_value,
    #                 'cost_price': cp_value,
    #                 'book_stock_qty': line.theoretical_qty or 0.0,
    #                 'new_division': snap_division,
    #                 'new_section': snap_section,
    #                 'new_department': snap_department,
    #                 'new_article': snap_article,
    #                 'item_rate': last_inward_rate,
    #             }))
    #
    #         # Create all audit lines at once
    #         report.ho_audit_report_ids = lines_to_create
    #
    #         # Calculate dif_rsp_amount safely if needed
    #         for audit_line in report.ho_audit_report_ids:
    #             audit_line.dif_rsp_amount = (audit_line.physical_stock_rsp or 0.0) - (audit_line.snapshot_rsp or 0.0)

    # def action_to_reset(self):
    #     for report in self:
    #         report.ho_audit_report_ids = [(5, 0, 0)]

    # def get_excel_sheet(self):
    #     pass







class HoAuditReportLine(models.Model):
    _name = 'ho.audit.report.line'

    ho_audit_report_id = fields.Many2one("ho.audit.report", string="audits")
    audit_site = fields.Char(string='Audit site')
    stock_point = fields.Char(string="Stock Point")
    audit_plan = fields.Char(string="Stock Point")
    description = fields.Char(string="Description")
    start_date = fields.Date(string="Actual Start Date")
    remarks = fields.Char(string="Remarks")
    barcode = fields.Char(string="Barcode")
    snap_division = fields.Char(string="Snap Division")
    snap_section = fields.Char(string="Snap Section")
    snap_department = fields.Char(string="Snap Department")
    snap_article = fields.Char(string="Snap Article")
    snap_categ_one = fields.Char(string="Snap Category1")
    snap_categ_two = fields.Char(string="Snap Category2")
    snap_categ_three = fields.Char(string="Snap Category3")
    snap_categ_four = fields.Char(string="Snap Category4")
    snap_categ_five = fields.Char(string="Snap Category5")
    snap_categ_six = fields.Char(string="Snap Category6")
    vendor = fields.Char(string="Vendor")
    new_division = fields.Char(string="New Division")
    new_section = fields.Char(string="New Section")
    new_department = fields.Char(string="New Department")
    new_article = fields.Char(string="New Article")
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
