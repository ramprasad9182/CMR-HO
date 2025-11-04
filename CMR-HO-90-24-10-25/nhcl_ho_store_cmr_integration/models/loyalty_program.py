import requests
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo import models, fields, api, _
import logging

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = "product.product"

    def get_store_products(self, ho_ip, ho_port, headers_source):
        product_lst = []
        for product in self:
            if product.name == 'Gift Card':
                product_domain = [('name', '=', 'Gift Card')]
                product_search_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"
                product_store_url = f"{product_search_url}?domain={product_domain}"
                product_data = requests.get(product_store_url, headers=headers_source).json()
                if not product_data.get("data"):
                    continue
                product_name = product_data.get("data")[0]
                product_id = product_name["id"]
                product_lst.append(product_id)
            if product.barcode:
                product_domain = [('barcode', '=', product.barcode)]
                product_search_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"
                product_store_url = f"{product_search_url}?domain={product_domain}"
                product_data = requests.get(product_store_url, headers=headers_source).json()
                if not product_data.get("data"):
                    continue
                product_name = product_data.get("data")[0]
                product_id = product_name["id"]
                product_lst.append(product_id)
        return product_lst


class ProductCategory(models.Model):
    _inherit = "product.category"

    def get_store_category_id(self, ho_ip, ho_port, headers_source):
        for rec in self:
            discount_product_category_url = f"http://{ho_ip}:{ho_port}/api/product.category/search"
            discount_product_category_domain = [('name', '=', rec.name)]
            discount_prod_categ_store_url = f"{discount_product_category_url}?domain={discount_product_category_domain}"
            discount_dest_category_data = requests.get(discount_prod_categ_store_url,
                                                       headers=headers_source).json()
            if not discount_dest_category_data.get("data"):
                continue
            discount_category_name = discount_dest_category_data.get("data")[0]
            discount_product_category_id = discount_category_name["id"]
            return discount_product_category_id


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    def get_store_attribute_vals(self, ho_ip, ho_port, headers_source):
        category_lst = []
        for rec in self:
            category_store_search_url = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
            category_domain = [('name', '=', rec.name)]
            category_store_url = f"{category_store_search_url}?domain={category_domain}"
            category_data = requests.get(category_store_url, headers=headers_source).json()
            if not category_data.get("data"):
                continue
            category_1_data_name = category_data.get("data")[0]
            category_1_data_id = category_1_data_name["id"]
            category_lst.append(category_1_data_id)
        return category_lst

class ProductAgingLine(models.Model):
    _inherit = 'product.aging.line'

    def get_store_product_aging_vals(self, ho_ip, ho_port, headers_source):
        product_aging_lst = []
        for rec in self:
            product_aging_search_url = f"http://{ho_ip}:{ho_port}/api/product.aging.line/search"
            product_aging_domain = [('name', '=', rec.name)]
            product_aging_url = f"{product_aging_search_url}?domain={product_aging_domain}"
            product_aging_data = requests.get(product_aging_url, headers=headers_source).json()
            if not product_aging_data.get("data"):
                continue
            product_aging_data_name = product_aging_data.get("data")[0]
            product_aging_data_id = product_aging_data_name["id"]
            product_aging_lst.append(product_aging_data_id)
        return product_aging_lst


