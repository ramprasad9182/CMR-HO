import requests
import logging

_logger = logging.getLogger(__name__)
from datetime import datetime
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
    creation_status = fields.Boolean(string="Synced Status", tracking=True, copy=False,readonly=True)
    # line_count = fields.Boolean(string="Lines Status", tracking=True, copy=False,readonly=True,default=False)
    #
    # @api.depends('division_line_ids')
    # def line_count(self):
    #     for rec in self:
    #         rec.line_count = True

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

    def _get_store_master_config(self):
        """Get the HO store config for the selected store/company"""
        self.ensure_one()

        if self.store_id.nhcl_company_bool != True:
            # raise ValidationError("Selected company is not a store.")
            store = self.env['nhcl.ho.store.master'].search([
                ('nhcl_store_name.company_id', '=', self.store_id.id),
                ('nhcl_active', '=', True)
            ], limit=1)

        if not store:
            raise ValidationError(
                f"No active Store configuration found for company: {self.store_id.name}"
            )

        if not store.nhcl_terminal_ip:
            raise ValidationError("Store Terminal IP is not configured.")
        if not store.nhcl_port_no:
            raise ValidationError("Store Port Number is not configured.")
        if not store.nhcl_api_key:
            raise ValidationError("Store API Key is not configured.")

        return store

    def send_store_target_data_to_store(self):
        """Send the Store Wise Data to the corresponding store via API"""
        for record in self:
            record.ensure_one()
            if not record.division_line_ids:
                raise ValidationError(f"Record {record.name} has no division lines.")
                # _logger.warning(f"Record {record.name} has no division lines. Skipping API call.")
                # continue
            # for line in record.division_line_ids:
            #     missing_fields = []
            #
            #     if not line.division_name:
            #         missing_fields.append("Division")
            #
            #     if not line.total_rsp_value:
            #         missing_fields.append("Stock Amount")
            #
            #     if not line.percentage:
            #         missing_fields.append("CON (%)")
            #
            #     if not line.per_month_value:
            #         missing_fields.append("Per Month")
            #
            #     if not line.total_amount:
            #         missing_fields.append("Target")
            #
            #     if missing_fields:
            #         raise ValidationError(
            #             f"Missing data in division '{line.division_name or 'Unknown'}' : "
            #             + ", ".join(missing_fields)
            #         )

            if record.creation_status:
                if record.creation_status:
                    raise ValidationError("This record is already integrated to the store.")
                    # _logger.info(f"Record {record.name} already integrated. Skipping API call.")
                    # continue
            ho_id = self.env['nhcl.ho.store.master'].search(
                [('nhcl_active', '=', True), ('nhcl_store_type', '=', "ho")],
                limit=1
            )

            # Step 1: Get Store configuration
            store = record._get_store_master_config()
            if not store:
                raise ValidationError("Store configuration not found.")
            store_ip = store.nhcl_terminal_ip
            store_port = store.nhcl_port_no
            store_api_key = store.nhcl_api_key
            # company_search_url = f"http://{store_ip}:{store_port}/api/res.company/search"
            #
            # company_domain = [('name', '=', self.company_id.name)]
            #
            # company_search_full_url = f"{company_search_url}?domain={company_domain}"
            #
            # company_data = requests.get(company_search_full_url, headers=headers).json()
            #
            # if not company_data:
            #     raise ValidationError("Company not found in destination database.")
            # company_id = company_data.get("data")
            # dest_company_id = company_id[0]

            # Step 2: Prepare payload
            division_data = []
            for line in record.division_line_ids:
                data_list = {
                    "division_name": line.division_name,
                    "total_rsp_value": line.total_rsp_value,
                    "percentage": line.percentage,
                    "per_month_value": line.per_month_value,
                    "expenses": line.expenses,
                    "soh_exp": line.soh_exp,
                    "regular_percentage": line.regular_percentage,
                    "regular_excess_month": line.regular_excess_month,
                    "festival_percentage": line.festival_percentage,
                    "festival_excess_month": line.festival_excess_month,
                    "regular_per_day": line.regular_per_day,
                    "festival_per_day": line.festival_per_day,
                    "total_amount": line.total_amount
                }
                division_data.append((0, 0, data_list))
                print("Data1245678",division_data)


            store_target_data = {
                'name':record.name,
                # "store_name": dest_company_id,
                "from_date": str(record.from_date) if record.from_date else False,
                "to_date": str(record.to_date) if record.to_date else False,
                "division_line_ids": division_data
            }

            # Step 3: Send data via POST
            api_url = f"http://{store_ip}:{store_port}/api/store.target.data/create"
            headers = {"api-key": store_api_key, "Content-Type": "application/json"}
            try:
                response = requests.post(api_url, headers=headers, json=store_target_data, timeout=30)
                response_json = response.json()
                success = response_json.get("success", False)
                message = response_json.get("message", "No message provided")
                model_name = response_json.get("object_name", "store.target.data")
                self.env['store.wise.division.replication.log'].create({
                    # 'nhcl_serial_no': ,
                    'nhcl_date_of_log': datetime.now(),
                    'nhcl_source_name': ho_id.nhcl_store_id,
                    'nhcl_source_id': ho_id.nhcl_store_name.id,
                    'nhcl_destination_name': store.nhcl_store_id,
                    'nhcl_destination_id': store.nhcl_store_name.id,
                    'nhcl_record_id': record.id,
                    'nhcl_function_required': 'add',
                    'nhcl_status': 'success' if success else 'failure',
                    'nhcl_details_status': message,
                    'nhcl_model': model_name,
                    'nhcl_status_code': str(response.status_code),
                })

                if success:
                    record.write({'creation_status': True})
                    _logger.info(f"Successfully integrated Audit Plan {record.name}")
                else:
                    record.write({'creation_status': False})
                    _logger.error(f"Integration failed: {message}")

                _logger.info(f"API Response for {record.name}: {message}")

            except requests.exceptions.RequestException as e:
                record.write({'creation_status': False})
                self.env['store.wise.division.replication.log'].create({
                    # 'nhcl_serial_no': ,
                    'nhcl_date_of_log': datetime.now(),
                    'nhcl_source_name': ho_id.nhcl_store_id,
                    'nhcl_source_id': ho_id.nhcl_store_name.id,
                    'nhcl_destination_name': store.nhcl_store_id,
                    'nhcl_destination_id': store.nhcl_store_name.id,
                    'nhcl_record_id': record.id,
                    'nhcl_function_required': 'add',
                    'nhcl_status': 'failure',
                    'nhcl_details_status': str(e),
                    'nhcl_model': 'store.target.data',
                    'nhcl_status_code': 'Connection Error',
                })
        return True


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
    total_amount = fields.Float(string="Target")
    month_target = fields.Float(
        string="Month Target",
        compute="_compute_targets",
        store=True,
        readonly=True
    )

    day_target = fields.Float(
        string="Day Target",
        compute="_compute_targets",
        store=True,
        readonly=True
    )

    @api.depends('total_amount', 'store_data_id.from_date', 'store_data_id.to_date')
    def _compute_targets(self):
        for rec in self:
            from_date = rec.store_data_id.from_date
            to_date = rec.store_data_id.to_date
            total = rec.total_amount or 0.0
            print("%%%%%",total)

            if not from_date or not to_date or total <= 0:
                rec.month_target = 0.0
                rec.day_target = 0.0
                continue

            rec.month_target = total / 4.0

            total_days = (to_date - from_date).days + 1
            # if total_days <= 0:
            #     total_days = 1
            print("&&&&",total_days)

            rec.day_target = total / total_days

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
            if rec.regular_percentage not in (None, 0):
                regular_pct = rec.regular_percentage
                rec.regular_excess_month = soh_exp + (soh_exp * (regular_pct / 100))
                rec.regular_per_day = rec.regular_excess_month / 30
            else:
                rec.regular_excess_month = 0.0
                rec.regular_per_day = 0.0

            if rec.festival_percentage not in (None, 0):
                festival_pct = rec.festival_percentage
                rec.festival_excess_month = soh_exp + (soh_exp * (festival_pct / 100))
                rec.festival_per_day = rec.festival_excess_month / 30
            else:
                rec.festival_excess_month = 0.0
                rec.festival_per_day = 0.0





