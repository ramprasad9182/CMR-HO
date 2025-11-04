from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_HALF_UP


def round_half_up(number):
    return int(Decimal(number).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


class StoreWiseData(models.Model):
    _name =  "store.wise.data"
    _description = "Store Wise Data"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Reference", required=True, readonly=True, default='New', tracking=True)
    store_id = fields.Many2one('res.company', string="Store",required=True,tracking=True,domain = [('nhcl_company_bool','!=',True)])
    from_date = fields.Date(string="From Date",tracking=True,copy=False,)
    to_date = fields.Date(string="To Date",tracking=True,copy=False,)
    division_line_ids = fields.One2many('store.wise.division.line', 'store_data_id', string="Division Lines")


    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('store.wise.data') or 'New'
        return super(StoreWiseData, self).create(vals)

    # unique date and store
    @api.constrains('store_id', 'from_date', 'to_date')
    def _check_duplicate_store_date(self):
        for rec in self:
            if rec.store_id and rec.from_date and rec.to_date:
                duplicate = self.search([
                    ('store_id', '=', rec.store_id.id),
                    ('from_date', '=', rec.from_date),
                    ('to_date', '=', rec.to_date),
                    ('id', '!=', rec.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(
                        "A record already exists for this Store with the same From Date and To Date."
                    )

    @api.onchange('from_date')
    def _onchange_from_date(self):
        """Auto-calculate to_date as exactly 4 months after from_date."""
        if self.from_date:
            self.to_date = self.from_date + relativedelta(months=+4)

    @api.constrains('to_date')
    def _check_date_range(self):
        for rec in self:
            if rec.from_date and rec.to_date:
                difference = relativedelta(rec.to_date, rec.from_date)
                total_months = (difference.years * 12) + difference.months
                total_days = difference.days
                # If less than 4 months, raise error
                if not (total_months == 4 and total_days == 0):
                    raise ValidationError(
                        "The date range must be exactly 4 full months between From Date and To Date.")


    def get_store_division_data(self):
        # Ensure a store is selected
        if not self.store_id:
            raise UserError("Please select a Store.")

        self.division_line_ids = [(5, 0, 0)]
        # Step 1: Get all stock.lot records for the selected store/company
        stock_lots = self.env['stock.lot'].sudo().search([('company_id.id', '=', self.store_id.id),('product_qty','>',0),('create_date', '<=', self.from_date)])
        # Get unique division names
        division_names = set()
        for lot in stock_lots:
            division_name = lot.product_id.family_categ_id.name
            if division_name:
                division_names.add(division_name)
        # Now for each division, get product count and sum of rs_price
        result = []
        grand_total_rsp = 0.0
        division_totals = {}
        for division_name in division_names:
            # Find stock.lot where product's family category matches this division
            lots_in_division = self.env['stock.lot'].sudo().search([
                ('product_id.family_categ_id.name', '=', division_name),
                ('company_id.id', '=', self.store_id.id)
            ])

            # Get unique products from those lots
            product_ids = lots_in_division.mapped('product_id')

            # Count of unique products
            # product_count = len(product_ids)

            # Sum of rs_price from stock.lot
            total_rsp_value = sum((lot.rs_price * lot.product_qty) for lot in lots_in_division if lot.rs_price)
            division_totals[division_name] = total_rsp_value
            grand_total_rsp += total_rsp_value

        # Second loop: Calculate Percentage and prepare One2many lines
        for division_name, total_rsp_value in division_totals.items():
            # percentage = (total_rsp_value / grand_total_rsp * 100) if grand_total_rsp else 0.0
            # percentage = round((total_rsp_value / grand_total_rsp * 100), 0) if grand_total_rsp else 0.0
            percentage = round_half_up((total_rsp_value / grand_total_rsp * 100)) if grand_total_rsp else 0.0
            per_month_value = total_rsp_value / 4 if total_rsp_value else 0.0

            result.append((0, 0, {
                'division_name': division_name,
                'total_rsp_value': total_rsp_value,
                'percentage': percentage,
                'per_month_value': per_month_value,
            }))

        self.division_line_ids = result


class StoreWiseDivisionLine(models.Model):
    _name = "store.wise.division.line"
    _description = "Store Wise Division Line"

    store_data_id = fields.Many2one('store.wise.data', string="Store Data")
    s_no = fields.Integer(string="Row No", compute="_compute_s_no")
    division_name = fields.Char(string="Department",readonly=True,copy=False,tracking=True)
    # product_count = fields.Integer(string="Product Count")
    total_rsp_value = fields.Float(string="Stock Amount",readonly=True,copy=False,tracking=True)
    percentage = fields.Float(string="CON (%)",readonly=True,copy=False,tracking=True)
    per_month_value = fields.Float(string="Per Month",readonly=True,copy=False,tracking=True)
    expenses = fields.Float(string="EXP",copy=False,tracking=True)
    soh_exp = fields.Float(string="SOH - EXP",readonly=True,copy=False,tracking=True)
    regular_percentage = fields.Float(string="Regular Percentage(%)",copy=False,tracking=True)
    regular_excess_month = fields.Float(string="15%Excess/per month",readonly=True)
    festival_percentage = fields.Float(string="Festival Percentage(%)",copy=False,tracking=True)
    festival_excess_month = fields.Float(string="30%Excess/per month",readonly=True)
    regular_per_day = fields.Float(string="Regular Per Day",readonly=True)
    festival_per_day = fields.Float(string="Festival Per Day",readonly=True)

    @api.depends('store_data_id.division_line_ids')
    def _compute_s_no(self):
        for rec in self.store_data_id:
            for index, line in enumerate(rec.division_line_ids, start=1):
                line.s_no = index

    @api.onchange('expenses')
    def _onchange_soh_exp(self):
        for rec in self:
            rec.soh_exp = (rec.per_month_value or 0.0) + (rec.expenses or 0.0)

    @api.onchange('soh_exp', 'regular_percentage', 'festival_percentage')
    def _onchange_excess_percentages(self):
        for rec in self:
            soh_exp = rec.soh_exp or 0.0
            if rec.regular_percentage:
                regular_pct = rec.regular_percentage or 0.0
                rec.regular_excess_month = soh_exp + (soh_exp * (regular_pct / 100))
                rec.regular_per_day = rec.regular_excess_month / 30
            if rec.festival_percentage:
                festival_pct = rec.festival_percentage or 0.0
                rec.festival_excess_month = soh_exp + (soh_exp * (festival_pct / 100))
                rec.festival_per_day = rec.festival_excess_month / 30





