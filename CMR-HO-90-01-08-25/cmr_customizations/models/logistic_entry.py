from odoo import models,fields,api,_
from odoo.exceptions import ValidationError
from datetime import datetime, date
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LogisticScreen(models.Model):
    _name = 'logistic.screen.data'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'lr_number'

    def _get_logistic_year_selection(self):
        current_year = datetime.now().year
        return [(str(year), str(year)) for year in range(current_year - 2, current_year + 3)]

    name = fields.Char(string="Logistic No", copy=False, index=True, default=lambda self: _('New'), tracking=True)
    vendor = fields.Many2one('res.partner', string="Vendor", copy=False, tracking=True)
    po_number = fields.Many2one('purchase.order', string="PO Number", copy=False, tracking=True)
    logistic_date = fields.Date(string="Logistic Date", copy=False, tracking=True, default=lambda self: date.today())
    lr_number = fields.Char(string="LR Number", copy=False, tracking=True)
    lr_date = fields.Date(string="LR Date", copy=False, tracking=True)
    transporter = fields.Many2one('res.partner', string='Transporter', copy=False, tracking=True)
    transporter_gst = fields.Char(related='transporter.vat', string='Transporter GST', copy=False, tracking=True)
    no_of_bales = fields.Integer(string="No Of Bales", copy=False, tracking=True)
    due_date = fields.Date(string="Due Date", copy=False, tracking=True)
    way_bill_no = fields.Char(string="Way Bill No", copy=False, tracking=True)
    se_branch = fields.Many2one('res.partner', string="SE Branch", copy=False, tracking=True,
                                default=lambda self: self._default_branch())
    placements = fields.Many2one('placement.master.data', string="Placement", copy=False, tracking=True,
                                 default=lambda self: self._default_basement())
    remarks = fields.Text(string="Remarks", copy=False, tracking=True)
    finencial_year = fields.Date(string="Fin Year", copy=False, tracking=True)
    fin_year = fields.Selection(selection=_get_logistic_year_selection,
                                string="Fin Year", copy=False, tracking=True,
                                default=lambda self: str(datetime.now().year))
    delivery_date = fields.Date(string="Delivery Date", copy=False, tracking=True)
    no_of_invoices = fields.Integer(string="No Of Invoices", copy=False, tracking=True)
    logistic_values = fields.Integer(string="Logistic Value", copy=False, tracking=True)
    logistic_type = fields.Selection([
        ('Road', 'By Road'),
        ('Hand', 'By Hand'),
        ('Courier', 'By Courier'),
    ], string="Logistic Type", copy=False, tracking=True)
    city = fields.Char(string="City", copy=False, tracking=True)
    consignor = fields.Many2one('res.partner', string="Consignor", copy=False, tracking=True)
    address = fields.Char(string="Address", copy=False, tracking=True)
    gst_no = fields.Char(string="GST No", copy=False, tracking=True)
    charges = fields.Float(string="Charges", copy=False, tracking=True)
    invoice_quantity = fields.Float(string="Invoice Quantity", copy=False, tracking=True, default="1")
    no_of_quantity = fields.Float(string="No Of Quantity", copy=False, tracking=True)
    product_id = fields.Many2one('product.template', string="Product", index=True, copy=False,
                                 tracking=True,
                                 default=lambda self: self._default_product_id())
    remaining_quantity = fields.Float(string="Remaining Quantity", copy=False, tracking=True,
                                      compute='_compute_remaining_quantity')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Logistic Entry Done'),
        ('cancel', 'Cancelled')], string='State'
        , copy=False, index=True, readonly=True, default='draft',
        store=True, tracking=True,
        help=" * Draft: The Transport check is not confirmed yet.\n"
             " * sent: Transport check verified and sent to Delivery Check.\n")
    logistic_vendor = fields.Many2one('res.partner', string="Agent", copy=False, domain=[('group_contact.name','=','Agent')])
    zone_id = fields.Many2one('placement.master.data', string='Zone', copy=False)

    @api.constrains('way_bill_no')
    def _check_unique_way_bill_no(self):
        for record in self:
            existing_records = self.env['logistic.screen.data'].search([('way_bill_no', '=', record.way_bill_no),('id', '!=', record.id)])
            if existing_records:
                raise ValidationError('The Way Bill Number must be unique!.')



    # @api.constrains('lr_number')
    # def _check_unique_lr_number(self):
    #     for record in self:
    #         existing_records = self.env['logistic.screen.data'].search(
    #             [('lr_number', '=', record.lr_number), ('id', '!=', record.id)])
    #         if existing_records:
    #             raise ValidationError('The Way LR Number Must Be Unique!.')

    @api.model
    def get_logistic_info(self):
        logistic_count = self.search_count([('state', '=', 'done')])
        return {
            'total_logistic': logistic_count
        }

    @api.model
    def create(self, vals_list):
        def get_unique_sequence(sequence_code):
            while True:
                seq_number = self.env['ir.sequence'].next_by_code(sequence_code) or 'New'
                if not self.env['logistic.screen.data'].search([('name', '=', seq_number)]):
                    return seq_number
                else:
                    # If the sequence number is already used, log a warning and regenerate
                    logger.warning(f"Sequence number {seq_number} already exists. Regenerating...")

        if vals_list.get('name', 'New') == 'New':
            vals_list['name'] = get_unique_sequence('logistic.screen.data')
        res = super(LogisticScreen, self).create(vals_list)
        return res

    @api.model
    def _default_product_id(self):
        product = self.env['product.template'].search([('name', '=', 'Bale'), ('detailed_type', '=', 'consu')], limit=1)
        if not product:
            product = self.env['product.template'].create({
                'name': 'Bale',
                'type': 'consu',
            })
        return product.id

    @api.model
    def _default_basement(self):
        basement = self.env['placement.master.data'].search([('name', '=', 'Basement')], limit=1)
        if not basement:
            basement = self.env['placement.master.data'].create({
                'name': 'Basement',
            })
        return basement

    @api.model
    def _default_branch(self):
        branch = self.env['res.company'].search([('nhcl_company_bool', '=', True)]).id
        return branch

    @api.depends('invoice_quantity', 'no_of_quantity')
    def _compute_remaining_quantity(self):
        for record in self:
            if record.po_number:
                total_invoice_quantity = 0
                recs = self.env['logistic.screen.data'].search([
                    ('po_number', '=', record.po_number.id),
                    ('state', '=', 'done')
                ])
                total_invoice_quantity += sum(rec.invoice_quantity for rec in recs)
                record.remaining_quantity = record.no_of_quantity - total_invoice_quantity

    @api.onchange('no_of_bales')
    def _check_positive_bales(self):
        if self.no_of_bales <= 0:
            raise ValidationError("The quantity of bales must be positive!.")

    @api.onchange('no_of_invoices')
    def _check_positive_invoices(self):
        if self.no_of_invoices <= 0:
            raise ValidationError("The number of invoices must be positive!.")

    @api.onchange('logistic_values')
    def _check_positive_logistic_value(self):
        if self.logistic_values <= 0:
            raise ValidationError("The number of invoices must be positive!.")

    @api.onchange('invoice_quantity')
    def _check_invoice_quantity(self):
        if self.invoice_quantity > self.remaining_quantity:
            raise ValidationError("The invoice quantity is more than the remaining quantity!.")

    def logistic_entry_check(self):
        for rec in self:
            product_details = "\n".join([line.product_id.display_name for line in rec.po_number.order_line])
            if rec.state == 'draft':
                rec.state = 'done'
                transport_check_data = self.env['transport.check'].create({
                    'po_order_id': rec.po_number.id,
                    'transporter': rec.transporter.id,
                    'logistic_lr_date': rec.lr_date,
                    'logistic_lr_number': rec.lr_number,
                    'consignment_number': rec.lr_number,
                    'no_of_bales': rec.no_of_bales,
                    'city': rec.city,
                    'logistic_entry_number': rec.name,
                    'logistic_date': rec.logistic_date,
                    'product_id': rec.product_id.id,
                    'item_details':product_details,
                })
                return transport_check_data


    def action_confirm(self):
        current = self.create_date.date()
        if self.logistic_date == False:
            raise ValidationError("Select the Logistic Date")
        elif self.lr_number == False:
            raise ValidationError("Enter alpha numeric LR number")
        elif self.lr_date == False:
            raise ValidationError("Select LR date")
        elif self.transporter == False:
            raise ValidationError("Select the Transporter")
        elif self.no_of_bales <= 0:
            raise ValidationError("Enter more than one bale")
        elif self.product_id == False:
            raise ValidationError("Select the product")
        elif self.due_date == False:
            raise ValidationError("Select Due Date")
        elif current > self.due_date:
            raise ValidationError("The due date must be greater than the previous date!.")
        elif self.way_bill_no == False and self.po_number.amount_total > 50000:
            raise ValidationError("Enter alpha numeric E-Way Bill Numbe")
        elif self.logistic_vendor == False:
            raise ValidationError("please give Agent")
        elif self.gst_no == False:
            raise ValidationError("please give GST Number")
        elif self.charges == False:
            raise ValidationError("Enter Transport Charges")
        elif self.delivery_date == False:
            raise ValidationError("Select Delivery Date")
        elif current > self.delivery_date:
            raise ValidationError("The delivery date must be greater than yesterday's date!.")

        # elif self.no_of_invoices <= 0:
        #     raise ValidationError("Enter at least one invoice")
        elif self.invoice_quantity <= 1:
            raise ValidationError("Enter more than one invoice quantity")
        elif self.logistic_values < 1:
            raise ValidationError("Enter Logistic Value")
        elif self.logistic_type == False:
            raise ValidationError("Select Logistic Type")
        elif self.address == False:
            raise ValidationError("Enter Address")
        elif self.consignor == False:
            raise ValidationError("Select the consignor")
        for rec in self:
            product_details = "\n".join([line.product_id.display_name for line in rec.po_number.order_line])
            rec.state = 'done'
            rec.po_number.ho_status = 'transport'
            rec.logistic_date = fields.Date.today()
            transport_check_data = self.env['transport.check'].create({
                'po_order_id': rec.po_number.id,
                'transporter': rec.transporter.id,
                'logistic_lr_date': rec.lr_date,
                'logistic_lr_number': rec.lr_number,
                'consignment_number': rec.lr_number,
                'no_of_bales': rec.no_of_bales,
                'city': rec.city,
                'logistic_entry_number':rec.name,
                'logistic_date':rec.logistic_date,
                'product_id':rec.product_id.id,
                'item_details':product_details,
                'zone_id': rec.zone_id.id,
            })

            existing_logistic_screen_data = self.env['logistic.screen.data'].search([
                ('po_number', '=', rec.po_number.id),
                ('state', '=', 'done'),
            ])

            if existing_logistic_screen_data and rec.remaining_quantity > rec.invoice_quantity and rec.remaining_quantity != 0:
                self.env['logistic.screen.data'].create({
                    'vendor': rec.vendor.id,
                    'po_number': rec.po_number.id,
                    'no_of_quantity': rec.no_of_quantity,
                    'remaining_quantity': rec.remaining_quantity - rec.invoice_quantity,
                    'gst_no': rec.vendor.vat,
                    'consignor':rec.vendor.id,
                    'zone_id': rec.zone_id.id,
                })

            return {
                'name': 'Purchase',
                'res_model': 'purchase.order',
                'view_mode': 'form',
                'type': 'ir.actions.act_window',
                'res_id': rec.po_number.id,
            }

    def reset_to_draft(self):
        picking_status = self.env['stock.picking'].sudo().search([('origin', '=', self.po_number.name)])
        transport_status = self.env['transport.check'].search([('logistic_entry_number','=',self.name)])
        if transport_status.state != 'sent':
            for rec in self:
                logistic_screen_data = self.env['logistic.screen.data'].search([
                    ('po_number', '=', rec.po_number.id),
                    ('state', '=', 'draft'),
                ])
                logistic_screen_data.unlink()
                if rec.state == 'done':
                    rec.state = 'draft'

                transport_check_records = self.env['transport.check'].search([
                    ('po_order_id', '=', rec.po_number.id),
                    ('logistic_lr_number', '=', rec.lr_number),
                    ('no_of_bales', '=', rec.no_of_bales),
                ])
                transport_check_records.unlink()

                delivery_check_records = self.env['delivery.check'].search([
                    ('po_order_id', '=', rec.po_number.id),
                    ('logistic_lr_number', '=', rec.lr_number),
                    ('no_of_bales', '=', rec.no_of_bales),
                ])
                delivery_check_records.unlink()
        else:
            raise ValidationError("Can not the Reset The Record already confirm.")

