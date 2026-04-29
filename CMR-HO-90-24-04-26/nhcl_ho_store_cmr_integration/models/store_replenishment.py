import requests
from odoo.exceptions import ValidationError
from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)


class StoreReplenishment(models.Model):
    _name = 'store.replenishment'
    _description = 'Store Replenishment'

    name = fields.Char(string="Reference",required=True,copy=False,readonly=True,default='New')
    store_id = fields.Many2one('res.company', default=lambda self:self.env.company.id)
    repl_type = fields.Selection([('regular', 'Regular'),('fashion', 'Fashions')], string="Type")
    product_tmpl_id = fields.Many2one('product.template', string='Product')
    product_tmpl_ids = fields.Many2many('product.template', 'store_repl_product_rel', string="Products")
    line_ids = fields.One2many('store.replenishment.line','repl_id',
        string="Replenishment Lines")
    price_from = fields.Float(compute='_compute_parent_values', store=True)
    price_to = fields.Float(compute='_compute_parent_values', store=True)
    min_qty = fields.Float(string='Min Qty', compute='_compute_parent_values', store=True)
    max_qty = fields.Float(string='Max Qty', compute='_compute_parent_values', store=True)
    onhand_qty = fields.Float(string='On Hand Qty', compute='_compute_parent_values', store=True)
    differ_qty = fields.Float(string='Differ Qty', compute='_compute_parent_values', store=True)
    indent_qty = fields.Float(string='Indent Qty', compute='_compute_parent_values', store=True)

    update_replication = fields.Boolean(string="Creation Status")
    update_status = fields.Boolean(string="Update status")
    delete_status = fields.Boolean(string="Delete status")
    replenishment_id = fields.One2many('nhcl.replenishment.line', 'nhcl_replenishment_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)
    warning_message = fields.Char(compute='_compute_warning_message')

    @api.onchange('repl_type')
    @api.constrains('repl_type')
    def _onchange_load_products(self):
        if self.repl_type != 'fashion' or not self.store_id:
            return
        ProductTemplate = self.env['product.template']
        Repl = self.env['store.replenishment']
        # ✅ All fashion templates
        all_templates = ProductTemplate.search([('repl_type', '=', 'fashion')])
        # ✅ Already used templates for this store
        existing_repls = Repl.search([
            ('store_id', '=', self.store_id.id),
            ('repl_type', '=', 'fashion')
        ])
        used_template_ids = existing_repls.mapped('product_tmpl_ids').ids
        # ✅ Remaining templates
        available_templates = all_templates.filtered(lambda t: t.id not in used_template_ids)
        self.product_tmpl_ids = [(6, 0, available_templates.ids)]

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def open_form_view(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Open MBQ',
            'res_model': 'store.replenishment',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.view_store_replenishment_form').id,
            'res_id': self.id,
            'target': 'current',
        }

    @api.depends(
        'line_ids.price_from',
        'line_ids.price_to',
        'line_ids.min_qty',
        'line_ids.max_qty',
        'line_ids.onhand_qty',
        'line_ids.differ_qty',
        'line_ids.indent_qty'
    )
    def _compute_parent_values(self):
        for rec in self:
            lines = rec.line_ids
            rec.update({
                'price_from': sum(lines.mapped('price_from')) if lines else 0,
                'price_to': sum(lines.mapped('price_to')) if lines else 0,
                'min_qty': sum(lines.mapped('min_qty')),
                'max_qty': sum(lines.mapped('max_qty')),
                'onhand_qty': sum(lines.mapped('onhand_qty')),
                'differ_qty': sum(lines.mapped('differ_qty')),
                'indent_qty': sum(lines.mapped('indent_qty')),
            })

    @api.constrains('store_id', 'product_tmpl_id', 'product_tmpl_ids', 'repl_type')
    def _check_unique_company_product(self):
        for rec in self:
            if not rec.store_id:
                continue
            # ✅ REGULAR
            if rec.repl_type == 'regular':
                if not rec.product_tmpl_id:
                    continue
                domain = [
                    ('store_id', '=', rec.store_id.id),
                    ('repl_type', '=', 'regular'),
                    ('product_tmpl_id', '=', rec.product_tmpl_id.id),
                    ('id', '!=', rec.id)
                ]
                if self.search_count(domain):
                    raise ValidationError("Regular replenishment already exists for this Store and Product!")
            # ✅ FASHION
            elif rec.repl_type == 'fashion':
                if not rec.product_tmpl_ids:
                    continue
                domain = [
                    ('store_id', '=', rec.store_id.id),
                    ('repl_type', '=', 'fashion'),
                    ('product_tmpl_ids', 'in', rec.product_tmpl_ids.ids),
                    ('id', '!=', rec.id)
                ]
                if self.search_count(domain):
                    raise ValidationError(
                        "Fashion replenishment already exists for one of the selected Products!"
                    )

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']

        # 🔒 Lock table to avoid duplicate nhcl_id
        self.env.cr.execute("SELECT id FROM store_replenishment FOR UPDATE")

        # Get current max once
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM store_replenishment")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        for i, vals in enumerate(vals_list, start=1):
            vals['nhcl_id'] = max_nhcl_id + i
            if vals.get('name', 'New') == 'New':
                vals['name'] = seq.next_by_code('store.replenishment.seq') or 'New'
        records = super().create(vals_list)
        return records

    def get_stores_data(self):
        for line in self:
            replication_data = []
            existing_store_ids = line.replenishment_id.mapped('store_id.id')
            ho_store_id = self.env['nhcl.ho.store.master'].sudo().search(
                [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True),
                 ('nhcl_store_name.company_id.name', '=', line.store_id.name)])
            for rec in line.replenishment_id:
                if rec.nhcl_terminal_ip not in ho_store_id.mapped('nhcl_terminal_ip'):
                    rec.unlink()
                elif rec.nhcl_api_key not in ho_store_id.mapped('nhcl_api_key'):
                    rec.unlink()
            for i in ho_store_id:
                for j in i.nhcl_store_data_id:
                    if j.model_id.name == 'Store Replenishment' and j.nhcl_line_data == True:
                        if i.nhcl_store_name.id in existing_store_ids:
                            continue
                        vals = {
                            'store_id': i.nhcl_store_name.id,
                            'nhcl_terminal_ip': i.nhcl_terminal_ip,
                            'nhcl_port_no': i.nhcl_port_no,
                            'nhcl_api_key': i.nhcl_api_key,
                            'status': i.nhcl_active,
                            'master_store_id': i.id
                        }
                        replication_data.append((0, 0, vals))
            line.update({'replenishment_id': replication_data})

    def send_replenishment_data_to_store(self):
        for line in self.replenishment_id:
            if not line.date_replication:
                store_ip = line.nhcl_terminal_ip
                store_port = line.nhcl_port_no
                store_api_key = line.nhcl_api_key
                headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
                replenishment_lines = []
                for replenishment in self.line_ids:
                    replenishment_vals = {
                        'price_from': replenishment.price_from,
                        'price_to': replenishment.price_to,
                        'min_qty': replenishment.min_qty,
                        'max_qty': replenishment.max_qty,

                    }
                    replenishment_lines.append((0, 0, replenishment_vals))
                if self.repl_type != 'fashion':
                    store_product_search_url = f"http://{store_ip}:{store_port}/api/product.template/search"
                    store_product_domain = [('nhcl_id', '=', self.product_tmpl_id.nhcl_id)]
                    store_product_url = f"{store_product_search_url}?domain={store_product_domain}"
                    store_product_data = requests.get(store_product_url,headers=headers_source)
                    store_product_data.raise_for_status()
                    product_data = store_product_data.json()
                    store_product = product_data.get("data", [])
                    product_id = False
                    if store_product:
                        product_id = store_product[0]['id']
                    replenishment_data = {
                        'repl_type': self.repl_type,
                        # 'nhcl_id': self.nhcl_id,
                        'product_tmpl_id': product_id,
                        'line_ids': replenishment_lines,
                    }
                else:
                    replenishment_product_ids = []
                    for replenishment_product_tmpl_id in self.product_tmpl_ids:
                        store_product_search_url = f"http://{store_ip}:{store_port}/api/product.template/search"
                        store_product_domain = [('nhcl_id', '=', replenishment_product_tmpl_id.nhcl_id)]
                        store_product_url = f"{store_product_search_url}?domain={store_product_domain}"
                        store_product_data = requests.get(store_product_url, headers=headers_source)
                        store_product_data.raise_for_status()
                        product_data = store_product_data.json()
                        store_product = product_data.get("data", [])
                        if not store_product:
                            continue
                        product_tmpl_name = store_product[0]
                        replenishment_product_ids.append(product_tmpl_name["id"])
                        replenishment_data = {
                            'repl_type': self.repl_type,
                            # 'nhcl_id': self.nhcl_id,
                            'line_ids': replenishment_lines,
                            'product_tmpl_ids': replenishment_product_ids,
                        }

                try:
                    store_creation_url = f"http://{store_ip}:{store_port}/api/store.replenishment/create"
                    stores_data = requests.post(store_creation_url, headers=headers_source, json=[replenishment_data])
                    stores_data.raise_for_status()
                    # Raise an exception for HTTP errors
                    stores_data.raise_for_status()

                    # Access the JSON content from the response
                    response_json = stores_data.json()

                    # Access specific values from the response (e.g., "message" or "responseCode")
                    message = response_json.get("message", "No message provided")
                    response_code = response_json.get("responseCode", "No response code provided")
                    if response_json.get("success") == False:
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                            'add', 'failure', message)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                      self.id, 200, 'add', 'failure',
                                                                                      message)

                    else:
                        line.date_replication = True
                        self.update_replication = True
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                            'add', 'success',
                                                                            f"Successfully create Replenishment {self.name}")
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                      self.id, 200, 'add', 'success',
                                                                                      f"Successfully create Replenishment {self.name}")
                except requests.exceptions.RequestException as e:
                    line.date_replication = False
                    self.update_replication = False
                    if line.master_store_id.nhcl_sink == False:
                        line.master_store_id.create_cmr_replication_log('product.template',
                                                                        self.id, 500, 'add', 'failure',
                                                                        e)
                    else:
                        line.master_store_id.create_cmr_old_store_replication_log('product.template',
                                                                                  self.id, 500, 'add', 'failure',
                                                                                  e)



