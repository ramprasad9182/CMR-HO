from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TransportCheck(models.Model):
    _name = 'transport.check'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    logistic_entry_number = fields.Char(string="Logistic Entry Number",readonly="1", copy=False, tracking=True)
    logistic_lr_date = fields.Date(string="Logistic LR Date", copy=False, tracking=True)
    logistic_lr_number = fields.Char(string="Logistic LR Number", copy=False, tracking=True)
    logistic_date = fields.Date(string="Logistic Date", copy=False, tracking=True)
    transporter = fields.Many2one('res.partner', 'Transporter', index=True, copy=False, tracking=True)
    consignment_number = fields.Char(string="Consignment", copy=False, tracking=True)
    po_order_id = fields.Many2one('purchase.order', string='Source PO', index=True, required=True,
                               ondelete='cascade', copy=False, tracking=True)
    product_id = fields.Many2one('product.template',string="Product", index=True, required=True, copy=False, tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('cancel', 'Cancelled')], string='State'
        , copy=False, index=True, readonly=True,default='draft',
        store=True, tracking=True,
        help=" * Draft: The Transport check is not confirmed yet.\n"
             " * sent: Transport check verified and sent to Delivery Check.\n"
           )
    no_of_bales = fields.Integer(string="No of Bales", tracking=True)
    item_details = fields.Text(string="Item Details", tracking=True, readonly=True)
    city = fields.Char(string="City", tracking=True)
    invoice_list = fields.Char(string="Invoice List", tracking=True)
    zone_id = fields.Many2one('placement.master.data', string='Zone', copy=False)

    @api.model
    def get_transport_check_info(self):
        upcoming_lr = self.search_count([('state', '=', 'sent')])
        return {
            'upcoming_lr_count': upcoming_lr,
        }

    def logistic_transport_check(self):
        for rec in self:
            product_details = "\n".join([line.product_id.display_name for line in rec.po_order_id.order_line])
            if rec.state == 'draft':
                rec.state = 'sent'

                delivery_check_data = self.env['delivery.check'].create({
                    'po_order_id': rec.po_order_id.id,
                    'logistic_entry_number': rec.logistic_entry_number,
                    'logistic_lr_date': rec.logistic_lr_date,
                    'logistic_date': rec.logistic_date,
                    'logistic_lr_number': rec.logistic_lr_number,
                    'no_of_bales': rec.no_of_bales,
                    'deliver_bales': rec.no_of_bales,
                    'transporter': rec.transporter.id,
                    'city': rec.city,
                    'product_id': rec.product_id.id,
                    'placements': rec.po_order_id.partner_id.vendor_zone.id,
                    'item_details': product_details,
                })

                return delivery_check_data

    def action_confirm(self):
        for rec in self:
            product_details = "\n".join([line.product_id.display_name for line in rec.po_order_id.order_line])
            rec.state = 'sent'
            rec.po_order_id.ho_status = 'delivery'

            delivery_check_data = self.env['delivery.check'].create({

                'po_order_id': rec.po_order_id.id,
                'logistic_entry_number': rec.logistic_entry_number,
                'logistic_lr_date':rec.logistic_lr_date,
                'logistic_date':rec.logistic_date,
                'logistic_lr_number':rec.logistic_lr_number,
                'no_of_bales':rec.no_of_bales,
                'deliver_bales': rec.no_of_bales,
                'overall_remaining_bales': rec.no_of_bales,
                'transporter':rec.transporter.id,
                'city':rec.city,
                'product_id': rec.product_id.id,
                'consignment_number': rec.consignment_number,
                'placements': rec.po_order_id.partner_id.vendor_zone.id,
                'item_details':product_details,
            })
            self.env.cr.commit()

            return {
                    'name': 'Purchase',
                    'res_model': 'purchase.order',
                    'view_mode': 'form',
                    'type': 'ir.actions.act_window',
                    'res_id': rec.po_order_id.id,
                }

    def reset_to_draft(self):
        picking_status = self.env['stock.picking'].sudo().search([('origin', '=', self.po_order_id.name)])
        delivery_status = self.env['delivery.check'].search([('logistic_entry_number','=',self.logistic_entry_number)])
        if delivery_status.state != 'delivery':
            for rec in self:
                if self.state == 'sent':
                    self.state = 'draft'
                delivery_check_data = self.env['delivery.check'].search([

                    ('po_order_id', '=', rec.po_order_id.id),
                    ('logistic_lr_date', '=', rec.logistic_lr_date),
                    ('logistic_lr_number', '=', rec.logistic_lr_number),
                    ('no_of_bales', '=', rec.no_of_bales),
                    ('consignment_number', '=', rec.consignment_number),
                ])
                delivery_check_data.unlink()
        else:
            raise ValidationError("Can not the Reset The Record already confirm.")


