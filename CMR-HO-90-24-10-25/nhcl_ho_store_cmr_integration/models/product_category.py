import requests
from odoo import models, fields, api, _
import logging
import os
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class ProductCategory(models.Model):
    _inherit = "product.category"

    update_replication = fields.Boolean(string="Creation status")
    update_status = fields.Boolean(string="Update status")
    delete_status = fields.Boolean(string="Delete status")
    replication_id = fields.One2many('product.category.replication', 'product_replication_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')
    nhcl_create_status = fields.Boolean(string="Create Status")

    @api.model
    def get_pending_category(self):
        pending_category = self.search_count([('update_replication', '=', False)])
        return {
            'pending_category': pending_category,
        }

    def get_category_stores(self):
        return {
            'name': _('Product Categories'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.category',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_category_view').id,
            'context': {'create': False, 'delete': False, 'duplicate': False,'default_nhcl_selected_ids': self.ids},
        }

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM product_category")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(ProductCategory, self).create(vals)


    def get_stores_data(self):
        for line in self:
            replication_data = []
            ho_store_id = self.env['nhcl.ho.store.master'].search(
                [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
            no_ip_lines = line.replication_id.filtered(lambda x:x.nhcl_terminal_ip not in ho_store_id.mapped('nhcl_terminal_ip'))
            no_api_lines = line.replication_id.filtered(lambda x:x.nhcl_api_key not in ho_store_id.mapped('nhcl_api_key'))
            if no_ip_lines :
                no_ip_lines.unlink()
            elif no_api_lines:
                no_api_lines.unlink()
            existing_store_ids = line.replication_id.mapped('store_id.id')
            for i in ho_store_id:
                for j in i.nhcl_store_data_id:
                    if j.model_id.name == 'Product Category' and j.nhcl_line_data == True:
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
            line.update({'replication_id': replication_data})
            line.env.cr.commit()

    def send_replication_data(self):
        # for category in self:
        #     errors = []
        #     # Check parent replication chain before proceeding
        #     for line in category.replication_id:
        #         if not line.date_replication:
        #             store = line.store_id or line.master_store_id
        #             parent = category.parent_id
        #
        #             while parent:
        #                 parent_replication = parent.replication_id.filtered(
        #                     lambda r: r.store_id == store and r.date_replication
        #                 )
        #                 if not parent_replication:
        #                     errors.append(
        #                         _("Store '%s' is missing parent category '%s' "
        #                           "for replicating '%s'.")
        #                         % (store.display_name, parent.name, category.name)
        #                     )
        #                     break  # stop checking higher parents for this store
        #                 parent = parent.parent_id
        #
        #     if errors:
        #         raise ValidationError("\n".join(errors))
        # for category in self:
        #     # Check parent replication chain before proceeding
        #     for line in category.replication_id:
        #         if not line.date_replication:
        #             store = line.store_id or line.master_store_id  # adjust depending on your model
        #             parent = category.parent_id
        #
        #             while parent:
        #                 parent_replication = parent.replication_id.filtered(
        #                     lambda r: r.store_id == store and r.date_replication
        #                 )
        #                 if not parent_replication:
        #                     raise ValidationError(
        #                         _("Cannot replicate category '%s' to store '%s' "
        #                           "because parent category '%s' is not replicated.")
        #                         % (category.name, store.display_name, parent.name)
        #                     )
        #                 parent = parent.parent_id


        for line in self.replication_id:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                dest_category_url = f"http://{ho_ip}:{ho_port}/api/product.category/search"
                dest_category_domain = [('nhcl_id', '=', self.nhcl_id)]
                dest_category_domain1 = [('name', '=', self.parent_id.name), ('nhcl_id', '=', self.parent_id.nhcl_id)]
                dest_store_url = f"{dest_category_url}?domain={dest_category_domain}"
                dest_store_url1 = f"{dest_category_url}?domain={dest_category_domain1}"
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                try:
                    dest_category_data = requests.get(dest_store_url, headers=headers_source).json()
                    dest_categories = dest_category_data.get("data", [])
                    dest_category_data1 = requests.get(dest_store_url1, headers=headers_source).json()
                    dest_categories1 = dest_category_data1.get("data", [])
                    # category_id = dest_categories[0]["id"]
                    if dest_categories:
                        _logger.info(f" '{self.name}' Already exists as Category on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(f" '{self.name}' Already exists as Category on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        self.update_replication = True
                        # continue
                    try:
                        store_url_data = f"http://{ho_ip}:{ho_port}/api/product.category/create"
                        dest_parent_id = None
                        for category in dest_categories1:
                            if self.parent_id and category.get("name") == self.parent_id.name:
                                dest_parent_id = category.get("id")
                                break

                        if not dest_parent_id and self.parent_id:
                            _logger.info(f"Parent category '{self.parent_id.name}' not found in destination.")

                        category_list = {
                            'name': self.name,
                            'nhcl_id': self.nhcl_id,
                            'parent_id': dest_parent_id,
                            'property_account_income_categ_id': self.property_account_income_categ_id.id if self.property_account_income_categ_id else False,
                            'property_account_expense_categ_id': self.property_account_expense_categ_id.id if self.property_account_expense_categ_id else False,
                            'route_ids': [route.id for route in self.route_ids] if self.route_ids else False,
                            'total_route_ids': [route.id for route in self.total_route_ids] if self.total_route_ids else [],
                            # 'removal_strategy_id': self.removal_strategy_id if self.removal_strategy_id else None,
                            # 'packaging_reserve_method': self.packaging_reserve_method if self.packaging_reserve_method else None,
                            # 'property_valuation': self.property_valuation if self.property_valuation else None,
                            'property_cost_method': self.property_cost_method if self.property_cost_method else None,
                        }
                        # Send product category creation request
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[category_list])
                        stores_data.raise_for_status()
                        # Raise an exception for HTTP errors
                        stores_data.raise_for_status()

                        # Access the JSON content from the response
                        response_json = stores_data.json()

                        # Access specific values from the response (e.g., "message" or "responseCode")
                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create category {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create category  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log('product.category', self.id, 200,
                                                                                'add', 'failure', message)
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log('product.category',
                                                                                          self.id, 200, 'add', 'failure',
                                                                                          message)
                        else:
                            line.date_replication = True
                            self.update_replication = True
                            _logger.info(
                                f"Successfully create category {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully create category {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log('product.category', self.id, 200,
                                                                                'add', 'success', f"Successfully create category {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log('product.category',
                                                                                          self.id, 200, 'add', 'success',
                                                                                          f"Successfully create category {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.error(
                            f"'{self.name}' failed to create category '{ho_ip}' with name '{ho_port}'. Error: {e}")
                        logging.error(
                            f"'{self.name}' failed to create category '{ho_ip}' with name '{ho_port}'. Error: {e}")
                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('product.category',
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('product.category',
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(f" '{self.name}' Error checking Category on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Category on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
        self.env.cr.commit()

    def update_product_category(self):
        for line in self.replication_id:
            # if line.update_status == False and line.status == True:
            ho_ip = line.nhcl_terminal_ip
            ho_port = line.nhcl_port_no
            ho_api_key = line.nhcl_api_key
            store_url_data = f"http://{ho_ip}:{ho_port}/api/product.category/search"
            category_domain = self.nhcl_id
            cate_domain = [('nhcl_id', '=', category_domain)]
            store_url = f"{store_url_data}?domain={cate_domain}"
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}

            try:
                response = requests.get(store_url, headers=headers_source)
                response.raise_for_status()  # Raises an HTTPError for bad responses

                # Parse the JSON response
                data = response.json()  # Now `data` is a dictionary
                category_id_data = data.get("data", [])
                category_id = category_id_data[0]['id']
                if not category_id_data[0]['parent_id']:
                    product_list = {
                        'name': self.name,
                        'route_ids': [route.id for route in self.route_ids] if self.route_ids else [],
                        'removal_strategy_id': self.removal_strategy_id.id if self.removal_strategy_id else None,
                        'property_valuation': self.property_valuation if self.property_valuation else None,
                        'property_cost_method': self.property_cost_method if self.property_cost_method else None,
                    }
                else:
                    product_list = {
                        'name': self.name,
                        'parent_id': category_id_data[0]['parent_id'][0]['id'],
                        'removal_strategy_id': self.removal_strategy_id.id if self.removal_strategy_id else None,
                        'route_ids': [route.id for route in self.route_ids] if self.route_ids else [],
                        # 'property_valuation': self.property_valuation if self.property_valuation else None,
                        'property_cost_method': self.property_cost_method if self.property_cost_method else None,
                    }
                store_url_data1 = f"http://{ho_ip}:{ho_port}/api/product.category/{category_id}"

                # Update the product category
                update_response = requests.put(store_url_data1, headers=headers_source, json=product_list)
                update_response.raise_for_status()

                # Update the status after successful request
                line.update_status = True
                self.update_status = True
                _logger.info(f"'{self.name}' Successfully updated Category '{ho_ip}' with partner '{ho_port}'.")
                logging.info(f"'{self.name}' Successfully updated Category '{ho_ip}' with partner '{ho_port}'.")
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log('product.category',
                                                                    self.id, 200, 'update', 'success',
                                                                    f"'{self.name}' Successfully updated Category")
                else:
                    line.master_store_id.create_cmr_old_store_replication_log('product.category',
                                                                              self.id, 200, 'update', 'success',
                                                                              f"'{self.name}' Successfully updated Category")
            except requests.exceptions.RequestException as e:
                _logger.error(
                    f"'{self.name}' Failed to update Category '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                logging.error(
                    f"'{self.name}' Failed to update Category '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                line.update_status = False
                self.update_status = False
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log('product.category',
                                                                    self.id, 500, 'update', 'failure',
                                                                    e)
                else:
                    line.master_store_id.create_cmr_old_store_replication_log('product.category',
                                                                              self.id, 500, 'update', 'failure',
                                                                              e)

    def send_replication_data_to_store(self,existing_store_id):
        if existing_store_id:
            if not existing_store_id.date_replication:
                ho_ip = existing_store_id.nhcl_terminal_ip
                ho_port = existing_store_id.nhcl_port_no
                ho_api_key = existing_store_id.nhcl_api_key
                dest_category_url = f"http://{ho_ip}:{ho_port}/api/product.category/search"
                dest_category_domain = [('nhcl_id', '=', self.nhcl_id)]
                dest_category_domain1 = [('nhcl_id', '=', self.parent_id.nhcl_id)]
                # domain_str = json.dumps(dest_category_domain1)
                # encoded_domain = quote(domain_str)
                dest_store_url = f"{dest_category_url}?domain={dest_category_domain}"
                dest_store_url1 = f"{dest_category_url}?domain={dest_category_domain1}"
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                try:
                    dest_category_data = requests.get(dest_store_url, headers=headers_source)
                    dest_category_data.raise_for_status()
                    dest_category_data = dest_category_data.json()
                    dest_categories = dest_category_data.get("data", [])
                    dest_category_data1 = requests.get(dest_store_url1, headers=headers_source).json()
                    dest_categories1 = dest_category_data1.get("data", [])
                    if dest_categories:
                        _logger.info(
                            f" '{self.name}' Already exists as Category on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(
                            f" '{self.name}' Already exists as Category on '{ho_ip}' with partner '{ho_port}'.")
                        existing_store_id.date_replication = True

                    try:
                        store_url_data = f"http://{ho_ip}:{ho_port}/api/product.category/create"
                        dest_parent_id = None
                        for category in dest_categories1:
                            if self.parent_id and category.get("name") == self.parent_id.name:
                                dest_parent_id = category.get("id")
                                break

                        if not dest_parent_id and self.parent_id:
                            _logger.info(f"Parent category '{self.parent_id.name}' not found in destination.")

                        category_list = {
                            'name': self.name,
                            'nhcl_id': self.nhcl_id,
                            'parent_id': dest_parent_id,
                            'property_account_income_categ_id': self.property_account_income_categ_id.id if self.property_account_income_categ_id else False,
                            'property_account_expense_categ_id': self.property_account_expense_categ_id.id if self.property_account_expense_categ_id else False,
                            'route_ids': [route.id for route in self.route_ids] if self.route_ids else False,
                            'total_route_ids': [route.id for route in
                                                self.total_route_ids] if self.total_route_ids else False,
                            'property_cost_method': self.property_cost_method if self.property_cost_method else None,
                        }
                        # Send product category creation request
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[category_list])
                        stores_data.raise_for_status()
                        # Raise an exception for HTTP errors
                        stores_data.raise_for_status()

                        # Access the JSON content from the response
                        response_json = stores_data.json()

                        # Access specific values from the response (e.g., "message" or "responseCode")
                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create category {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create category  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                            if existing_store_id.master_store_id.nhcl_sink == False:
                                existing_store_id.master_store_id.create_cmr_replication_log('product.category', self.id, 200,
                                                                                'add', 'failure', message)
                            else:
                                existing_store_id.master_store_id.create_cmr_old_store_replication_log('product.category',
                                                                                          self.id, 200, 'add',
                                                                                          'failure',
                                                                                          message)
                        else:
                            existing_store_id.date_replication = True
                            _logger.info(
                                f"Successfully create category {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully create category {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if existing_store_id.master_store_id.nhcl_sink == False:
                                existing_store_id.master_store_id.create_cmr_replication_log('product.category', self.id, 200,
                                                                                'add', 'success',
                                                                                f"Successfully create category {self.name}")
                            else:
                                existing_store_id.master_store_id.create_cmr_old_store_replication_log('product.category',
                                                                                          self.id, 200, 'add',
                                                                                          'success',
                                                                                          f"Successfully create category {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.error(
                            f"'{self.name}' failed to create category '{ho_ip}' with name '{ho_port}'. Error: {e}")
                        logging.error(
                            f"'{self.name}' failed to create category '{ho_ip}' with name '{ho_port}'. Error: {e}")
                        existing_store_id.date_replication = False
                        if existing_store_id.master_store_id.nhcl_sink == False:
                            existing_store_id.master_store_id.create_cmr_replication_log('product.category',
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            existing_store_id.master_store_id.create_cmr_old_store_replication_log('product.category',
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Category on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Category on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
        self.env.cr.commit()


class ProductCategoryReplication(models.Model):
    _name = 'product.category.replication'

    product_replication_id = fields.Many2one('product.category', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Creation status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update status")
    delete_status = fields.Boolean(string="Delete status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')