class StoreReplenishmentLine(models.Model):
    _name = 'store.replenishment.line'
    _description = 'Store Replenishment Line'

    repl_id = fields.Many2one('store.replenishment',required=True,ondelete='cascade')
    product_tmpl_id = fields.Many2one('product.template',related='repl_id.product_tmpl_id')
    price_from = fields.Float(required=True)
    price_to = fields.Float(required=True)
    min_qty = fields.Float()
    max_qty = fields.Float()
    onhand_qty = fields.Float(compute='_compute_onhand')
    differ_qty = fields.Float(compute='_compute_differ')
    indent_qty = fields.Float(compute='_compute_indent_qty')
    to_be_qty = fields.Float(compute='_compute_to_be')
    price_range = fields.Char(string="Price Range", compute="_compute_price_range", store=True)

    @api.depends('price_from', 'price_to')
    def _compute_price_range(self):
        for rec in self:
            if rec.price_from or rec.price_to:
                rec.price_range = f"{int(rec.price_from)}-{int(rec.price_to)}"
            else:
                rec.price_range = False


    def _compute_indent_qty(self):
        POLine = self.env['purchase.order.line']
        for rec in self:
            company = rec.repl_id.store_id
            if not company:
                rec.indent_qty = 0
                continue
            if rec.repl_id.repl_type == 'regular':
                template_ids = [rec.repl_id.product_tmpl_id.id]
            else:
                template_ids = rec.repl_id.product_tmpl_ids.ids
            if not template_ids:
                rec.indent_qty = 0
                continue
            po_lines = POLine.search([('product_template_id', 'in', template_ids),('mbq_plan','=',rec.price_range),
                                      ('company_id.nhcl_company_bool','=',False),('order_id.upload_type','=','normal')])
            rec.indent_qty = sum(po_lines.mapped('product_qty'))


    def _compute_onhand(self):
        Quant = self.env['stock.quant']
        Location = self.env['stock.location']
        for rec in self:
            company = rec.repl_id.store_id
            if not company:
                rec.onhand_qty = 0
                continue
            # ⭐ Decide templates
            if rec.repl_id.repl_type == 'regular':
                template_ids = [rec.repl_id.product_tmpl_id.id]
            else:
                template_ids = rec.repl_id.product_tmpl_ids.ids
            if not template_ids:
                rec.onhand_qty = 0
                continue
            locations = Location.search([
                ('company_id', '=', company.id),
                ('usage', '=', 'internal')])
            quants = Quant.search([
                ('location_id', 'in', locations.ids),
                ('product_id.product_tmpl_id', 'in', template_ids),
                ('lot_id.rs_price', '>=', rec.price_from),
                ('lot_id.rs_price', '<=', rec.price_to),
            ])
            rec.onhand_qty = sum(quants.mapped('quantity'))

    def _compute_differ(self):
        for rec in self:
            rec.differ_qty = rec.max_qty - rec.onhand_qty

    def _compute_to_be(self):
        for rec in self:
            rec.to_be_qty = rec.differ_qty - rec.indent_qty