class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"

    @api.constrains('name', 'company_id')
    def _check_name_per_company(self):
        for record in self:
            existing = self.env['loyalty.program'].search([
                ('name', '=', record.name),
                ('company_id', '=', record.company_id.id),
                ('id', '!=', record.id)
            ], limit=1)
            if existing:
                raise ValidationError("Program Name must be unique per company.")

    loyalty_program_id = fields.One2many('loyalty.program.replication', 'loyalty_program_replication_id')
    update_replication = fields.Boolean(string="Creation Status")
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    update_status = fields.Boolean(string="Update Status")
    warning_message = fields.Char(compute='_compute_warning_message')
    nhcl_company_ids = fields.Many2many('res.company',string='Companies',copy=False)


    @api.model
    def get_pending_loyalty(self):
        pending_loyalty = self.search_count([('update_replication', '=', False)])
        return {
            'pending_loyalty': pending_loyalty,
        }

    def get_loyalty_stores(self):
        return {
            'name': _('Promotion'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.loyalty',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_loyalty_view').id,
            'context': {'create': False, 'delete': False, 'duplicate': False, 'default_nhcl_selected_ids': self.ids},
        }

    @api.model
    def _program_type_default_values(self):
        res = super()._program_type_default_values()
        if 'gift_card' in res:
            res['gift_card']['trigger'] = 'with_code'
        if 'ewallet' in res:
            res['ewallet']['trigger'] = 'with_code'
        return res

    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM loyalty_program")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(LoyaltyProgram, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Completed in both Branch and Stores'

    def get_replication_store_list(self):
        replication_data = []
        existing_store_ids = self.loyalty_program_id.mapped('store_id.id')
        ho_store_id = self.env['nhcl.ho.store.master'].search(
            [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Loyalty Program' and j.nhcl_line_data == True:
                    if self.program_type in ['gift_card','ewallet']:
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
                    else:
                        if i.nhcl_store_name.id in existing_store_ids:
                            continue
                        if i.nhcl_store_name.company_id.id in self.nhcl_company_ids.ids:
                            vals = {
                                'store_id': i.nhcl_store_name.id,
                                'nhcl_terminal_ip': i.nhcl_terminal_ip,
                                'nhcl_port_no': i.nhcl_port_no,
                                'nhcl_api_key': i.nhcl_api_key,
                                'status': i.nhcl_active,
                                'master_store_id': i.id
                            }
                            replication_data.append((0, 0, vals))
        self.update({'loyalty_program_id': replication_data})

    @api.onchange('nhcl_company_ids')
    def _onchange_company_ids(self):
        self.loyalty_program_id = False
        if self.nhcl_company_ids:
            self.get_replication_store_list()

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.loyalty_program_id = False
        if self.company_id:
            if self.company_id.nhcl_company_bool == False:
                raise UserError(_("You are not allowed to create Promotions in Branches"))

    def get_serial_number_stores(self):
        if self.program_type in ['gift_card','ewallet']:
            self.get_replication_store_list()
        elif self.rule_ids:
            if self.rule_ids[0].type_filter in ['cart','grc','filter','serial']:
                self.nhcl_company_ids = self.env['nhcl.ho.store.master'].search(
                    [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)]).nhcl_store_name.company_id
                self.get_replication_store_list()


    def send_loyalty_program_replication_data(self):
        if self.program_type not in ['gift_card', 'ewallet']:
            allowed_company_ids = self.env.context.get('allowed_company_ids', [])
            if (len(allowed_company_ids) -1) != len(self.loyalty_program_id):
                raise ValidationError("Please enable the All companies ")
        if self.program_type in ['gift_card', 'ewallet']:
            allowed_company_ids = self.env.context.get('allowed_company_ids', [])
            if (len(allowed_company_ids) -1) != len(self.loyalty_program_id):
                raise ValidationError("Please enable the All companies ")
        if self.program_type in ['gift_card','ewallet'] and self.coupon_count == 0:
            raise ValidationError(_('You are not allowed to replicate Gift card with 0 Qty'))
        for line in self.loyalty_program_id:
            if not line.date_replication and line.is_replicate == True:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                headers_source = {
                    'api-key': ho_api_key,
                    'Content-Type': 'application/json'
                }
                search_store_url_data = f"http://{ho_ip}:{ho_port}/api/loyalty.program/search"
                partner_domain = [('nhcl_id', '=', self.nhcl_id), ('program_type', '=', self.program_type)]
                store_url = f"{search_store_url_data}?domain={partner_domain}"
                store_url_data = f"http://{ho_ip}:{ho_port}/api/loyalty.program/create"
                rule_ids_lst = []
                branch_rule_ids_lst = []
                rewards_lst = []
                branch_rewards_lst = []
                trigger_product_lst = []
                coupon_lst = []
                payment_program_discount_product_id = False
                mail_template_id = False
                report_id = False
                for data in self.rule_ids:
                    product_lst = []
                    lot_lst = []
                    ref_product_lst = []
                    category_1_lst = []
                    category_2_lst = []
                    category_3_lst = []
                    category_4_lst = []
                    category_5_lst = []
                    category_6_lst = []
                    category_7_lst = []
                    description_1_lst = False
                    description_2_lst = []
                    description_3_lst = []
                    description_4_lst = []
                    description_5_lst = []
                    description_6_lst = []
                    if data.category_1_ids:
                        category_1_lst = data.category_1_ids.get_store_attribute_vals(ho_ip, ho_port, headers_source)
                    if data.category_2_ids:
                        category_2_lst = data.category_2_ids.get_store_attribute_vals(ho_ip, ho_port, headers_source)
                    if data.category_3_ids:
                        category_3_lst = data.category_3_ids.get_store_attribute_vals(ho_ip, ho_port, headers_source)
                    if data.category_4_ids:
                        category_4_lst = data.category_4_ids.get_store_attribute_vals(ho_ip, ho_port, headers_source)
                    if data.category_5_ids:
                        category_5_lst = data.category_5_ids.get_store_attribute_vals(ho_ip, ho_port, headers_source)
                    if data.category_6_ids:
                        category_6_lst = data.category_6_ids.get_store_attribute_vals(ho_ip, ho_port, headers_source)
                    if data.category_7_ids:
                        category_7_lst = data.category_7_ids.get_store_attribute_vals(ho_ip, ho_port, headers_source)
                    if data.description_1_ids:
                        description_1_lst = data.description_1_ids.get_store_product_aging_vals(ho_ip, ho_port,
                                                                                            headers_source)
                    if data.description_2_ids:
                        description_2_lst = data.description_2_ids.get_store_attribute_vals(ho_ip, ho_port,
                                                                                            headers_source)
                    if data.description_3_ids:
                        description_3_lst = data.description_3_ids.get_store_attribute_vals(ho_ip, ho_port,
                                                                                            headers_source)
                    if data.description_4_ids:
                        description_4_lst = data.description_4_ids.get_store_attribute_vals(ho_ip, ho_port,
                                                                                            headers_source)
                    if data.description_5_ids:
                        description_5_lst = data.description_5_ids.get_store_attribute_vals(ho_ip, ho_port,
                                                                                            headers_source)
                    if data.description_6_ids:
                        description_6_lst = data.description_6_ids.get_store_attribute_vals(ho_ip, ho_port,
                                                                                            headers_source)
                    if data.product_ids:
                        product_lst = data.product_ids.get_store_products(ho_ip, ho_port, headers_source)

                    if data.ref_product_ids:
                        ref_product_lst = data.ref_product_ids.get_store_products(ho_ip, ho_port, headers_source)


                    product_category_id = False
                    if data.product_category_id:
                        product_category_id = data.product_category_id.get_store_category_id(ho_ip, ho_port,
                                                                                            headers_source)
                    rule_ids_lst.append((0, 0, {
                        'minimum_qty': data.minimum_qty,
                        'minimum_amount': data.minimum_amount,
                        'type_filter': data.type_filter,
                        'reward_point_amount': data.reward_point_amount,
                        'reward_point_mode': data.reward_point_mode,
                        'product_ids': product_lst,
                        'ref_product_ids': ref_product_lst,
                        'serial_nos': data.serial_nos,
                        'category_1_ids': category_1_lst,
                        'category_2_ids': category_2_lst,
                        'category_3_ids': category_3_lst,
                        'category_4_ids': category_4_lst,
                        'category_5_ids': category_5_lst,
                        'category_6_ids': category_6_lst,
                        'category_7_ids': category_7_lst,
                        'description_1_ids': description_1_lst,
                        'description_2_ids': description_2_lst,
                        'description_3_ids': description_3_lst,
                        'description_4_ids': description_4_lst,
                        'description_5_ids': description_5_lst,
                        'description_6_ids': description_6_lst,
                        'product_category_id': product_category_id if product_category_id else False
                    }))
                    branch_rule_ids_lst.append((0, 0, {
                        'minimum_qty': data.minimum_qty,
                        'minimum_amount': data.minimum_amount,
                        'type_filter': data.type_filter,
                        'reward_point_amount': data.reward_point_amount,
                        'reward_point_mode': data.reward_point_mode,
                        'product_ids': data.product_ids,
                        'ref_product_ids': data.ref_product_ids,
                        'serial_nos': data.serial_nos,
                        'category_1_ids': data.category_1_ids,
                        'category_2_ids': data.category_2_ids,
                        'category_3_ids': data.category_3_ids,
                        'category_4_ids': data.category_4_ids,
                        'category_5_ids': data.category_5_ids,
                        'category_6_ids': data.category_6_ids,
                        'category_7_ids': data.category_7_ids,
                        'description_1_ids': data.description_1_ids,
                        'description_2_ids': data.description_2_ids,
                        'description_3_ids': data.description_3_ids,
                        'description_4_ids': data.description_4_ids,
                        'description_5_ids': data.description_5_ids,
                        'description_6_ids': data.description_6_ids,
                        'product_category_id': data.product_category_id.ids
                    }))

                for reward in self.reward_ids:
                    rwd_product_lst = []
                    discount_line_product_id = False
                    if reward.discount_line_product_id:
                        discount_line_product_id = reward.discount_line_product_id.get_store_products(ho_ip, ho_port,
                                                                                                      headers_source)
                    if reward.discount_product_ids:
                        rwd_product_lst = reward.discount_product_ids.get_store_products(ho_ip, ho_port, headers_source)
                    discount_product_category_id = False
                    reward_product_id = False
                    discount_product_id = False
                    if reward.discount_product_category_id:
                        discount_product_category_id = reward.discount_product_category_id.get_store_category_id(ho_ip,
                                                                                                                 ho_port,
                                                                                                                 headers_source)

                    if reward.reward_product_id:
                        reward_product_id = reward.reward_product_id.get_store_products(ho_ip, ho_port, headers_source)

                    if reward.discount_product_id:
                        discount_product_id = reward.discount_product_id.get_store_products(ho_ip, ho_port, headers_source)

                    rewards_lst.append((0, 0, {
                            'reward_type': reward.reward_type,
                            'discount': reward.discount,
                            'discount_mode': reward.discount_mode,
                            'discount_applicability': reward.discount_applicability,
                            'discount_max_amount': reward.discount_max_amount,
                            'required_points': reward.required_points,
                            'discount_line_product_id': discount_line_product_id[0] if discount_line_product_id else False,
                            'description': reward.description,
                            'reward_product_qty': reward.reward_product_qty,
                            'discount_product_ids': rwd_product_lst,
                            'discount_product_category_id': discount_product_category_id,
                            'reward_product_id': reward_product_id[0] if reward_product_id else False,
                            'discount_product_id': discount_product_id[0] if discount_product_id else False,
                            'product_price': reward.product_price if reward.product_price else 0.0

                    }))
                    branch_rewards_lst.append((0, 0, {
                            'reward_type': reward.reward_type,
                            'discount': reward.discount,
                            'discount_mode': reward.discount_mode,
                            'discount_applicability': reward.discount_applicability,
                            'discount_max_amount': reward.discount_max_amount,
                            'required_points': reward.required_points,
                            'reward_product_qty': reward.reward_product_qty,
                            'discount_product_ids': reward.discount_product_ids,
                            'discount_product_category_id': reward.discount_product_category_id.id,
                            'reward_product_id': reward.reward_product_id.id,
                            'discount_product_id': reward.discount_product_id.id,
                            'product_price': reward.product_price if reward.product_price else 0.0

                    }))
                for vochur in self.coupon_ids:
                    coupon_lst.append((0, 0, {
                        'code': vochur.code,
                        'expiration_date': vochur.expiration_date.strftime('%Y-%m-%d') if vochur.expiration_date else None,
                        'points': vochur.points,

                    }))
                if self.trigger_product_ids:
                    trigger_product_lst = self.trigger_product_ids.get_store_products(ho_ip, ho_port, headers_source)
                if self.payment_program_discount_product_id:
                    payment_program_discount_product_id = self.payment_program_discount_product_id.get_store_products(ho_ip, ho_port, headers_source)
                if self.mail_template_id:
                    mail_template_id_url = f"http://{ho_ip}:{ho_port}/api/mail.template/search"
                    mail_template_id_domain = [('name', '=', self.mail_template_id.name)]
                    mail_template_id_store_url = f"{mail_template_id_url}?domain={mail_template_id_domain}"
                    mail_template_id_data = requests.get(mail_template_id_store_url,
                                                               headers=headers_source).json()
                    if not mail_template_id_data.get("data"):
                        continue
                    mail_template_name = mail_template_id_data.get("data")[0]
                    mail_template_id = mail_template_name["id"]
                if self.pos_report_print_id:
                    pos_report_print_url = f"http://{ho_ip}:{ho_port}/api/ir.actions.report/search"
                    pos_report_print_domain = [('name', '=', self.pos_report_print_id.name)]
                    pos_report_print_store_url = f"{pos_report_print_url}?domain={pos_report_print_domain}"
                    pos_report_print_data = requests.get(pos_report_print_store_url,
                                                         headers=headers_source).json()
                    if not pos_report_print_data.get("data"):
                        continue
                    pos_report_print_name = pos_report_print_data.get("data")[0]
                    report_id = pos_report_print_name["id"]
                tax_list = {
                    'name': self.name,
                    'program_type': self.program_type,
                    'portal_point_name': self.portal_point_name,
                    'currency_id': self.currency_id.id,
                    'portal_visible': self.portal_visible,
                    'trigger': self.trigger,
                    'is_vendor_return': self.is_vendor_return,
                    'applies_on': self.applies_on,
                    'date_from': self.date_from.strftime('%Y-%m-%d') if self.date_from else None,
                    'date_to': self.date_to.strftime('%Y-%m-%d') if self.date_to else None,
                    'limit_usage': self.limit_usage,
                    'pos_ok': self.pos_ok,
                    'nhcl_id': self.nhcl_id,
                    'rule_ids': rule_ids_lst,
                    'reward_ids': rewards_lst,
                    'coupon_ids': coupon_lst,
                    'trigger_product_ids': trigger_product_lst,
                    'mail_template_id': mail_template_id,
                    'pos_report_print_id': report_id,
                    'payment_program_discount_product_id': payment_program_discount_product_id[0] if payment_program_discount_product_id else False
                }
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()  # Raises an HTTPError for bad responses

                    # Parse the JSON response
                    data = response.json()  # Now `data` is a dictionary
                    loyalty_data = data.get("data", [])
                    # Check if Loyalty Program already exists
                    if loyalty_data:
                        _logger.info(
                            f" '{self.name}' Already exists as Loyalty Program on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(
                            f" '{self.name}' Already exists as Loyalty Program on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        self.update_replication = True
                        continue
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[tax_list])
                        stores_data.raise_for_status()
                        # Raise an exception for HTTP errors
                        stores_data.raise_for_status()
                        branch_promotion_vals = {
                            'name': self.name,
                            'program_type': self.program_type,
                            'portal_point_name': self.portal_point_name,
                            'currency_id': self.currency_id.id,
                            'portal_visible': self.portal_visible,
                            'trigger': self.trigger,
                            'applies_on': self.applies_on,
                            'date_from': self.date_from.strftime('%Y-%m-%d') if self.date_from else None,
                            'date_to': self.date_to.strftime('%Y-%m-%d') if self.date_to else None,
                            'limit_usage': self.limit_usage,
                            'pos_ok': self.pos_ok,
                            'nhcl_id': self.nhcl_id,
                            'rule_ids': branch_rule_ids_lst,
                            'reward_ids': branch_rewards_lst,
                            'coupon_ids': coupon_lst,
                            'trigger_product_ids': self.trigger_product_ids,
                            'pos_report_print_id': self.pos_report_print_id.id,
                            'company_id':line.store_id.company_id.id,
                            'payment_program_discount_product_id': self.payment_program_discount_product_id.id
                        }
                        if self.program_type not in ['gift_card','ewallet']:
                            self.env['loyalty.program'].sudo().create(branch_promotion_vals)
                        # Access the JSON content from the response
                        response_json = stores_data.json()

                        # Access specific values from the response (e.g., "message" or "responseCode")
                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Promotion {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Promotion  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                'add', 'failure', message)
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'], self.id,
                                                                                          200, 'add', 'failure',
                                                                                          message)


                        else:
                            line.date_replication = True
                            self.update_replication = True
                            _logger.info(
                                f"Successfully created Promotion {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully created Promotion {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id,
                                                                                200,
                                                                                'add', 'success', f"Successfully created Promotion {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id,
                                                                                          200, 'add', 'success',
                                                                                          f"Successfully created Promotion {self.name}")

                    except requests.exceptions.RequestException as e:
                        _logger.warning(f"Failed to create Promotions '{self.name}' at '{ho_ip}:{ho_port}'. Error: {e}")
                        line.date_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('loyalty.program', self.id,
                                                                            500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('loyalty.program', self.id,
                                                                                500, 'add', 'failure',
                                                                                e)
                        self.update_replication = False
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Loyalty Program on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Loyalty Program on '{ho_ip}' with partner '{ho_port}'. Error: {e}")

    def update_loyalty_program_data(self):
        for line in self.loyalty_program_id:
            ho_ip = line.nhcl_terminal_ip
            ho_port = line.nhcl_port_no
            ho_api_key = line.nhcl_api_key
            store_url_data = f"http://{ho_ip}:{ho_port}/api/loyalty.program/search"
            store_url_data1 = f"http://{ho_ip}:{ho_port}/api/loyalty.rule/search"
            store_url_data2 = f"http://{ho_ip}:{ho_port}/api/loyalty.reward/search"
            program_domain = self.nhcl_id
            prog_domain = [('nhcl_id', '=', program_domain)]
            store_url = f"{store_url_data}?domain={prog_domain}"
            headers_source = {'api-key': ho_api_key, 'Content-Type': 'application/json'}

            try:
                    # Step 1: Retrieve the existing program
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()
                    data = response.json()
                    program_data = data.get("data", [])

                    if not program_data:
                        _logger.warning(f"No matching loyalty program found for '{self.name}'. Skipping update.")
                        continue

                    program_id = program_data[0].get('id')
                    store_url1 = f"{store_url_data1}"
                    store_url2 = f"{store_url_data2}"
                    payload = {'domain': [('program_id', '=', program_id)]}

                    # Retrieve rule values based on program_id
                    response1 = requests.get(store_url1, headers=headers_source, json=payload)
                    response1.raise_for_status()
                    data1 = response1.json()
                    rule_value_data = data1.get("data", [])
                    # Retrieve reward values based on program_id
                    response2 = requests.get(store_url2, headers=headers_source, json=payload)
                    response2.raise_for_status()
                    data2 = response2.json()
                    reward_value_data = data2.get("data", [])

                    # Debugging: Check the raw response data

                    _logger.debug(f"Raw response data from store_url1: {data1}")
                    _logger.debug(f"Raw response data from store_url2: {data2}")

                    # Log the rule value data
                    _logger.debug(f"Retrieved rule value data: {rule_value_data}")
                    _logger.debug(f"Retrieved reward value data: {reward_value_data}")

                    # Check if the program ID was retrieved
                    if not program_id:
                        _logger.error(f"Program ID not found for '{self.name}' in response. Skipping update.")
                        continue

                    # Step 2: Prepare the update data
                    rule_line = []
                    for data in self.rule_ids:
                        # Check if the value already exists in destination (attribute_value_data)
                        existing_value = next((val for val in rule_value_data if val.get('minimum_qty') == data.minimum_qty and val.get('minimum_amount') == data.minimum_amount),
                                              None)

                        if existing_value:
                            # If the value exists, use the existing ID and update the values
                            rule_line.append([1, existing_value['id'], {
                                'minimum_qty': data.minimum_qty,
                                'minimum_amount': data.minimum_amount,
                                'type_filter': data.type_filter,
                                # 'range_from': data.range_from,
                                # 'range_to': data.range_to,
                                'reward_point_amount': data.reward_point_amount,
                                'reward_point_mode': data.reward_point_mode
                            }])
                        else:
                            # If the value doesn't exist, create a new one
                            rule_line.append([0, 0, {
                                'minimum_qty': data.minimum_qty,
                                'minimum_amount': data.minimum_amount,
                                'type_filter': data.type_filter,
                                # 'range_from': data.range_from,
                                # 'range_to': data.range_to,
                                'reward_point_amount': data.reward_point_amount,
                                'reward_point_mode': data.reward_point_mode
                            }])

                    # Log the product_attribute_line data for debugging
                    _logger.debug(f"Prepared Loyalty rule line: {rule_line}")

                    # Rewards
                    reward_line = []
                    for reward in self.reward_ids:
                        # Check if the value already exists in destination (reward_value_data)
                        existing_reward_value = next(
                            (val1 for val1 in reward_value_data if val1.get('discount') == reward.discount and val1.get('reward_type') == reward.reward_type),
                            None)

                        if existing_reward_value:
                            # If the value exists, use the existing ID and update the values
                            reward_line.append([1, existing_reward_value['id'], {
                                'reward_type': reward.reward_type,
                                'discount': reward.discount,
                                'discount_applicability': reward.discount_applicability,
                                'discount_max_amount': reward.discount_max_amount,
                                'required_points': reward.required_points,
                            }])
                        else:
                            # If the value doesn't exist, create a new one
                            rule_line.append([0, 0, {
                                'reward_type': reward.reward_type,
                                'discount': reward.discount,
                                'discount_applicability': reward.discount_applicability,
                                'discount_max_amount': reward.discount_max_amount,
                                'required_points': reward.required_points,
                            }])

                    # Construct the full loyalty list
                    loyalty_program_list = {
                        'name': self.name,
                        'program_type': self.program_type,
                        'portal_point_name': self.portal_point_name,
                        'portal_visible': self.portal_visible,
                        'trigger': self.trigger,
                        'applies_on': self.applies_on,
                        'date_from': self.date_from.strftime('%Y-%m-%d') if self.date_from else None,
                        'date_to': self.date_to.strftime('%Y-%m-%d') if self.date_to else None,
                        'limit_usage': self.limit_usage,
                        'pos_ok': self.pos_ok,
                        'nhcl_id': self.nhcl_id,
                        'rule_ids': rule_line,
                        'reward_ids': reward_line
                    }

                    # Log the final data for debugging
                    _logger.debug(f"Loyalty program data prepared for update: {loyalty_program_list}")

                    # Step 3: Send the update request
                    store_url_program = f"http://{ho_ip}:{ho_port}/api/loyalty.program/{program_id}"
                    update_response = requests.put(store_url_program, headers=headers_source, json=loyalty_program_list)
                    update_response.raise_for_status()

                    # Step 4: Update the status upon success
                    line.update_status = True
                    self.update_status = True
                    _logger.info(f"Successfully updated loyalty Program '{self.name}' at '{ho_ip}:{ho_port}'.")
                    logging.info(f"Successfully updated loyalty Program '{self.name}' at '{ho_ip}:{ho_port}'.")
                    if line.master_store_id.nhcl_sink == False:
                        line.master_store_id.create_cmr_replication_log('loyalty.program', self.id,
                                                                        200, 'update', 'success',
                                                                        f"Successfully updated loyalty Program '{self.name}'")
                    else:
                        line.master_store_id.create_cmr_old_store_replication_log('loyalty.program', self.id,
                                                                                  200, 'update', 'success',
                                                                                  f"Successfully updated loyalty Program '{self.name}'")

            except requests.exceptions.RequestException as e:
                    _logger.error(f"Failed to update attribute '{self.name}' at '{ho_ip}:{ho_port}'. Error: {e}")
                    logging.error(f"Failed to update attribute '{self.name}' at '{ho_ip}:{ho_port}'. Error: {e}")
                    line.update_status = False
                    self.update_status = False
                    if line.master_store_id.nhcl_sink == False:
                        line.master_store_id.create_cmr_replication_log('loyalty.program', self.id,
                                                                        500, 'update', 'failure',
                                                                        e)
                    else:
                        line.master_store_id.create_cmr_old_store_replication_log('loyalty.program', self.id,
                                                                                  500, 'update', 'failure',
                                                                                  e)


class LoyaltyPogramReplication(models.Model):
    _name = 'loyalty.program.replication'

    loyalty_program_replication_id = fields.Many2one('loyalty.program', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')
    update_status = fields.Boolean(string="Update Status")
    is_replicate = fields.Boolean(string='Replicate',default=True)

