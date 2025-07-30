from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime


class HoStoreMaster(models.Model):
    """Created nhcl.ho.store.master class to add fields and functions"""
    _name = "nhcl.ho.store.master"
    _description = "HO/Store Master"

    nhcl_store_id = fields.Char("Store ID", readonly=True, copy=False)
    nhcl_store_name = fields.Many2one('stock.warehouse', string='Store Name')
    nhcl_store_type = fields.Selection([('ho', 'HO'), ('store', 'Stores')], default='', string='Master Type')
    nhcl_location_id = fields.Many2one('stock.location', string='Location')
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    nhcl_active = fields.Boolean(default=False, string="Status")
    nhcl_web_url = fields.Char('URL')
    nhcl_login_user = fields.Char('User')
    nhcl_password = fields.Char('Password')
    nhcl_effective_date = fields.Date('Effective Date')
    nhcl_create_date = fields.Date('Create Date', default=fields.Date.context_today)
    nhcl_store_data_id = fields.One2many('nhcl.store.master.line.data', 'nhcl_store_line_ids')
    nhcl_sink = fields.Boolean(default=False, string="Sink")

    def _compute_display_name(self):
        super()._compute_display_name()
        for i in self:
            i.display_name = f"{i.nhcl_store_name.name} - {i.nhcl_terminal_ip}"

    def activate_store(self):
        if self.nhcl_active == False:
            self.nhcl_active = True
        return {
            'type': 'ir.actions.client', 'tag': 'reload'
        }

    def deactivate_store(self):
        if self.nhcl_active == True:
            self.nhcl_active = False
        return {
            'type': 'ir.actions.client', 'tag': 'reload'
        }

    def replicate_product_categories(self, product_categories):
        for product_categ in product_categories:
            stores = product_categ.replication_id.filtered(
                lambda
                    x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
            if not stores:
                product_categ.get_stores_data()
                stores = product_categ.replication_id.filtered(
                    lambda
                        x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
            if stores:
                product_categ.send_replication_data_to_store(stores)
                if len(product_categ.replication_id) == len(product_categ.replication_id.filtered(
                        lambda x: x.date_replication == True)):
                    product_categ.update_replication = True

    def call_parent_product_category_master(self):
        parent_product_categories = self.env['product.category'].search(
            [('parent_id', '=', False), ('update_replication', '=', False)], order='id asc')
        if parent_product_categories:
            self.replicate_product_categories(parent_product_categories)

    def call_child_product_category_master(self):
        child_product_categories = self.env['product.category'].search(
            [('parent_id', '!=', False), ('update_replication', '=', False)], order='id asc')
        if child_product_categories:
            self.replicate_product_categories(child_product_categories)

    def call_product_attributes_master(self):
        product_attributes = self.env['product.attribute'].search([('update_replication', '=', False)],
                                                                  order='id asc')
        if product_attributes:
            for product_attribute in product_attributes:
                stores = product_attribute.product_attribute_replication_id.filtered(
                    lambda
                        x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if not stores:
                    product_attributes.get_stores_data()
                    stores = product_attribute.product_attribute_replication_id.filtered(
                        lambda
                            x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if stores:
                    product_attribute.send_replication_data_to_store(stores)
                    if len(product_attribute.product_attribute_replication_id) == len(
                            product_attribute.product_attribute_replication_id.filtered(
                                lambda x: x.date_replication == True)):
                        product_attribute.update_replication = True

    def call_product_template_master(self):
        product_template_ids = self.env['product.template'].search(
            [('active', '=', True), ('update_replication', '=', False)], order='id asc')
        if product_template_ids:
            for product_template_id in product_template_ids:
                stores = product_template_id.product_replication_id.filtered(
                    lambda
                        x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if not stores:
                    product_template_id.get_stores_data()
                    stores = product_template_id.product_replication_id.filtered(
                        lambda
                            x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if stores:
                    product_template_id.send_replication_data_to_store(stores)
                    if len(product_template_id.product_replication_id) == len(
                            product_template_id.product_replication_id.filtered(
                                lambda x: x.date_replication == True)):
                        product_template_id.update_replication = True

    @api.model
    def create(self, vals_list):
        res = super(HoStoreMaster, self).create(vals_list)
        return res

    def call_product_product_master(self):
        product_ids = self.env['product.product'].search(
            [('active', '=', True), ('update_replication', '=', False)], order='id asc')
        if product_ids:
            for product_id in product_ids:
                stores = product_id.product_replication_list_id.filtered(
                    lambda
                        x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if not stores:
                    product_id.button_fetch_replication_data()
                    stores = product_id.product_replication_list_id.filtered(
                        lambda
                            x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if stores:
                    product_id.send_replication_data_to_store(stores)
                    if len(product_id.product_replication_list_id) == len(
                            product_id.product_replication_list_id.filtered(
                                lambda x: x.date_replication == True)):
                        product_id.update_replication = True

    def call_hr_employee_master(self):
        hr_employee_ids = self.env['hr.employee'].search(
            [('company_id.name', '=', self.nhcl_store_name.company_id.name), ('update_replication', '=', False)],
            order='id asc')
        if hr_employee_ids:
            for hr_employee_id in hr_employee_ids:
                stores = hr_employee_id.hr_employee_replication_id.filtered(
                    lambda
                        x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if not stores:
                    hr_employee_id.get_stores_data()
                    stores = hr_employee_id.hr_employee_replication_id.filtered(
                        lambda
                            x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if stores:
                    hr_employee_id.send_replication_data_to_store(stores)
                    if len(hr_employee_id.hr_employee_replication_id) == len(
                            hr_employee_id.hr_employee_replication_id.filtered(
                                lambda x: x.date_replication == True)):
                        hr_employee_id.update_replication = True

    def call_master_functions(self):
        self.call_parent_product_category_master()
        self.call_hr_employee_master()
        self.call_product_attributes_master()
        self.call_child_product_category_master()
        self.call_product_template_master()
        self.call_product_product_master()

    @api.model
    def masters_job_scheduler_for_old_store(self):
        old_stores = self.search(
            [('nhcl_sink', '=', True), ('nhcl_active', '=', True), ('nhcl_store_type', '!=', "ho")])
        for old_store in old_stores:
            old_store.call_master_functions()

    def call_Ho_delivery_orders(self):
        delivery_orders = self.env['stock.picking'].search(
            [('picking_type_code', '=', 'outgoing'), ('nhcl_delivery_status', '=', False), ('state', '=', 'done')])
        for delivery in delivery_orders:
            delivery.get_delivery_orders()

    def call_Ho_batch_orders(self):
        batch_orders = self.env['stock.picking.batch'].search(
            [('nhcl_batch_status', '=', False), ('state', '=', 'done')])
        for batch in batch_orders:
            batch.get_batch_orders()

    def send_delivery_ho_store(self):
        self.call_Ho_delivery_orders()
        self.call_Ho_batch_orders()

    def action_show_store_details(self):
        for record in self:
            return {
                'name': 'Masters Data',
                'res_model': 'nhcl.ho.store.master',
                'view_mode': 'form',
                'type': 'ir.actions.act_window',
                'target': 'new',
                'res_id': record.id,
            }

    @api.model
    def create(self, vals):
        if not vals.get('nhcl_store_id'):
            vals['nhcl_store_id'] = self.env['ir.sequence'].next_by_code('nhcl.ho.store.master') or 'NEW'
        if vals.get('nhcl_store_type') == 'ho':
            ho_store = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '=', 'ho')])
            if ho_store:
                raise ValidationError("An HO already exists.")

        if vals.get('nhcl_store_name'):
            store_name_exists = self.env['nhcl.ho.store.master'].search(
                [('nhcl_store_name', '=', vals['nhcl_store_name'])])
            if store_name_exists:
                raise ValidationError("Store Name already exists.")

        if vals.get('nhcl_location_id'):
            location_exists = self.env['nhcl.ho.store.master'].search(
                [('nhcl_location_id', '=', vals['nhcl_location_id'])])
            if location_exists:
                raise ValidationError("Location already exists.")

        if vals.get('nhcl_terminal_ip'):
            ip_exists = self.env['nhcl.ho.store.master'].search(
                [('nhcl_terminal_ip', '=', vals['nhcl_terminal_ip'])])
            if ip_exists:
                raise ValidationError("Terminal IP already exists.")

        if vals.get('nhcl_port_no'):
            port_exists = self.env['nhcl.ho.store.master'].search(
                [('nhcl_port_no', '=', vals['nhcl_port_no'])])
            # if port_exists:
            #     raise ValidationError("Terminal PORT already exists.")

        if vals.get('nhcl_api_key'):
            api_key_exists = self.env['nhcl.ho.store.master'].search(
                [('nhcl_api_key', '=', vals['nhcl_api_key'])])
            if api_key_exists:
                raise ValidationError("API KEY already exists.")

        return super(HoStoreMaster, self).create(vals)

    def write(self, vals):
        if vals.get('nhcl_store_type') == 'ho':
            ho_store = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '=', 'ho'), ('id', '!=', self.id)])
            if ho_store:
                raise ValidationError("An HO already exists.")

        if vals.get('nhcl_store_name'):
            store_name_exists = self.env['nhcl.ho.store.master'].search([
                ('nhcl_store_name', '=', vals['nhcl_store_name']),
                ('id', '!=', self.id)
            ])
            if store_name_exists:
                raise ValidationError("Store Name already exists.")

        if vals.get('nhcl_location_id'):
            location_exists = self.env['nhcl.ho.store.master'].search([
                ('nhcl_location_id', '=', vals['nhcl_location_id']),
                ('id', '!=', self.id)
            ])
            if location_exists:
                raise ValidationError("Location already exists.")

        if vals.get('nhcl_terminal_ip'):
            ip_exists = self.env['nhcl.ho.store.master'].search(
                [('nhcl_terminal_ip', '=', vals['nhcl_terminal_ip'])])
            if ip_exists:
                raise ValidationError("Terminal IP already exists.")

        if vals.get('nhcl_port_no'):
            port_exists = self.env['nhcl.ho.store.master'].search(
                [('nhcl_port_no', '=', vals['nhcl_port_no'])])
            # if port_exists:
            #     raise ValidationError("Terminal PORT already exists.")

        if vals.get('nhcl_api_key'):
            api_key_exists = self.env['nhcl.ho.store.master'].search(
                [('nhcl_api_key', '=', vals['nhcl_api_key'])])
            if api_key_exists:
                raise ValidationError("API KEY already exists.")

        return super(HoStoreMaster, self).write(vals)

    def create_cmr_replication_log(self, model_name, record_id, status_code, function_required, status, details_status):
        ho_id = self.search(
            [('nhcl_active', '=', True), ('nhcl_store_type', '=', "ho")])
        vals = {
            'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.replication.log"),
            'nhcl_date_of_log': datetime.now(),
            'nhcl_source_id': ho_id.nhcl_store_id,
            'nhcl_source_name': ho_id.nhcl_store_name.id,
            'nhcl_destination_id': self.nhcl_store_id,
            'nhcl_destination_name': self.nhcl_store_name.id,
            'nhcl_model': model_name,
            'nhcl_record_id': record_id,
            'nhcl_status_code': status_code,
            'nhcl_function_required': function_required,
            'nhcl_status': status,
            'nhcl_details_status': details_status
        }
        self.env['nhcl.replication.log'].create(vals)

    def create_cmr_server_replication_log(self, status, details_status):
        vals = {
            'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.replication.log"),
            'nhcl_date_of_log': datetime.now(),
            'nhcl_destination_id': self.nhcl_store_id,
            'nhcl_destination_name': self.nhcl_store_name.id,
            'nhcl_status': status,
            'nhcl_details_status': details_status
        }
        self.env['nhcl.replication.log'].create(vals)

    def create_cmr_old_store_replication_log(self, model_name, record_id, status_code, function_required, status,
                                             details_status):
        ho_id = self.search(
            [('nhcl_active', '=', True), ('nhcl_store_type', '=', "ho")])
        vals = {
            'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.old.store.replication.log"),
            'nhcl_date_of_log': datetime.now(),
            'nhcl_source_id': ho_id.nhcl_store_id,
            'nhcl_source_name': ho_id.nhcl_store_name.id,
            'nhcl_destination_id': self.nhcl_store_id,
            'nhcl_destination_name': self.nhcl_store_name.id,
            'nhcl_model': model_name,
            # 'nhcl_processing_time': start_time,
            # 'nhcl_end_time': datetime.now(),
            'nhcl_record_id': record_id,
            'nhcl_status_code': status_code,
            'nhcl_function_required': function_required,
            'nhcl_status': status,
            'nhcl_details_status': details_status
        }
        self.env['nhcl.old.store.replication.log'].create(vals)

    def create_cmr_old_store_server_replication_log(self, status, details_status):
        vals = {
            'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.old.store.replication.log"),
            'nhcl_date_of_log': datetime.now(),
            'nhcl_destination_id': self.nhcl_store_id,
            'nhcl_destination_name': self.nhcl_store_name.id,
            'nhcl_status': status,
            'nhcl_details_status': details_status
        }
        self.env['nhcl.old.store.replication.log'].create(vals)

    def create_cmr_transaction_replication_log(self, model_name, record_id, status_code, function_required, status,
                                               details_status):
        ho_id = self.search(
            [('nhcl_active', '=', True), ('nhcl_store_type', '=', "ho")])
        vals = {
            'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.transaction.replication.log"),
            'nhcl_date_of_log': datetime.now(),
            'nhcl_source_id': ho_id.nhcl_store_id,
            'nhcl_source_name': ho_id.nhcl_store_name.id,
            'nhcl_destination_id': self.nhcl_store_id,
            'nhcl_destination_name': self.nhcl_store_name.id,
            'nhcl_model': model_name,
            'nhcl_record_id': record_id,
            'nhcl_status_code': status_code,
            'nhcl_function_required': function_required,
            'nhcl_status': status,
            'nhcl_details_status': details_status
        }
        self.env['nhcl.transaction.replication.log'].create(vals)

    def create_cmr_transaction_server_replication_log(self, status, details_status):
        vals = {
            'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.transaction.replication.log"),
            'nhcl_date_of_log': datetime.now(),
            'nhcl_destination_id': self.nhcl_store_id,
            'nhcl_destination_name': self.nhcl_store_name.id,
            'nhcl_status': status,
            'nhcl_details_status': details_status
        }
        self.env['nhcl.transaction.replication.log'].create(vals)

    def create_cmr_store_replication_log(self, model_name, record_id, status_code, function_required, status,
                                         details_status):
        ho_id = self.search(
            [('nhcl_active', '=', True), ('nhcl_store_type', '=', "ho")])
        vals = {
            'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.store.replication.log"),
            'nhcl_date_of_log': datetime.now(),
            'nhcl_source_id': self.nhcl_store_id,
            'nhcl_source_name': self.nhcl_store_name.id,
            'nhcl_destination_id': ho_id.nhcl_store_id,
            'nhcl_destination_name': ho_id.nhcl_store_name.id,
            'nhcl_model': model_name,
            'nhcl_record_id': record_id,
            'nhcl_status_code': status_code,
            'nhcl_function_required': function_required,
            'nhcl_status': status,
            'nhcl_details_status': details_status
        }
        self.env['nhcl.store.replication.log'].create(vals)

    def create_cmr_store_server_replication_log(self, status, details_status):
        ho_id = self.search(
            [('nhcl_active', '=', True), ('nhcl_store_type', '=', "ho")])
        vals = {
            'nhcl_serial_no': self.env['ir.sequence'].next_by_code("nhcl.transaction.replication.log"),
            'nhcl_date_of_log': datetime.now(),
            'nhcl_destination_id': ho_id.nhcl_store_id,
            'nhcl_destination_name': ho_id.nhcl_store_name.id,
            'nhcl_status': status,
            'nhcl_details_status': details_status
        }
        self.env['nhcl.transaction.replication.log'].create(vals)

    # New Store Schedular Action #

    def replicate_product_categories_to_store(self, product_categories):
        for product_categ in product_categories:
            stores = product_categ.replication_id.filtered(
                lambda
                    x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
            if not stores:
                product_categ.get_stores_data()
                stores = product_categ.replication_id.filtered(
                    lambda
                        x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
            if stores:
                product_categ.send_replication_data_to_store(stores)
                if len(product_categ.replication_id) == len(product_categ.replication_id.filtered(
                        lambda x: x.date_replication == True)):
                    product_categ.update_replication = True

    def call_new_store_parent_product_category_master(self, old_store):
        if self.nhcl_sink == False and old_store == True:
            parent_product_categories = self.env['product.category'].search(
                [('parent_id', '=', False), ('update_replication', '=', True)], order='id asc')
        else:
            parent_product_categories = self.env['product.category'].search(
                [('parent_id', '=', False), ('update_replication', '=', False)], order='id asc')
        if parent_product_categories:
            self.replicate_product_categories_to_store(parent_product_categories)

    def call_new_store_child_product_category_master(self, old_store):
        if self.nhcl_sink == False and old_store == True:
            child_product_categories = self.env['product.category'].search(
                [('parent_id', '!=', False), ('update_replication', '=', True)], order='id asc')
        else:
            child_product_categories = self.env['product.category'].search(
                [('parent_id', '!=', False), ('update_replication', '=', False)], order='id asc')
        if child_product_categories:
            self.replicate_product_categories_to_store(child_product_categories)

    def call_new_store_hr_employee_master(self, old_store):
        if self.nhcl_sink == False and old_store == True:
            hr_employee_ids = self.env['hr.employee'].search(
                [('company_id.name', '=', self.nhcl_store_name.company_id.name), ('update_replication', '=', True)],
                order='id asc')

        else:
            hr_employee_ids = self.env['hr.employee'].search(
                [('company_id.name', '=', self.nhcl_store_name.company_id.name), ('update_replication', '=', False)],
                order='id asc')
        if hr_employee_ids:
            for hr_employee_id in hr_employee_ids:
                stores = hr_employee_id.hr_employee_replication_id.filtered(
                    lambda
                        x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if not stores:
                    hr_employee_id.get_stores_data()
                    stores = hr_employee_id.hr_employee_replication_id.filtered(
                        lambda
                            x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if stores:
                    hr_employee_id.send_replication_data_to_store(stores)
                    if len(hr_employee_id.hr_employee_replication_id) == len(
                            hr_employee_id.hr_employee_replication_id.filtered(
                                lambda x: x.date_replication == True)):
                        hr_employee_id.update_replication = True

    def call_new_store_product_attributes_master(self, old_store):
        if self.nhcl_sink == False and old_store == True:
            product_attributes = self.env['product.attribute'].search([('update_replication', '=', True)],
                                                                      order='id asc')

        else:
            product_attributes = self.env['product.attribute'].search([('update_replication', '=', False)],
                                                                      order='id asc')

        if product_attributes:
            for product_attribute in product_attributes:
                stores = product_attribute.product_attribute_replication_id.filtered(
                    lambda
                        x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if not stores:
                    product_attributes.get_stores_data()
                    stores = product_attribute.product_attribute_replication_id.filtered(
                        lambda
                            x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if stores:
                    product_attribute.send_replication_data_to_store(stores)
                    if len(product_attribute.product_attribute_replication_id) == len(
                            product_attribute.product_attribute_replication_id.filtered(
                                lambda x: x.date_replication == True)):
                        product_attribute.update_replication = True

    def call_new_store_product_template_master(self, old_store):
        if self.nhcl_sink == False and old_store == True:
            product_template_ids = self.env['product.template'].search(
                [('active', '=', True), ('update_replication', '=', True)], order='id asc')

        else:
            product_template_ids = self.env['product.template'].search(
                [('active', '=', True), ('update_replication', '=', False)], order='id asc')
        if product_template_ids:
            for product_template_id in product_template_ids:
                stores = product_template_id.product_replication_id.filtered(
                    lambda
                        x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if not stores:
                    product_template_id.get_stores_data()
                    stores = product_template_id.product_replication_id.filtered(
                        lambda
                            x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if stores:
                    product_template_id.send_replication_data_to_store(stores)
                    if len(product_template_id.product_replication_id) == len(
                            product_template_id.product_replication_id.filtered(
                                lambda x: x.date_replication == True)):
                        product_template_id.update_replication = True

    def call_new_store_product_product_master(self, old_store):

        if self.nhcl_sink == False and old_store == True:
            product_ids = self.env['product.product'].search([('active', '=', True), ('update_replication', '=', True)],
                                                             order='id asc')
        else:
            product_ids = self.env['product.product'].search(
                [('active', '=', True), ('update_replication', '=', False)], order='id asc')
        if product_ids:
            for product_id in product_ids:
                stores = product_id.product_replication_list_id.filtered(
                    lambda
                        x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if not stores:
                    product_id.button_fetch_replication_data()
                    stores = product_id.product_replication_list_id.filtered(
                        lambda
                            x: x.date_replication == False and x.nhcl_terminal_ip == self.nhcl_terminal_ip and x.nhcl_api_key == self.nhcl_api_key)
                if stores:
                    product_id.send_replication_data_to_store(stores)
                    if len(product_id.product_replication_list_id) == len(
                            product_id.product_replication_list_id.filtered(
                                lambda x: x.date_replication == True)):
                        product_id.update_replication = True

    def call_new_store_master_functions(self, old_store):
        if not self.nhcl_store_name:
            raise ValueError("Store name (nhcl_store_name) is not set")
        store = self.env['stock.warehouse'].sudo().search(
            [('name', '=', self.nhcl_store_name.name)], limit=1)
        if not store:
            raise ValueError(f"Store with name '{self.nhcl_store_name.name}' not found")
        model_names = [
            'product.category',
            'product.attribute',
            'product.template',
            'product.product',
            'hr.employee',
        ]

        for model_name in model_names:
            ir_model = self.env['ir.model'].search([('model', '=', model_name)], limit=1)
            if not ir_model:
                continue
            record_count = self.env[model_name].search_count([])
            self.env['master.data'].sudo().create({
                'sending_count': record_count,
                'created_count': 0,
                'pending_count': 0,
                'date_time': datetime.now(),
                'master_type': ir_model.id,
                'store_id': store.id,
            })

        self.call_new_store_parent_product_category_master(old_store)
        self.call_new_store_hr_employee_master(old_store)
        self.call_new_store_product_attributes_master(old_store)
        self.call_new_store_child_product_category_master(old_store)
        self.call_new_store_product_template_master(old_store)
        self.call_new_store_product_product_master(old_store)

    @api.model
    def masters_job_scheduler_for_new_store(self):
        old_stores = self.search(
            [('nhcl_sink', '=', True), ('nhcl_active', '=', True), ('nhcl_store_type', '!=', "ho")])
        new_stores = self.search(
            [('nhcl_sink', '=', False), ('nhcl_active', '=', True), ('nhcl_store_type', '!=', "ho")])
        for new_store in new_stores:
            if old_stores:
                new_store.call_new_store_master_functions(old_store=True)
            else:
                new_store.call_new_store_master_functions(old_store=False)


class StoreMasterLineData(models.Model):
    """Created nhcl.ho.store.master class to add fields and functions"""
    _name = "nhcl.store.master.line.data"
    _description = "HO/Store Master Line Data"

    nhcl_store_line_id = fields.Many2one('nhcl.store.master', string="Store Line")
    nhcl_store_line_ids = fields.Many2one('nhcl.ho.store.master', string="Store Line")
    model_id = fields.Many2one('ir.model', string='Resource')
    nhcl_line_data = fields.Boolean("Status", default=True)