class NhclReplenishmentLine(models.Model):
    _name = 'nhcl.replenishment.line'
    _description = "Replenishment Line"

    nhcl_replenishment_id = fields.Many2one('store.replenishment', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update status")
    delete_status = fields.Boolean(string="Delete status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')



class ReplenishmentWizard(models.TransientModel):
    _name = 'replenishment.wizard'
    _description = 'Replenishment Wizard'

    product_tmpl_id = fields.Many2one('product.template')
    approval_line_id = fields.Many2one('approval.product.line')
    line_ids = fields.One2many('replenishment.wizard.line', 'wizard_id')

    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        product_tmpl_id = self.env.context.get('default_product_tmpl_id')
        if not product_tmpl_id:
            return res

        ReplLine = self.env['store.replenishment.line'].sudo()
        Quant = self.env['stock.quant']
        Location = self.env['stock.location']
        POLine = self.env['purchase.order.line'].sudo()

        # -----------------------------
        # FETCH DATA
        # -----------------------------
        lines = ReplLine.search([
            ('product_tmpl_id', '=', product_tmpl_id)
        ])

        if not lines:
            return res

        # price buckets
        price_ranges = set((l.price_from, l.price_to) for l in lines)

        # -----------------------------
        # MAIN COMPANY
        # -----------------------------
        main_company = self.env['res.company'].search([
            ('nhcl_company_bool', '=', True)
        ], limit=1)

        main_stock_map = {}
        ho_indent_map = {}

        # -----------------------------
        # MAIN COMPANY STOCK
        # -----------------------------
        if main_company:
            locations = Location.search([
                ('company_id', '=', main_company.id),
                ('usage', '=', 'internal')
            ])

            quants = Quant.search([
                ('location_id', 'in', locations.ids),
                ('product_id.product_tmpl_id', '=', product_tmpl_id),
            ])

            for q in quants:
                price = q.lot_id.rs_price or 0

                for (pf, pt) in price_ranges:
                    if pf <= price <= pt:
                        main_stock_map[(pf, pt)] = main_stock_map.get((pf, pt), 0) + q.quantity
        # -----------------------------
        # HO INDENT (PO PENDING QTY)
        # -----------------------------
        if main_company:
            po_lines = POLine.search([('company_id', '=', main_company.id),('product_id.product_tmpl_id', '=', product_tmpl_id),
                ('state', 'in', ['purchase', 'done']),('order_id.nhcl_po_type','in',['ho_operation','direct_po'])])
            for pol in po_lines:
                pending_qty = pol.product_qty - pol.qty_received
                if pending_qty <= 0:
                    continue
                # price fallback
                price = pol.rsp or 0
                for (pf, pt) in price_ranges:
                    if pf <= price <= pt:
                        ho_indent_map[(pf, pt)] = ho_indent_map.get((pf, pt), 0) + pending_qty
        # -----------------------------
        # GROUPING
        # -----------------------------
        grouped = {}

        for line in lines:
            key = (line.price_from, line.price_to)
            if key not in grouped:
                grouped[key] = {
                    'price_range': line.price_range,
                    'price_from': line.price_from,
                    'price_to': line.price_to,
                    'min_qty': line.min_qty,
                    'max_qty': line.max_qty,
                    'onhand_qty': 0,
                    'indent_qty': line.indent_qty,
                    'ho_indent_qty': 0,
                    'main_onhand_qty': 0,
                }
            grouped[key]['onhand_qty'] += line.onhand_qty
        # -----------------------------
        # ADD MAIN STOCK + HO INDENT
        # -----------------------------
        for key in grouped:
            grouped[key]['main_onhand_qty'] += main_stock_map.get(key, 0)
            grouped[key]['ho_indent_qty'] += ho_indent_map.get(key, 0)
        # ----------------------------
        # BUILD WIZARD LINES
        # -----------------------------
        wizard_lines = []

        for vals in grouped.values():
            differ = vals['max_qty'] - vals['onhand_qty']
            to_be = differ - vals['indent_qty']
            wizard_lines.append((0, 0, {
                'price_range': vals['price_range'],
                'price_from': vals['price_from'],
                'price_to': vals['price_to'],
                'min_qty': vals['min_qty'],
                'max_qty': vals['max_qty'],
                'onhand_qty': vals['onhand_qty'],
                'differ_qty': differ,
                'indent_qty': vals['indent_qty'],
                'to_be_qty': to_be,
                'ho_indent_qty': vals['ho_indent_qty'],
                'main_onhand_qty': vals['main_onhand_qty'],
            }))
        res['line_ids'] = wizard_lines
        return res

    def action_apply_to_po(self):
        self.ensure_one()
        po_line = self.env['approval.product.line'].browse(self.env.context.get('default_approval_line_id'))
        selected_lines = self.line_ids.filtered(lambda l: l.select_line)
        if not selected_lines:
            raise ValidationError("Please select at least one line.")
        if len(selected_lines) > 1:
            raise ValidationError("Please select at only one line.")
        # sort by price
        selected_lines = selected_lines.sorted(key=lambda l: l.price_from)
        # (optional) continuity check
        for i in range(len(selected_lines) - 1):
            if selected_lines[i].price_to + 1 != selected_lines[i + 1].price_from:
                raise ValidationError("Selected ranges must be continuous.")
        price_from = selected_lines[0].price_from
        price_to = selected_lines[-1].price_to
        mbq_plan_val = selected_lines.price_range
        # ✅ ONLY UPDATE EXISTING LINE
        po_line.write({
            'mbq_plan': mbq_plan_val,
        })
        return {'type': 'ir.actions.act_window_close'}

    def action_close_wizard(self):
        self.ensure_one()
        selected_lines = self.line_ids.filtered(lambda l: l.select_line)
        if not selected_lines:
            raise ValidationError("At least one line must be selected before closing.")
        return {'type': 'ir.actions.act_window_close'}


class ReplenishmentWizardLine(models.TransientModel):
    _name = 'replenishment.wizard.line'
    _description = 'Replenishment Wizard Line'

    wizard_id = fields.Many2one('replenishment.wizard')
    price_range = fields.Char(string="Price Range")
    price_from = fields.Float()
    price_to = fields.Float()
    min_qty = fields.Float()
    max_qty = fields.Float()
    onhand_qty = fields.Float()
    differ_qty = fields.Float()
    indent_qty = fields.Float()
    to_be_qty = fields.Float()
    ho_indent_qty = fields.Float(string="HO Indent Qty")
    main_onhand_qty = fields.Float(string="HO Onhand Qty")
    select_line = fields.Boolean(string="Select")