class DeliveryCheck(models.Model):
    _name = 'delivery.check'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = "logistic_lr_number"

    logistic_entry_number = fields.Char(string="Logistic Entry Number",readonly="1", copy=False, tracking=True)
    logistic_lr_date = fields.Date(string="Logistic LR Date", copy=False, tracking=True)
    logistic_lr_number = fields.Char(string="Logistic LR Number", copy=False, tracking=True)
    logistic_date = fields.Date(string="Logistic Date", copy=False, tracking=True)
    transporter = fields.Many2one('res.partner', 'Transporter', index=True, copy=False, tracking=True)
    consignment_number = fields.Char(string="Consignment", copy=False, tracking=True)
    po_order_id = fields.Many2one('purchase.order', string='Source PO', index=True, required=True,
                               ondelete='cascade', copy=False, tracking=True)
    product_id = fields.Many2one('product.template',string="Product", index=True, required=True, copy=False, tracking=True)
    delivery_date = fields.Date(string='Delivery Date', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('delivery', 'Delivered'),
        ('cancel', 'Cancelled')], string='State'
        , copy=False, index=True, readonly=True,default='draft',
        store=True, tracking=True,
        help=" * Draft: The Delivery check is not confirmed yet.\n"
             " * sent: Transport check verified and sent to Delivery Check.\n"
           )
    no_of_bales = fields.Integer(string="No Of Bales", copy=False, tracking=True)
    item_details = fields.Text(string="Item Details", copy=False, tracking=True, readonly=True)
    city = fields.Char(string="City", copy=False, tracking=True)
    invoice_entry = fields.Char(string="Invoice Entry", copy=False, tracking=True)
    partial_bales = fields.Integer(string="Received Bales", copy=False, tracking=True)
    deliver_bales = fields.Integer(string="Total Bales", copy=False, tracking=True)
    overall_remaining_bales = fields.Integer(string="Balance Bales")
    placements = fields.Many2one('placement.master.data',string="Placement", copy=False, tracking=True)
    delivery_ids = fields.One2many("delivery.barcode","delivery_id")
    zone_id = fields.Many2one('placement.master.data', string='Zone', copy=False)

    @api.model
    def get_delivery_check_info(self):
        shortage_count = self.search_count([('state', '=', 'draft')])
        delivery_count = self.search([('state', '=', 'delivery')])
        transferred_parcel = sum(delivery_count.mapped('partial_bales'))
        return {
            'delivery_count': len(delivery_count),
            'shortage_count': shortage_count,
            'transferred_bales': transferred_parcel
        }

    def _prepare_parcel_open(self, rec):
        open_parcels = []
        barcode_lines = self.delivery_ids.search([('delivery_id', '=', rec.id)])

        for barcode in barcode_lines:
            open_parcel_data = {
                'parcel_lr_no': rec.logistic_lr_number,
                'parcel_bale': rec.partial_bales,
                'parcel_po_no': rec.po_order_id.id,
                'parcel_transporter': rec.transporter.id,
                'barcode': barcode.barcode
            }
            open_parcels.append(open_parcel_data)
        created_parcels = self.env['open.parcel'].create(open_parcels)
        return created_parcels

    def action_confirm(self):
        if self.partial_bales <= 0:
            raise ValidationError("The number of Received Bales must be greater than one!")
        for rec in self:
            product_details = "\n".join([line.product_id.display_name for line in rec.po_order_id.order_line])
            rec.state = 'delivery'
            rec.delivery_date = fields.Date.today()
            total_partial_bales = 0
            existing_records_same_lr_number = self.search([
                ('logistic_entry_number', '=', self.logistic_entry_number), ('state', '=', 'delivery')])

            total_partial_bales += sum(rec.partial_bales for rec in existing_records_same_lr_number)
            remaining_bales = rec.deliver_bales - total_partial_bales
            rec.overall_remaining_bales = remaining_bales
            total_barcodes = self.delivery_ids.search_count(
                [('delivery_id.logistic_lr_number', '=', rec.logistic_lr_number)])
            if rec.deliver_bales != total_partial_bales:
                delivery_barcode_vals = []
                if rec.deliver_bales - rec.overall_remaining_bales == 0:
                    for i in range(1, rec.partial_bales + 1):
                        barcode = f"{rec.logistic_lr_number}-{i}"
                        delivery_barcode_vals.append({
                            'serial_no': i,
                            'barcode': barcode,
                            'delivery_id': rec.id,
                        })
                    rec.delivery_ids = [(0, 0, vals) for vals in delivery_barcode_vals]
                    rec._prepare_parcel_open(rec)

                else:
                    k = self.delivery_ids.search_count(
                        [('delivery_id.logistic_lr_number', '=', rec.logistic_lr_number)])
                    for i in range(k + 1, k + rec.partial_bales + 1):
                        barcode = f"{rec.logistic_lr_number}-{i}"
                        delivery_barcode_vals.append({
                            'serial_no': i,
                            'barcode': barcode,
                            'delivery_id': rec.id,
                        })

                    rec.delivery_ids = [(0, 0, vals) for vals in delivery_barcode_vals]
                    rec._prepare_parcel_open(rec)

                delivery_check_data = self.env['delivery.check'].create({
                    'po_order_id': rec.po_order_id.id,
                    'logistic_entry_number': rec.logistic_entry_number,
                    'logistic_lr_date': rec.logistic_lr_date,
                    'logistic_date': rec.logistic_date,
                    'logistic_lr_number': rec.logistic_lr_number,
                    'no_of_bales': rec.no_of_bales,
                    'deliver_bales': rec.no_of_bales,
                    'overall_remaining_bales': remaining_bales,
                    'transporter': rec.transporter.id,
                    'city': rec.city,
                    'product_id': rec.product_id.id,
                    'placements': rec.zone_id.id,
                    'item_details':product_details,
                })

                return delivery_check_data,
            elif total_barcodes != rec.deliver_bales:
                k = self.delivery_ids.search_count([('delivery_id.logistic_lr_number', '=', rec.logistic_lr_number)])
                delivery_barcode_vals = []
                for i in range(k + 1, k + rec.partial_bales + 1):
                    barcode = f"{rec.logistic_lr_number}-{i}"
                    delivery_barcode_vals.append({
                        'serial_no': i,
                        'barcode': barcode,
                        'delivery_id': rec.id,
                    })
                rec.delivery_ids = [(0, 0, vals) for vals in delivery_barcode_vals]
                rec._prepare_parcel_open(rec)
            else:
                delivery_barcode_vals = []
                for i in range(rec.partial_bales):
                    barcode = f"{rec.logistic_lr_number}-{i + 1}"
                    delivery_barcode_vals.append({
                        'serial_no': i + 1,
                        'barcode': barcode,
                        'delivery_id': rec.id,
                    })

                rec.delivery_ids = [(0, 0, vals) for vals in delivery_barcode_vals]
                rec._prepare_parcel_open(rec)




    def logistic_delivery_check(self):
        for rec in self:
            if rec.state == 'draft':
                rec.state = 'delivery'

    def print_barcodes(self):

        report_name = 'cmr_customizations.delivery_check_barcode'
        return {
            'type': 'ir.actions.report',
            'report_name': report_name,
            'report_type': 'qweb-pdf',
        }

    @api.depends("partial_bales")
    def _compute_remaining_bales(self):
        for rec in self:
            rec.remaining_bales = rec.deliver_bales - rec.partial_bales

    @api.constrains('partial_bales')
    def _check_partial_bales(self):
        for rec in self:
            if rec.partial_bales < 0 or rec.partial_bales > rec.overall_remaining_bales:
                raise UserError(_("The number of received bales must be greater than one!."))

    def get_first_six_characters(self, text):
        return text[:6] if text else ''


class DeliveryBarcode(models.Model):
    _name = 'delivery.barcode'

    @api.model
    def create(self, vals_list):
        delivery_check_seq = self.env['nhcl.master.sequence'].search(
            [('nhcl_code', '=', 'cmr.delivery'), ('nhcl_state', '=', 'activate')], limit=1)
        if not delivery_check_seq:
            raise ValidationError(_('The Delivery Check Sequence is not specified in the sequence master. "Please configure it!.'))

        if vals_list.get('sequence', 'New') == 'New':
            vals_list['sequence'] = self.env['ir.sequence'].next_by_code('cmr.delivery') or 'New'
        res = super(DeliveryBarcode, self).create(vals_list)
        return res

    sequence = fields.Char(string='Barcode', copy=False, default=lambda self: _("New"))
    delivery_id = fields.Many2one('delivery.check', string="LR Number")
    barcode = fields.Char(string="Sequence")
    serial_no = fields.Integer(string='S.NO')







