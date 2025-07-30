from odoo import models, fields, api
import logging
import requests
import json
from urllib.parse import quote

_logger = logging.getLogger(__name__)


class BulkAccount(models.TransientModel):
    _name = 'nhcl.bulk.account'

    nhcl_selected_ids = fields.Many2many('account.account', string='Accounts')
    nhcl_account_line_id = fields.One2many('bulk.process.line','account_id')

    @api.model
    def default_get(self, fields_list):
        res = super(BulkAccount, self).default_get(fields_list)
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            print(i.nhcl_store_name.name)
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Account' and j.nhcl_line_data == True:
                    vals = {
                        'store_id': i.id,
                        'is_required': "yes",
                    }
                    replication_data.append((0, 0, vals))
                res.update({'nhcl_account_line_id': replication_data})
        return res

    def button_replicate_account(self):
        for k in self.nhcl_selected_ids:
            k.get_stores_data()
            b = len(k.chart_of_account_id)
            a = self.env['account.account.replication'].search_count(
                [('account_replication_id', '=', k.id), ('date_replication', '=', True)])
            if a == b:
                k.update_replication = True
            else:
                k.update_replication = False
            for l in k.chart_of_account_id:
                tax_list = {
                    'name': k.name if k.name else None,
                    'code': k.code if k.code else None,
                    'account_type': k.account_type if k.account_type else None,
                    'currency_id': k.currency_id.id if k.currency_id.id else False,
                    'reconcile': k.reconcile if k.reconcile else None,
                    'deprecated': k.deprecated if k.deprecated else None,
                    'tax_ids': [tax.id for tax in k.tax_ids] if k.tax_ids else False,
                    # 'tax_ids': data for data in self.tax_ids ,
                    'tag_ids': [tag.id for tag in k.tag_ids] if k.tag_ids else False,
                    # 'allowed_journal_ids': self.allowed_journal_ids.id if self.allowed_journal_ids else False,
                    'allowed_journal_ids': [journal.id for journal in k.allowed_journal_ids] if k.allowed_journal_ids else False,
                    'nhcl_id':k.nhcl_id
                }
                for line in self.nhcl_account_line_id:
                    if line.is_required == 'yes':
                        ho_ip = line.store_id.nhcl_terminal_ip
                        ho_port = line.store_id.nhcl_port_no
                        ho_api_key = line.store_id.nhcl_api_key
                        headers_source = {
                            'api-key': ho_api_key,
                            'Content-Type': 'application/json'
                        }
                        store_url_exist_data = f"http://{ho_ip}:{ho_port}/api/account.account/search"
                        chart_acc_domain = [('nhcl_id', '=', k.nhcl_id)]
                        store_url = f"{store_url_exist_data}?domain={chart_acc_domain}"
                        try:
                            response = requests.get(store_url, headers=headers_source)
                            response.raise_for_status()  # Raises an HTTPError for bad responses

                            # Parse the JSON response
                            data = response.json()  # Now `data` is a dictionary
                            chart_acc_id_data = data.get("data", [])
                            # Check if Chart of Account already exists
                            if chart_acc_id_data:
                                _logger.info(
                                    f" '{k.name}' Already exists as Chart of Account on '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f" '{k.name}' Already exists as Chart of Account on '{ho_ip}' with partner '{ho_port}'.")
                                l.date_replication = True
                                continue
                            store_url_data = f"http://{ho_ip}:{ho_port}/api/account.account/create"
                            try:
                                stores_data = requests.post(store_url_data, headers=headers_source, json=[tax_list])
                                # Raise an exception for HTTP errors
                                stores_data.raise_for_status()

                                # Access the JSON content from the response
                                response_json = stores_data.json()

                                # Access specific values from the response (e.g., "message" or "responseCode")
                                message = response_json.get("message", "No message provided")
                                response_code = response_json.get("responseCode", "No response code provided")
                                if response_json.get("success") == False:
                                    _logger.info(
                                        f"Failed to create Chart of Account {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create Chart of Account  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                else:
                                    l.date_replication = True
                                    _logger.info(
                                        f"Successfully created Chart of Account {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully created Chart of Account {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            except requests.exceptions.RequestException as e:
                                _logger.info(
                                    f" '{k.name}'Failed to create Chart of Account '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                logging.error(
                                    f" '{k.name}' Failed to create Chart of Account '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        except requests.exceptions.RequestException as e:
                            _logger.info(
                                f" '{k.name}' Error checking Chart of Account on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            logging.error(
                                f" '{k.name}' Error checking Chart of Account on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class BulkContact(models.TransientModel):
    _name = 'nhcl.bulk.contact'

    nhcl_selected_ids = fields.Many2many('res.partner', string='Contacts')
    nhcl_contact_line_id = fields.One2many('bulk.process.line', 'partner_id')

    @api.model
    def default_get(self, fields_list):
        res = super(BulkContact, self).default_get(fields_list)
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Contact' and j.nhcl_line_data == True:
                    vals = {
                        'store_id': i.id,
                        'is_required': "yes",
                    }
                    replication_data.append((0, 0, vals))
                res.update({'nhcl_contact_line_id': replication_data})
        return res

    def button_replicate_contact(self):
        for k in self.nhcl_selected_ids:
            k.get_stores_data()
            b = len(k.contact_replication_id)
            a = self.env['res.partner.replication'].search_count(
                [('contact_replication_line_id', '=', k.id), ('date_replication', '=', True)])
            if a == b:
                k.update_replication = True
            else:
                k.update_replication = False
            for l in k.contact_replication_id:
                for line in self.nhcl_contact_line_id:
                    if line.is_required == 'yes':
                        ho_ip = line.nhcl_terminal_ip
                        ho_port = line.nhcl_port_no
                        ho_api_key = line.nhcl_api_key
                        headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                        search_store_url_data = f"http://{ho_ip}:{ho_port}/api/res.partner/search"
                        partner_domain = [('nhcl_id', '=', k.nhcl_id), ('mobile', '=', k.mobile),
                                          ('email', '=', k.email)]
                        store_url = f"{search_store_url_data}?domain={partner_domain}"
                        partner_category_search_url = f"http://{ho_ip}:{ho_port}/api/res.partner.category/search"
                        partner_category_domain = [('name', '=', k.group_contact.name),
                                                   ('nhcl_id', '=', k.group_contact.nhcl_id)]
                        partner_category_url = f"{partner_category_search_url}?domain={partner_category_domain}"

                        try:
                            response = requests.get(store_url, headers=headers_source)
                            response.raise_for_status()  # Raise an exception for bad responses
                            data = response.json()
                            contact_data = data.get("data", [])
                            partner_category_response = requests.get(partner_category_url, headers=headers_source)
                            partner_category_response_data = partner_category_response.json()
                            partner_category_data = partner_category_response_data.get("data", [])
                            partner_category_id = False
                            if partner_category_data:
                                partner_category_id = partner_category_data[0]['id']
                            # Check if Contact already exists
                            if contact_data:
                                _logger.info(
                                    f" '{k.name}' Already exists as Contact on '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f" '{k.name}' Already exists as Contact on '{ho_ip}' with partner '{ho_port}'.")
                                line.date_replication = True
                                continue
                            store_url_data = f"http://{ho_ip}:{ho_port}/api/res.partner/create"
                            partner_list = {
                                'name': k.name,
                                'company_type': k.company_type,
                                'street': k.street if k.street else None,
                                'street2': k.street2 if k.street2 else None,
                                'city': k.city if k.city else None,
                                'state_id': k.state_id.id if k.state_id else False,
                                'zip': k.zip if k.zip else None,
                                'country_id': k.country_id.id if k.country_id else False,
                                'vat': k.vat if k.vat else None,
                                'function': k.function if k.function else None,
                                'phone': k.phone if k.phone else None,
                                'mobile': k.mobile if k.mobile else None,
                                'email': k.email if k.email else None,
                                'website': k.website if k.website else None,
                                'contact_sequence': k.contact_sequence if k.contact_sequence else None,
                                'lang': k.lang if k.lang else None,
                                'barcode': k.barcode if k.barcode else None,
                                'ref': k.ref if k.ref else None,
                                'company_registry': k.company_registry if k.company_registry else None,
                                'receipt_reminder_email': k.receipt_reminder_email if k.receipt_reminder_email else None,
                                'l10n_in_pan': k.l10n_in_pan if k.l10n_in_pan else None,
                                'l10n_in_gst_treatment': k.l10n_in_gst_treatment if k.l10n_in_gst_treatment else None,
                                'nhcl_id': k.nhcl_id,
                                'group_contact': partner_category_id,
                            }
                            try:
                                stores_data = requests.post(store_url_data, headers=headers_source, json=[partner_list])
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
                                        f"Failed to create Partner {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create Partner  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                    if line.store_id.nhcl_sink == False:
                                        line.store_id.create_cmr_replication_log(response_json['object_name'],
                                                                                        k.id, 200,
                                                                                        'add', 'failure', message)
                                    else:
                                        line.store_id.create_cmr_old_store_replication_log(
                                            response_json['object_name'],
                                            k.id, 200, 'add', 'failure',
                                            message)
                                else:
                                    l.date_replication = True
                                    k.update_replication = True
                                    _logger.info(
                                        f"Successfully created Partner {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully created Partner {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            except requests.exceptions.RequestException as e:
                                _logger.info(f"Failed to create Partner '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                logging.error(
                                    f"Failed to create Partner '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                line.date_replication = False
                                if line.store_id.nhcl_sink == False:
                                    line.store_id.create_cmr_replication_log('res.partner',
                                                                                    k.id, 500, 'add', 'failure',
                                                                                    e)
                                else:
                                    line.store_id.create_cmr_old_store_replication_log('res.partner',
                                                                                              k.id, 500, 'add',
                                                                                              'failure',
                                                                                              e)
                        except requests.exceptions.RequestException as e:
                            _logger.info(
                                f" '{k.name}' Error checking Contact on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            logging.error(
                                f" '{k.name}' Error checking Contact on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class BulkCategory(models.TransientModel):
    _name = 'nhcl.bulk.category'

    nhcl_selected_ids = fields.Many2many('product.category', string="Categories")
    nhcl_category_line_id = fields.One2many('bulk.process.line', 'category_id')

    @api.model
    def default_get(self, fields_list):
        res = super(BulkCategory, self).default_get(fields_list)
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Product Category' and j.nhcl_line_data == True:
                    vals = {
                        'store_id': i.id,
                        'is_required': "yes",
                    }
                    replication_data.append((0, 0, vals))
                res.update({'nhcl_category_line_id': replication_data})
        return res

    def button_replicate_category(self):
        for k in self.nhcl_selected_ids:
            k.get_stores_data()
            b = len(k.replication_id)
            a = self.env['product.category.replication'].search_count(
                [('product_replication_id', '=', k.id), ('date_replication', '=', True)])
            if a == b:
                k.update_replication = True
            else:
                k.update_replication = False
            for l in k.replication_id:
                for line in self.nhcl_category_line_id:
                    if line.is_required == 'yes':
                        ho_ip = line.store_id.nhcl_terminal_ip
                        ho_port = line.store_id.nhcl_port_no
                        ho_api_key = line.store_id.nhcl_api_key
                        dest_category_url = f"http://{ho_ip}:{ho_port}/api/product.category/search"
                        dest_category_domain = [('nhcl_id', '=', k.parent_id.nhcl_id)]
                        dest_category_domain1 = [('name', '=', k.parent_id.name), ('nhcl_id', '=', k.parent_id.nhcl_id)]
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
                                _logger.info(
                                    f" '{k.name}' Already exists as Category on '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f" '{k.name}' Already exists as Category on '{ho_ip}' with partner '{ho_port}'.")
                                l.date_replication = True
                                k.update_replication = True
                                # continue
                            try:
                                store_url_data = f"http://{ho_ip}:{ho_port}/api/product.category/create"
                                dest_parent_id = None
                                for category in dest_categories1:
                                    if category.get("nhcl_id") == k.parent_id.nhcl_id:
                                        dest_parent_id = category.get("id")
                                        break

                                if not dest_parent_id and k.parent_id:
                                    _logger.info(f"Parent category '{k.parent_id.name}' not found in destination.")

                                category_list = {
                                    'name': k.name,
                                    'nhcl_id': k.nhcl_id,
                                    'parent_id': dest_parent_id,
                                    'property_account_income_categ_id': k.property_account_income_categ_id.id if k.property_account_income_categ_id else False,
                                    'property_account_expense_categ_id': k.property_account_expense_categ_id.id if k.property_account_expense_categ_id else False,
                                    'route_ids': [route.id for route in k.route_ids] if k.route_ids else False,
                                    'total_route_ids': [route.id for route in
                                                        k.total_route_ids] if k.total_route_ids else False,
                                    'removal_strategy_id': k.removal_strategy_id if k.removal_strategy_id else None,
                                    'packaging_reserve_method': k.packaging_reserve_method if k.packaging_reserve_method else None,
                                    'property_valuation': k.property_valuation if k.property_valuation else None,
                                    'property_cost_method': k.property_cost_method if k.property_cost_method else None,
                                }
                                # Send product category creation request
                                stores_data = requests.post(store_url_data, headers=headers_source,
                                                            json=[category_list])
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
                                    if line.store_id.nhcl_sink == False:
                                        line.store_id.create_cmr_replication_log(response_json['object_name'],
                                                                                        k.id, 200,
                                                                                        'add', 'failure', message)
                                    else:
                                        line.store_id.create_cmr_old_store_replication_log(
                                            response_json['object_name'],
                                            k.id, 200, 'add', 'failure',
                                            message)
                                else:
                                    l.date_replication = True
                                    k.update_replication = True
                                    _logger.info(
                                        f"Successfully create category {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully create category {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")

                            except requests.exceptions.RequestException as e:
                                _logger.error(
                                    f"'{k.name}' failed to create category '{ho_ip}' with name '{ho_port}'. Error: {e}")
                                logging.error(
                                    f"'{k.name}' failed to create category '{ho_ip}' with name '{ho_port}'. Error: {e}")
                                l.date_replication = False
                                k.update_replication = False
                                if line.store_id.nhcl_sink == False:
                                    line.store_id.create_cmr_replication_log('product.category',
                                                                                    k.id, 500, 'add', 'failure',
                                                                                    e)
                                else:
                                    line.store_id.create_cmr_old_store_replication_log('product.category',
                                                                                              k.id, 500, 'add',
                                                                                              'failure',
                                                                                              e)
                        except requests.exceptions.RequestException as e:
                            _logger.info(
                                f" '{k.name}' Error checking Category on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            logging.error(
                                f" '{k.name}' Error checking Category on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class BulkAttribute(models.TransientModel):
    _name = 'nhcl.bulk.attribute'

    nhcl_selected_ids = fields.Many2many('product.attribute', string="Attribute's")
    nhcl_attribute_line_id = fields.One2many('bulk.process.line', 'attribute_id')

    @api.model
    def default_get(self, fields_list):
        res = super(BulkAttribute, self).default_get(fields_list)
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Product Attribute' and j.nhcl_line_data == True:
                    vals = {
                        'store_id': i.id,
                        'is_required': "yes",
                    }
                    replication_data.append((0, 0, vals))
                res.update({'nhcl_attribute_line_id': replication_data})
        return res

    def button_replicate_attribute(self):
        for k in self.nhcl_selected_ids:
            k.get_stores_data()
            b = len(k.product_attribute_replication_id)
            a = self.env['product.attribute.replication'].search_count(
                [('product_attribute_replication_line_id', '=', k.id), ('date_replication', '=', True)])
            if a == b:
                k.update_replication = True
            else:
                k.update_replication = False
            product_attribute_line = []
            for data in k.value_ids:
                product_attribute_line.append((0, 0, {
                    'name': data.name,
                    'nhcl_id': data.nhcl_id,
                    'is_custom': data.is_custom,
                    'html_color': data.html_color,
                    'image': data.image,
                    'default_extra_price': data.default_extra_price,

                }))

            product_attribute_list = {
                'name': k.name if k.name else None,
                'nhcl_id': k.nhcl_id,
                'display_type': k.display_type if k.display_type else None,
                'create_variant': k.create_variant if k.create_variant else None,
                'value_ids': product_attribute_line,
            }
            for l in k.product_attribute_replication_id:
                for line in self.nhcl_attribute_line_id:
                    if line.is_required == 'yes':
                        ho_ip = line.store_id.nhcl_terminal_ip
                        ho_port = line.store_id.nhcl_port_no
                        ho_api_key = line.store_id.nhcl_api_key
                        store_url_data = f"http://{ho_ip}:{ho_port}/api/product.attribute/search"
                        attribute_domain = [('nhcl_id', '=', k.nhcl_id)]
                        store_url = f"{store_url_data}?domain={attribute_domain}"
                        headers_source = {
                            'api-key': ho_api_key,
                            'Content-Type': 'application/json'
                        }
                        try:
                            response = requests.get(store_url, headers=headers_source)
                            response.raise_for_status()  # Raise an exception for bad responses
                            data = response.json()
                            attribute_data = data.get("data", [])

                            # Check if Attribute already exists
                            if attribute_data:
                                _logger.info(
                                    f" '{k.name}' Already exists as Attribute on '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f" '{k.name}' Already exists as Attribute on '{ho_ip}' with partner '{ho_port}'.")
                                l.date_replication = True
                                k.update_replication = True
                                continue
                            store_url_data = f"http://{ho_ip}:{ho_port}/api/product.attribute/create"
                            try:
                                stores_data = requests.post(store_url_data, headers=headers_source,
                                                            json=[product_attribute_list])
                                # Raise an exception for HTTP errors
                                stores_data.raise_for_status()

                                # Access the JSON content from the response
                                response_json = stores_data.json()

                                # Access specific values from the response (e.g., "message" or "responseCode")
                                message = response_json.get("message", "No message provided")
                                response_code = response_json.get("responseCode", "No response code provided")
                                if response_json.get("success") == False:
                                    _logger.info(
                                        f"Failed to create Attribute {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create Attribute  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                else:
                                    l.date_replication = True
                                    k.update_replication = True
                                    _logger.info(
                                        f"Successfully created Attribute {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully created Attribute {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")

                            except requests.exceptions.RequestException as e:
                                _logger.info(
                                    f"Failed to create Attribute '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                logging.error(
                                    f" '{k.name}' Failed to create Attribute '{ho_ip}' with partner '{ho_port}'. Error: {e}")

                                l.date_replication = False
                        except requests.exceptions.RequestException as e:
                            _logger.info(
                                f" '{k.name}' Error checking Attribute on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            logging.error(
                                f" '{k.name}' Error checking Attribute on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class BulkEmployee(models.TransientModel):
    _name = 'nhcl.bulk.employee'

    nhcl_selected_ids = fields.Many2many('hr.employee', string="Employee's")
    nhcl_employee_line_id = fields.One2many('bulk.process.line', 'employee_id')

    @api.model
    def default_get(self, fields_list):
        res = super(BulkEmployee, self).default_get(fields_list)
        selected_employee_ids = res.get('nhcl_selected_ids', [])
        extracted_ids = []
        for command in selected_employee_ids:
            if isinstance(command, tuple) and len(command) == 3 and command[0] == 6:
                extracted_ids.extend(command[2])
        if extracted_ids:
            replication_data = []
            employees = self.env['hr.employee'].browse(extracted_ids)

            for employee in employees:
                ho_store_ids = self.env['nhcl.ho.store.master'].search([
                    ('nhcl_store_type', '!=', 'ho'),
                    ('nhcl_active', '=', True),
                    ('nhcl_store_name.company_id.name', '=', employee.company_id.name),
                ])

                for ho_store in ho_store_ids:
                    for store_data in ho_store.nhcl_store_data_id:
                        if store_data.model_id.name == 'Employee' and store_data.nhcl_line_data:
                            vals = {
                                'store_id': ho_store.id,
                                'is_required': "yes",
                            }
                            replication_data.append((0, 0, vals))

            res.update({'nhcl_employee_line_id': replication_data})

        return res

    def button_replicate_employee(self):
        for k in self.nhcl_selected_ids:
            k.get_stores_data()
            b = len(k.hr_employee_replication_id)
            a = self.env['hr.employee.replication'].search_count(
                [('hr_employee_replication_line_id', '=', k.id), ('date_replication', '=', True)])
            if a == b:
                k.update_replication = True
            else:
                k.update_replication = False
            for l in k.hr_employee_replication_id:
                for line in self.nhcl_employee_line_id:
                    if line.is_required == 'yes':
                        ho_ip = line.store_id.nhcl_terminal_ip
                        ho_port = line.store_id.nhcl_port_no
                        ho_api_key = line.store_id.nhcl_api_key
                        store_get_url_data = f"http://{ho_ip}:{ho_port}/api/res.users/search"
                        manager_data_base_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                        nhcl_id = k.parent_id.nhcl_id
                        parent_name = k.parent_id.name
                        work_email = k.parent_id.work_email
                        work_email_user = k.work_email
                        user_domain = f"?domain=[('nhcl_id','=',\"{nhcl_id}\")]"
                        emp_manager_domain = f"?domain=[('nhcl_id','=',\"{nhcl_id}\")]"
                        emp_user_data = store_get_url_data + user_domain
                        emp_manager_data = manager_data_base_url + emp_manager_domain
                        headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                        search_store_url_data = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                        partner_domain = [('nhcl_id', '=', k.nhcl_id)]
                        store_url = f"{search_store_url_data}?domain={partner_domain}"
                        try:
                            response = requests.get(store_url, headers=headers_source)
                            response.raise_for_status()  # Raises an HTTPError for bad responses

                            # Parse the JSON response
                            data = response.json()  # Now `data` is a dictionary
                            employee_id_data = data.get("data", [])
                            # Check if Employee already exists
                            if employee_id_data:
                                _logger.info(
                                    f" '{k.name}' Already exists as Employee on '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f" '{k.name}' Already exists as Employee on '{ho_ip}' with partner '{ho_port}'.")
                                l.date_replication = True
                                continue
                            store_url_data = f"http://{ho_ip}:{ho_port}/api/hr.employee/create"
                            try:
                                manager_id = False
                                employee_get_data = requests.get(emp_manager_data, headers=headers_source).json()
                                employee_data = employee_get_data.get("data", [])
                                if employee_data:
                                    manager_id = employee_data[0]['id']
                                else:
                                    _logger.info(
                                        f"No manager found for '{parent_name}' with email '{work_email}'. Skipping replication.")
                                    # continue  # Skip the current iteration if no manager is found


                                    # Fetch user data
                                user_get_data = requests.get(emp_user_data, headers=headers_source).json()
                                user_data = user_get_data.get("data", [])
                                print(user_data)
                                if user_data:
                                    user_id = user_data[0]['id']
                                else:
                                    _logger.info(f"No user found with login '{work_email_user}'. Skipping replication.")
                                    # continue
                                employee_list = {
                                    'name': k.name if k.name else None,
                                    'sale_employee': k.sale_employee,
                                    'mobile_phone': k.mobile_phone if k.mobile_phone else None,
                                    'work_phone': k.work_phone if k.work_phone else None,
                                    'work_email': k.work_email if k.work_email else None,
                                    'parent_id': manager_id if k.parent_id else False,
                                    'coach_id': manager_id if k.parent_id else False,
                                    'private_street': k.private_street if k.private_street else None,
                                    'private_street2': k.private_street2 if k.private_street2 else None,
                                    'private_city': k.private_city if k.private_city else None,
                                    'private_state_id': k.private_state_id.id if k.private_state_id else False,
                                    'private_zip': k.private_zip if k.private_zip else None,
                                    'private_country_id': k.private_country_id.id if k.private_country_id else False,
                                    'private_email': k.private_email if k.private_email else None,
                                    'private_phone': k.private_phone if k.private_phone else None,
                                    # 'bank_account_id': self.bank_account_id.id,
                                    'km_home_work': k.km_home_work if k.km_home_work else None,
                                    'private_car_plate': k.private_car_plate if k.private_car_plate else None,
                                    'marital': k.marital if k.marital else None,
                                    'emergency_contact': k.emergency_contact if k.emergency_contact else None,
                                    'emergency_phone': k.emergency_phone if k.emergency_phone else None,
                                    'certificate': k.certificate if k.certificate else None,
                                    'identification_id': k.identification_id if k.identification_id else None,
                                    'ssnid': k.ssnid if k.ssnid else None,
                                    'passport_id': k.passport_id if k.passport_id else None,
                                    'gender': k.gender if k.gender else None,
                                    'study_field': k.study_field if k.study_field else None,
                                    'study_school': k.study_school if k.study_school else None,
                                    'visa_no': k.visa_no if k.visa_no else None,
                                    'permit_no': k.permit_no if k.permit_no else None,
                                    # 'birthday': self.birthday,
                                    # 'country_of_birth': self.country_of_birth.id if self.country_of_birth else None,
                                    'employee_type': k.employee_type if k.employee_type else None,
                                    # 'user_id': user_id,
                                    'pin': k.pin if k.pin else None,
                                    'place_of_birth': k.place_of_birth if k.place_of_birth else None,
                                    'children': k.children if k.children else None,
                                    'mobility_card': k.mobility_card if k.mobility_card else None,
                                    'hourly_cost': k.hourly_cost if k.hourly_cost else None,
                                    'barcode': k.barcode,
                                    "nhcl_id": k.nhcl_id,
                                }
                                print(employee_list)
                                try:
                                    stores_data = requests.post(store_url_data, headers=headers_source,
                                                                json=[employee_list])
                                    # Raise an exception for HTTP errors
                                    stores_data.raise_for_status()

                                    # Access the JSON content from the response
                                    response_json = stores_data.json()

                                    # Access specific values from the response (e.g., "message" or "responseCode")
                                    message = response_json.get("message", "No message provided")
                                    response_code = response_json.get("responseCode", "No response code provided")
                                    if response_json.get("success") == False:
                                        _logger.info(
                                            f"Failed to create Employee {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                        logging.error(
                                            f"Failed to create Employee  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                    else:
                                        l.date_replication = True
                                        k.update_replication = True
                                        _logger.info(
                                            f"Successfully created Employee {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                        logging.info(
                                            f"Successfully created Employee {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                except requests.exceptions.RequestException as e:
                                    _logger.info(
                                        f"Failed to create Employee '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                    logging.error(
                                        f"Failed to create Employee '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                    l.date_replication = False
                            except requests.exceptions.RequestException as e:
                                _logger.info(
                                    f" '{k.name}' Error checking Employee on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                logging.error(
                                    f" '{k.name}' Error checking Employee on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        except requests.exceptions.RequestException as e:
                            _logger.info(

                                f" '{k.name}' Error checking Employee on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            logging.error(
                                f" '{k.name}' Error checking Employee on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class BulkUser(models.TransientModel):
    _name = 'nhcl.bulk.user'

    nhcl_selected_ids = fields.Many2many('res.users', string='Users')
    nhcl_user_line_id = fields.One2many('bulk.process.line', 'user_id')

    @api.model
    def default_get(self, fields_list):
        res = super(BulkUser, self).default_get(fields_list)
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'User' and j.nhcl_line_data == True:
                    vals = {
                        'store_id': i.id,
                        'is_required': "yes",
                    }
                    replication_data.append((0, 0, vals))
                res.update({'nhcl_user_line_id': replication_data})
        return res

    def button_replicate_user(self):
        for k in self.nhcl_selected_ids:
            k.get_stores_data()
            b = len(k.user_replication_id)
            a = self.env['res.users.replication'].search_count(
                [('re_user_replication_line_id', '=', k.id), ('date_replication', '=', True)])
            if a == b:
                k.update_replication = True
            else:
                k.update_replication = False
            user_list = {
                 'name': k.name,
                'login': k.login,
                'nhcl_id':k.nhcl_id,
                'groups_id': [group.id for group in k.groups_id] if k.groups_id else False,

                # 'lang': self.lang,
                # 'notification_type': self.notification_type,
                # 'odoobot_state': self.odoobot_state,
                # 'import_approval_line': self.import_approval_line,
                # 'import_purchase_order_line': self.import_purchase_order_line,
                # 'import_sale_order_line': self.import_sale_order_line,
                # 'import_account_move_line': self.import_account_move_line,
                # 'import_stock_move_line': self.import_stock_move_line,
                # 'import_bom_line': self.import_bom_line,
                # 'allow_discount_button': self.allow_discount_button,
                # 'allow_numpad_button': self.allow_numpad_button,
                # 'allow_plusminus_button': self.allow_plusminus_button,
                # 'allow_qty_button': self.allow_qty_button,
                # 'allow_remove_button': self.allow_remove_button,
                # 'allow_price_button': self.allow_price_button,
                # 'allow_payment_button': self.allow_payment_button,
                # 'allow_refund_button': self.allow_refund_button,
                # 'allow_customer_selection': self.allow_customer_selection,
                # 'allow_new_order_button': self.allow_new_order_button,
            }
            for l in k.user_replication_id:
                for line in self.nhcl_user_line_id:
                    if line.is_required == 'yes':
                        ho_ip = line.store_id.nhcl_terminal_ip
                        ho_port = line.store_id.nhcl_port_no
                        ho_api_key = line.store_id.nhcl_api_key
                        headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                        search_store_url_data = f"http://{ho_ip}:{ho_port}/api/res.users/search"
                        user_domain = [('nhcl_id', '=', k.nhcl_id)]
                        store_url = f"{search_store_url_data}?domain={user_domain}"
                        try:
                            response = requests.get(store_url, headers=headers_source)
                            response.raise_for_status()  # Raise an exception for bad responses
                            data = response.json()
                            user_data = data.get("data", [])

                            # Check if User already exists
                            if user_data:
                                _logger.info(
                                    f" '{k.name}' Already exists as User on '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f" '{k.name}' Already exists as User on '{ho_ip}' with partner '{ho_port}'.")
                                l.date_replication = True
                                continue
                            store_url_data = f"http://{ho_ip}:{ho_port}/api/res.users/create"
                            try:
                                stores_data = requests.post(store_url_data, headers=headers_source, json=[user_list])
                                # Raise an exception for HTTP errors
                                stores_data.raise_for_status()

                                # Access the JSON content from the response
                                response_json = stores_data.json()

                                # Access specific values from the response (e.g., "message" or "responseCode")
                                message = response_json.get("message", "No message provided")
                                response_code = response_json.get("responseCode", "No response code provided")
                                if response_json.get("success") == False:
                                    _logger.info(
                                        f"Failed to create User {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create User  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                else:
                                    l.date_replication = True
                                    k.update_replication = True
                                    _logger.info(
                                        f"Successfully created User {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully created User {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            except requests.exceptions.RequestException as e:
                                _logger.info(
                                    f" '{k.name}'Failed to create User '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                logging.error(
                                    f" '{k.name}' Failed to create User '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                l.date_replication = False
                        except requests.exceptions.RequestException as e:
                            _logger.info(
                                f" '{k.name}' Error checking User on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            logging.error(
                                f" '{k.name}' Error checking User on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class BulkFinYear(models.TransientModel):
    _name = 'nhcl.bulk.fin_year'

    nhcl_selected_ids = fields.Many2many('account.fiscal.year', string="Fiscal Year's")
    nhcl_fin_year_line_id = fields.One2many('bulk.process.line', 'fin_year_id')

    @api.model
    def default_get(self, fields_list):
        res = super(BulkFinYear, self).default_get(fields_list)
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Fiscal Year' and j.nhcl_line_data == True:
                    vals = {
                        'store_id': i.id,
                        'is_required': "yes",
                    }
                    replication_data.append((0, 0, vals))
                res.update({'nhcl_fin_year_line_id': replication_data})
        return res


    def button_replicate_fin_year(self): pass


class BulkTax(models.TransientModel):
    _name = 'nhcl.bulk.tax'

    nhcl_selected_ids = fields.Many2many('account.tax', string='Taxes')
    nhcl_tax_line_id = fields.One2many('bulk.process.line', 'tax_id')

    @api.model
    def default_get(self, fields_list):
        res = super(BulkTax, self).default_get(fields_list)
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Tax' and j.nhcl_line_data == True:
                    vals = {
                        'store_id': i.id,
                        'is_required': "yes",
                    }
                    replication_data.append((0, 0, vals))
                    print(vals)
                res.update({'nhcl_tax_line_id': replication_data})
        return res


    def button_replicate_tax(self):
        for k in self.nhcl_selected_ids:
            k.get_stores_data()
            b = len(k.account_tax_id)
            a = self.env['tax.replication'].search_count(
                [('tax_replication_id', '=', k.id), ('date_replication', '=', True)])
            if a == b:
                k.update_replication = True
            else:
                k.update_replication = False
            children_tax = []
            for data in k.children_tax_ids:
                children_tax.append((0, 0, {
                    'name': data.name,
                    'amount_type': data.amount_type,
                    'amount': data.amount,

                }))
            tax_list = {
                'name': k.name if k.name else None,
                'description': k.description if k.description else None,
                'tax_scope': k.tax_scope if k.tax_scope else None,
                'amount_type': k.amount_type if k.amount_type else None,
                'type_tax_use': k.type_tax_use if k.type_tax_use else None,
                'python_compute': k.python_compute if k.python_compute else None,
                'tax_group_id': k.tax_group_id.id if k.tax_group_id.id else False,
                'price_include': k.price_include if k.price_include else None,
                'invoice_label': k.invoice_label if k.invoice_label else None,
                'analytic': k.analytic if k.analytic else None,
                'min_amount': k.min_amount if k.min_amount else None,
                'max_amount': k.max_amount if k.max_amount else None,
                'include_base_amount': k.include_base_amount if k.include_base_amount else None,
                'is_base_affected': k.is_base_affected if k.is_base_affected else None,
                'l10n_in_reverse_charge': k.l10n_in_reverse_charge if k.l10n_in_reverse_charge else None,
                'country_id': k.country_id.id if k.country_id else False,
                'nhcl_id': k.nhcl_id,
                'children_tax_ids': children_tax,
            }
            for l in k.account_tax_id:
                for line in self.nhcl_tax_line_id:
                    if line.is_required == 'yes':
                        ho_ip = line.store_id.nhcl_terminal_ip
                        ho_port = line.store_id.nhcl_port_no
                        ho_api_key = line.store_id.nhcl_api_key
                        store_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                        tax_domain = [('nhcl_id', '=', k.nhcl_id)]
                        store_url = f"{store_url_data}?domain={tax_domain}"
                        headers_source = {
                            'api-key': ho_api_key,
                            'Content-Type': 'application/json'
                        }

                        try:
                            response = requests.get(store_url, headers=headers_source)
                            response.raise_for_status()  # Raise an exception for bad responses
                            data = response.json()
                            tax_acc_data = data.get("data", [])

                            # Check if tax already exists
                            if tax_acc_data:
                                _logger.info(
                                    f" '{k.name}' Already exists as Tax on '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f" '{k.name}' Already exists as Tax on '{ho_ip}' with partner '{ho_port}'.")
                                l.date_replication = True
                                continue

                            # Tax does not exist, so create it
                            store_url_data = f"http://{ho_ip}:{ho_port}/api/account.tax/create"
                            try:
                                stores_data = requests.post(store_url_data, headers=headers_source, json=[tax_list])
                                # Raise an exception for HTTP errors
                                stores_data.raise_for_status()

                                # Access the JSON content from the response
                                response_json = stores_data.json()

                                # Access specific values from the response (e.g., "message" or "responseCode")
                                message = response_json.get("message", "No message provided")
                                response_code = response_json.get("responseCode", "No response code provided")
                                if response_json.get("success") == False:
                                    _logger.info(
                                        f"Failed to create Tax {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create Tax  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                else:
                                    l.date_replication = True
                                    k.update_replication = True
                                    _logger.info(
                                        f"Successfully created Tax {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully created Tax {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")

                            except requests.exceptions.RequestException as e:
                                _logger.info(
                                    f" '{k.name}' Failed to create Tax on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                logging.error(
                                    f" '{k.name}' Failed to create Tax on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                l.date_replication = False

                        except requests.exceptions.RequestException as e:
                            _logger.info(
                                f" '{k.name}' Error checking Tax on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            logging.error(
                                f" '{k.name}' Error checking Tax on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class BulkProductTemplate(models.TransientModel):
    _name = 'nhcl.bulk.product_temp'

    nhcl_selected_ids = fields.Many2many('product.template', string='Product Template')
    nhcl_product_temp_line_id = fields.One2many('bulk.process.line', 'product_temp_id')

    @api.model
    def default_get(self, fields_list):
        res = super(BulkProductTemplate, self).default_get(fields_list)
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Product' and j.nhcl_line_data == True:
                    vals = {
                        'store_id': i.id,
                        'is_required': "yes",
                    }
                    replication_data.append((0, 0, vals))
                res.update({'nhcl_product_temp_line_id': replication_data})
        return res

    def button_replicate_product_temp(self):
        for k in self.nhcl_selected_ids:
            k.get_stores_data()
            b = len(k.product_replication_id)
            a = self.env['product.replication'].search_count(
                [('product_replication_id', '=', k.id), ('date_replication', '=', True)])
            if a == b:
                k.update_replication = True
            else:
                k.update_replication = False
            for l in k.product_replication_id:
                for line in self.nhcl_product_temp_line_id:
                    if line.is_required == 'yes':
                        ho_ip = line.store_id.nhcl_terminal_ip
                        ho_port = line.store_id.nhcl_port_no
                        ho_api_key = line.store_id.nhcl_api_key
                        product_category_search_url = f"http://{ho_ip}:{ho_port}/api/product.category/search"
                        category_nhcl_id = k.categ_id.nhcl_id
                        print(category_nhcl_id)
                        # category_domain = [('name','=',category_name)]
                        category_domain = f"?domain=[('nhcl_id','ilike',\"{category_nhcl_id}\")]"
                        category_url_data = product_category_search_url + category_domain
                        # category_url_data = f"{product_category_search_url}?domain={category_domain}"
                        headers_source = {
                            'api-key': ho_api_key,
                            'Content-Type': 'application/json'
                        }
                        search_store_url_data = f"http://{ho_ip}:{ho_port}/api/product.template/search"
                        prod_tmpl_domain = [('nhcl_id', '=', k.nhcl_id)]
                        store_url = f"{search_store_url_data}?domain={prod_tmpl_domain}"

                        search_store_attribute_value = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                        # prod_tmpl_domain = [('name', '=', self.name), ('default_code', '=', self.default_code)]
                        # store_url = f"{search_store_url_data}?domain={prod_tmpl_domain}"
                        try:
                            response = requests.get(store_url, headers=headers_source)
                            response.raise_for_status()  # Raise an exception for bad responses
                            data = response.json()
                            product_data = data.get("data", [])

                            attribute_value_response = requests.get(search_store_attribute_value,
                                                                    headers=headers_source)
                            attribute_value_response.raise_for_status()  # Raise an exception for bad responses
                            attribute_value_data = attribute_value_response.json()
                            attribute_value_data1 = attribute_value_data.get("data", [])
                            # Check if Product already exists
                            if product_data:
                                _logger.info(
                                    f" '{k.name}' Already exists as Product on '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f" '{k.name}' Already exists as Product on '{ho_ip}' with partner '{ho_port}'.")
                                l.date_replication = True
                                k.update_replication = True
                                continue

                            store_url_data = f"http://{ho_ip}:{ho_port}/api/product.template/create"
                            category_get_data = requests.get(category_url_data, headers=headers_source).json()
                            category_id_data = category_get_data.get("data", [])
                            print("category_id_data", category_id_data)
                            if category_id_data:
                                category_id = category_id_data[0]['id']
                                print(category_id)
                            else:
                                category_id = None
                                _logger.info(f"No Category found with '{k.name}'. Skipping replication.")
                                if line.store_id.nhcl_sink == False:
                                    line.store_id.create_cmr_replication_log(category_get_data['object_name'],
                                                                                    k.id, 500, 'add',
                                                                                    'failure',
                                                                                    f"No Category found with '{k.name}'. Skipping replication.")
                                else:
                                    line.store_id.create_cmr_old_store_replication_log(
                                        category_get_data['object_name'], k.id, 500,
                                        'add', 'failure',
                                        'No matching product attributes found. Skipping this attribute.')

                                # continue
                            product_attribute_line = []
                            for data in k.attribute_line_ids:
                                search_store_attribute = f"http://{ho_ip}:{ho_port}/api/product.attribute/search"
                                attribute1_domain = [('nhcl_id', '=', data.attribute_id.nhcl_id)]
                                attribute_url = f"{search_store_attribute}?domain={attribute1_domain}"
                                attribute_response = requests.get(attribute_url,
                                                                  headers=headers_source)
                                attribute_response.raise_for_status()  # Raise an exception for bad responses
                                attribute_data = attribute_response.json()
                                attribute_data1 = attribute_data.get("data", [])
                                attribute_id = attribute_data1[0]['id']
                                value_ids = []
                                for da_val in data.value_ids:
                                    search_store_attribute_value = f"http://{ho_ip}:{ho_port}/api/product.attribute.value/search"
                                    attribute_domain = [('nhcl_id', '=', da_val.nhcl_id)]
                                    attribute_value_url = f"{search_store_attribute_value}?domain={attribute_domain}"
                                    attribute_value_response = requests.get(attribute_value_url,
                                                                            headers=headers_source)
                                    attribute_value_response.raise_for_status()  # Raise an exception for bad responses
                                    attribute_value_data = attribute_value_response.json()
                                    attribute_value_data1 = attribute_value_data.get("data", [])
                                    if attribute_value_data1:
                                        if attribute_value_data1[0]['nhcl_id'] == da_val.nhcl_id:
                                            value_ids.append(attribute_value_data1[0]['id'])
                                product_attribute_line.append((0, 0, {
                                    'attribute_id': attribute_id,
                                    'value_ids': value_ids,
                                }))
                            tax_ids = []
                            for tax_id in k.taxes_id:
                                search_store_tax_value = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                                tax_domain = [('name', '=', tax_id.name)]
                                tax_value_url = f"{search_store_tax_value}?domain={tax_domain}"
                                tax_value_response = requests.get(tax_value_url,
                                                                  headers=headers_source)
                                tax_value_response.raise_for_status()  # Raise an exception for bad responses
                                tax_value_data = tax_value_response.json()
                                tax_data = tax_value_data.get("data", [])
                                if tax_data:
                                    tax_ids.append(tax_data[0]['id'])
                            supp_tax_ids = []
                            for sup_tax_id in k.supplier_taxes_id:
                                search_store_tax_value = f"http://{ho_ip}:{ho_port}/api/account.tax/search"
                                tax_domain = [('name', '=', sup_tax_id.name)]
                                tax_value_url = f"{search_store_tax_value}?domain={tax_domain}"
                                tax_value_response = requests.get(tax_value_url,
                                                                  headers=headers_source)
                                tax_value_response.raise_for_status()  # Raise an exception for bad responses
                                tax_value_data = tax_value_response.json()
                                tax_data = tax_value_data.get("data", [])
                                if tax_data:
                                    supp_tax_ids.append(tax_data[0]['id'])
                            print("product_attribute_line", product_attribute_line)
                            product_list = {
                                'name': k.name,
                                'nhcl_id':k.nhcl_id,
                                'category_abbr': k.category_abbr,
                                'uom_id': k.uom_id.id if k.uom_id else False,
                                'uom_po_id': k.uom_po_id.id if k.uom_po_id else False,
                                'detailed_type': k.detailed_type if k.detailed_type else None,
                                'nhcl_type': k.nhcl_type if k.nhcl_type else None,
                                'invoice_policy': k.invoice_policy if k.invoice_policy else None,
                                'segment': k.segment if k.segment else None,
                                'list_price': k.list_price if k.list_price else None,
                                'available_in_pos': k.available_in_pos if k.available_in_pos else None,
                                'tracking': k.tracking if k.tracking else None,
                                'categ_id': category_id,
                                'l10n_in_hsn_code': k.l10n_in_hsn_code if k.l10n_in_hsn_code else None,
                                'default_code': k.default_code if k.default_code else None,
                                'web_product': k.web_product if k.web_product else None,
                                'product_description': k.product_description if k.product_description else None,
                                'to_weight': k.to_weight if k.to_weight else None,
                                'weight': k.weight if k.weight else None,
                                'volume': k.volume if k.volume else None,
                                'sale_delay': k.sale_delay if k.sale_delay else None,
                                'purchase_method': k.purchase_method if k.purchase_method else None,
                                'product_tag_ids': [tag.id for tag in k.product_tag_ids] if k.product_tag_ids else False,
                                'optional_product_ids': [product.id for product in k.optional_product_ids] if k.optional_product_ids else False,
                                'taxes_id': tax_ids,
                                'supplier_taxes_id': supp_tax_ids,
                                # 'pos_categ_ids': [categ.id for categ in k.pos_categ_ids] if k.pos_categ_ids else False,
                                # 'route_ids': [route.id for route in self.route_ids] if self.route_ids else False,
                                'responsible_id': k.responsible_id.id if k.responsible_id else False,
                                'property_stock_production': k.property_stock_production.id if k.property_stock_production else False,
                                'property_stock_inventory': k.property_stock_inventory.id if k.property_stock_inventory else False,
                                'property_account_income_id': k.property_account_income_id.id if k.property_account_income_id else False,
                                'property_account_expense_id': k.property_account_expense_id.id if k.property_account_expense_id else False,
                                'property_account_creditor_price_difference': k.property_account_creditor_price_difference.id if k.property_account_creditor_price_difference else False,
                                'attribute_line_ids': product_attribute_line,

                            }
                            print("product_list", product_list)
                            try:
                                stores_data = requests.post(store_url_data, headers=headers_source, json=[product_list])
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
                                        f"Failed to create Product {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create Product  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                    if line.store_id.nhcl_sink == False:
                                        line.store_id.create_cmr_replication_log(response_json['object_name'],
                                                                                        k.id, 200,
                                                                                        'add', 'failure', message)
                                    else:
                                        line.store_id.create_cmr_old_store_replication_log(
                                            response_json['object_name'],
                                            k.id, 200, 'add', 'failure',
                                            message)

                                else:
                                    l.date_replication = True
                                    k.update_replication = True
                                    _logger.info(
                                        f"Successfully create Product {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully create Product {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")

                            except requests.exceptions.RequestException as e:
                                _logger.info(
                                    f" '{k.name}'Failed to create Product '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                logging.error(
                                    f" '{k.name}' Failed to create Product '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                                l.date_replication = False
                                k.update_replication = False
                                if line.store_id.nhcl_sink == False:
                                    line.store_id.create_cmr_replication_log('product.template',
                                                                                    k.id, 500, 'add', 'failure',
                                                                                    e)
                                else:
                                    line.store_id.create_cmr_old_store_replication_log('product.template',
                                                                                              k.id, 500, 'add',
                                                                                              'failure',
                                                                                              e)
                        except requests.exceptions.RequestException as e:
                            _logger.info(
                                f" '{k.name}' Error checking Product on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            logging.error(
                                f" '{k.name}' Error checking Product on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class BulkProductProduct(models.TransientModel):
    _name = 'nhcl.bulk.product_prod'

    nhcl_selected_ids = fields.Many2many('product.product', string='Product Product')
    nhcl_product_prod_line_id = fields.One2many('bulk.process.line', 'product_prop_id')

    @api.model
    def default_get(self, fields_list):
        res = super(BulkProductProduct, self).default_get(fields_list)
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Product Variant' and j.nhcl_line_data == True:
                    vals = {
                        'store_id': i.id,
                        'is_required': "yes",
                    }
                    replication_data.append((0, 0, vals))
                res.update({'nhcl_product_prod_line_id': replication_data})
        return res

    def button_replicate_product_prop(self):
        for k in self.nhcl_selected_ids:
            k.button_fetch_replication_data()
            b = len(k.product_replication_list_id)
            a = self.env['product.product.replication'].search_count(
                [('product_product_replication_id', '=', k.id), ('date_replication', '=', True)])
            if a == b:
                k.update_replication = True
            else:
                k.update_replication = False
            for l in k.product_replication_list_id:
                for line in self.nhcl_product_prod_line_id:
                    if line.is_required == 'yes':
                        ho_ip = line.store_id.nhcl_terminal_ip
                        ho_port = line.store_id.nhcl_port_no
                        ho_api_key = line.store_id.nhcl_api_key
                        headers_source = {
                            'api-key': ho_api_key,
                            'Content-Type': 'application/json'
                        }
                        try:
                            product_attribute_search_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"
                            if k.default_code:
                                product_display_name = len(k.default_code)
                                varient_domain = [
                                    ('nhcl_display_name', '=', k.display_name[product_display_name + 3:])]
                                # varient_domain = [('A-PURE SAREES-KANCHI FANCY-KANCHI GOLD SAREE 1+1', '=', self.display_name[product_display_name + 3:])]
                                print("if", varient_domain)
                            else:
                                varient_domain = [
                                    ('nhcl_display_name', '=', k.display_name)]
                                print(varient_domain)
                            product_template_name = k.product_tmpl_id.name
                            domain_str = json.dumps(varient_domain)
                            encoded_domain = quote(domain_str)

                            varient_url_data = f"{product_attribute_search_url}?domain={encoded_domain}"
                            product_varient_get_data = requests.get(varient_url_data, headers=headers_source).json()
                            # print("API Response:", json.dumps(product_attribute_get_data, indent=4))

                            varient_id_data = product_varient_get_data.get("data", [])
                            print(varient_id_data)
                            if not varient_id_data:
                                _logger.info(
                                    f"No matching product varints found {k.product_tmpl_id.name}. Skipping this attribute.")
                                logging.info(
                                    f"No matching product varints found {k.product_tmpl_id.name}. Skipping this attribute.")
                                if line.store_id.nhcl_sink == False:
                                    line.store_id.create_cmr_replication_log(
                                        product_varient_get_data['object_name'],
                                        k.id, 500, 'add',
                                        'failure',
                                        f'No matching product attributess found {k.product_tmpl_id.name}. Skipping this attribute.')
                                else:
                                    line.store_id.create_cmr_old_store_replication_log(
                                        product_varient_get_data['object_name'], k.id, 500,
                                        'add', 'failure',
                                        f'No matching productt attributes found {k.product_tmpl_id.name}. Skipping this attribute.')

                                continue
                            varient_id = varient_id_data[0]['id']
                            print(varient_id)
                            combination_indices = varient_id_data[0]['combination_indices']
                            product_list = {
                                'default_code': k.default_code,
                                'barcode': k.barcode,
                                'nhcl_id': k.nhcl_id,
                            }
                            print(product_list)
                            store_url_data = f"http://{ho_ip}:{ho_port}/api/product.product/{varient_id}"
                            response = requests.put(store_url_data, headers=headers_source, json=product_list)
                            response.raise_for_status()
                            response_json = response.json()

                            message = response_json.get("message", "No message provided")
                            response_code = response_json.get("responseCode", "No response code provided")
                            if response_json.get("success") == False:
                                _logger.info(
                                    f"Failed to create Product Variant {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                logging.error(
                                    f"Failed to create Product Variant  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                if line.store_id.nhcl_sink == False:
                                    line.store_id.create_cmr_replication_log(response_json['object_name'],
                                                                                    k.id, 200, 'add',
                                                                                    'failure', message)
                                else:
                                    line.store_id.create_cmr_old_store_replication_log(
                                        response_json['object_name'], k.id, 200,
                                        'add', 'failure', message)


                            else:
                                l.date_replication = True
                                k.update_replication = True
                                _logger.info(
                                    f"Successfully created Product Variant {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f"Successfully created Product Variant {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")

                        except requests.exceptions.RequestException as e:
                            _logger.error(
                                f"'{k.name}' Failed to update Product Variant'{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            logging.error(
                                f"'{k.name}' Failed to update Product Variant'{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            l.date_replication = False
                            k.update_replication = False
                            if line.store_id.nhcl_sink == False:
                                line.store_id.create_cmr_replication_log('product.product',
                                                                                k.id, 500, 'add', 'failure',
                                                                                e)
                            else:
                                line.store_id.create_cmr_old_store_replication_log('product.product',
                                                                                          k.id, 500, 'add',
                                                                                          'failure',
                                                                                          e)


class BulkLoyalty(models.TransientModel):
    _name = 'nhcl.bulk.loyalty'

    nhcl_selected_ids = fields.Many2many('loyalty.program', string='Program')
    nhcl_loyalty_line_id = fields.One2many('bulk.process.line', 'loyalty_id')

    @api.model
    def default_get(self, fields_list):
        res = super(BulkLoyalty, self).default_get(fields_list)
        replication_data = []
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Product Variant' and j.nhcl_line_data == True:
                    vals = {
                        'store_id': i.id,
                        'is_required': "yes",
                    }
                    replication_data.append((0, 0, vals))
                res.update({'nhcl_loyalty_line_id': replication_data})
        return res

    def button_replicate_loyalty(self):
        for k in self.nhcl_selected_ids:
            k.get_replication_store_list()
            b = len(k.loyalty_program_id)
            a = self.env['loyalty.program.replication'].search_count(
                [('loyalty_program_replication_id', '=', k.id), ('date_replication', '=', True)])
            if a == b:
                k.update_replication = True
            else:
                k.update_replication = False
            for l in k.loyalty_program_id:
                for line in self.nhcl_loyalty_line_id:
                    if line.is_required == 'yes':
                        ho_ip = line.store_id.nhcl_terminal_ip
                        ho_port = line.store_id.nhcl_port_no
                        ho_api_key = line.store_id.nhcl_api_key
                        headers_source = {
                            'api-key': ho_api_key,
                            'Content-Type': 'application/json'
                        }
                        rule_ids_lst = []
                        rewards_lst = []
                        trigger_product_lst = []
                        coupon_lst = []
                        payment_program_discount_product_id = False
                        mail_template_id = False
                        report_id = False
                        for data in k.rule_ids:
                            product_lst = []
                            lot_lst = []
                            ref_product_lst = []
                            category_1_lst = []
                            category_2_lst = []
                            category_3_lst = []
                            category_4_lst = []
                            category_5_lst = []
                            category_6_lst = []
                            description_1_lst = []
                            description_2_lst = []
                            description_3_lst = []
                            description_4_lst = []
                            description_5_lst = []
                            description_6_lst = []
                            if data.category_1_ids:
                                category_1_lst = data.category_1_ids.get_store_attribute_vals(ho_ip, ho_port,
                                                                                              headers_source)
                            if data.category_2_ids:
                                category_2_lst = data.category_2_ids.get_store_attribute_vals(ho_ip, ho_port,
                                                                                              headers_source)
                            if data.category_3_ids:
                                category_3_lst = data.category_3_ids.get_store_attribute_vals(ho_ip, ho_port,
                                                                                              headers_source)
                            if data.category_4_ids:
                                category_4_lst = data.category_4_ids.get_store_attribute_vals(ho_ip, ho_port,
                                                                                              headers_source)
                            if data.category_5_ids:
                                category_5_lst = data.category_5_ids.get_store_attribute_vals(ho_ip, ho_port,
                                                                                              headers_source)
                            if data.category_6_ids:
                                category_6_lst = data.category_6_ids.get_store_attribute_vals(ho_ip, ho_port,
                                                                                              headers_source)
                            if data.description_1_ids:
                                description_1_lst = data.description_1_ids.get_store_attribute_vals(ho_ip, ho_port,
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
                                ref_product_lst = data.ref_product_ids.get_store_products(ho_ip, ho_port,
                                                                                          headers_source)

                            for serial_id in data.serial_ids:
                                lot_search_url = f"http://{ho_ip}:{ho_port}/api/stock.lot/search"
                                lot_domain = [('name', '=', serial_id.name)]
                                lot_store_url = f"{lot_search_url}?domain={lot_domain}"
                                lot_data = requests.get(lot_store_url, headers=headers_source).json()
                                if not lot_data.get("data"):
                                    _logger.warning(
                                        f"Failed to add Serial Number, Because Serial No-'{serial_id.name}' does not exist at '{ho_ip}:{ho_port}'.")
                                    continue
                                lot_name = lot_data.get("data")[0]
                                lot_id = lot_name["id"]
                                lot_lst.append(lot_id)
                            product_category_id = False
                            if data.product_category_id:
                                product_category_id = data.product_category_id.get_store_category_id(ho_ip, ho_port,
                                                                                                     headers_source)
                            loyalty_line_lst = []
                            for loyalty_line in data.loyalty_line_id:
                                loyalty_line_product_search_url = f"http://{ho_ip}:{ho_port}/api/product.product/search"
                                loyalty_line_product_domain = [('barcode', '=', loyalty_line.product_id.barcode)]
                                loyalty_line_product_store_url = f"{loyalty_line_product_search_url}?domain={loyalty_line_product_domain}"
                                loyalty_line_product_data = requests.get(loyalty_line_product_store_url,
                                                                         headers=headers_source).json()
                                if not loyalty_line_product_data.get("data"):
                                    continue
                                loyalty_line_product_name = loyalty_line_product_data.get("data")[0]
                                loyalty_line_product_id = loyalty_line_product_name["id"]
                                loyalty_line_lot_search_url = f"http://{ho_ip}:{ho_port}/api/stock.lot/search"
                                loyalty_line_lot_domain = [('name', '=', loyalty_line.lot_id.name)]
                                loyalty_line_lot_store_url = f"{loyalty_line_lot_search_url}?domain={loyalty_line_lot_domain}"
                                loyalty_line_lot_data = requests.get(loyalty_line_lot_store_url,
                                                                     headers=headers_source).json()
                                if not loyalty_line_lot_data.get("data"):
                                    _logger.warning(
                                        f"Failed to add Serial Number, Because Serial No-'{loyalty_line.lot_id.name}' does not exist at '{ho_ip}:{ho_port}'.")
                                    continue
                                loyalty_line_lot_name = loyalty_line_lot_data.get("data")[0]
                                loyalty_line_lot_id = loyalty_line_lot_name["id"]
                                loyalty_line_vals = {
                                    'lot_id': loyalty_line_lot_id,
                                    'product_id': loyalty_line_product_id
                                }
                                loyalty_line_lst.append((0, 0, loyalty_line_vals))
                            rule_ids_lst.append((0, 0, {
                                'minimum_qty': data.minimum_qty,
                                'minimum_amount': data.minimum_amount,
                                'type_filter': data.type_filter,
                                'reward_point_amount': data.reward_point_amount,
                                'reward_point_mode': data.reward_point_mode,
                                # 'range_from': data.range_from,
                                # 'range_to': data.range_to,
                                'product_ids': product_lst,
                                'ref_product_ids': ref_product_lst,
                                # 'loyalty_line_id': loyalty_line_lst,
                                'serial_ids': lot_lst,
                                'category_1_ids': category_1_lst,
                                'category_2_ids': category_2_lst,
                                'category_3_ids': category_3_lst,
                                'category_4_ids': category_4_lst,
                                'category_5_ids': category_5_lst,
                                'category_6_ids': category_6_lst,
                                'description_1_ids': description_1_lst,
                                'description_2_ids': description_2_lst,
                                'description_3_ids': description_3_lst,
                                'description_4_ids': description_4_lst,
                                'description_5_ids': description_5_lst,
                                'description_6_ids': description_6_lst,
                                'product_category_id': product_category_id if product_category_id else False
                            }))
                        for reward in k.reward_ids:
                            rwd_product_lst = []
                            if reward.discount_product_ids:
                                rwd_product_lst = reward.discount_product_ids.get_store_products(ho_ip, ho_port,
                                                                                                 headers_source)
                            discount_product_category_id = False
                            if reward.discount_product_category_id:
                                discount_product_category_id = reward.discount_product_category_id.get_store_category_id(
                                    ho_ip,
                                    ho_port,
                                    headers_source)
                            rewards_lst.append((0, 0, {
                                'reward_type': reward.reward_type,
                                'discount': reward.discount,
                                'discount_mode': reward.discount_mode,
                                'discount_applicability': reward.discount_applicability,
                                'discount_max_amount': reward.discount_max_amount,
                                'required_points': reward.required_points,
                                'discount_product_ids': rwd_product_lst,
                                'discount_product_category_id': discount_product_category_id

                            }))
                        for vochur in k.coupon_ids:
                            coupon_lst.append((0, 0, {
                                'code': vochur.code,
                                'expiration_date': vochur.expiration_date.strftime(
                                    '%Y-%m-%d') if vochur.expiration_date else None,
                                'points': vochur.points,

                            }))
                        if k.trigger_product_ids:
                            trigger_product_lst = k.trigger_product_ids.get_store_products(ho_ip, ho_port,
                                                                                              headers_source)

                        if k.payment_program_discount_product_id:
                            payment_program_discount_product_id = k.payment_program_discount_product_id.get_store_products(
                                ho_ip,
                                ho_port,
                                headers_source)
                        if k.mail_template_id:
                            mail_template_id_url = f"http://{ho_ip}:{ho_port}/api/mail.template/search"
                            mail_template_id_domain = [('name', '=', k.mail_template_id.name)]
                            mail_template_id_store_url = f"{mail_template_id_url}?domain={mail_template_id_domain}"
                            mail_template_id_data = requests.get(mail_template_id_store_url,
                                                                 headers=headers_source).json()
                            if not mail_template_id_data.get("data"):
                                continue
                            mail_template_name = mail_template_id_data.get("data")[0]
                            mail_template_id = mail_template_name["id"]
                        if k.pos_report_print_id:
                            pos_report_print_url = f"http://{ho_ip}:{ho_port}/api/ir.actions.report/search"
                            pos_report_print_domain = [('name', '=', k.pos_report_print_id.name)]
                            pos_report_print_store_url = f"{pos_report_print_url}?domain={pos_report_print_domain}"
                            pos_report_print_data = requests.get(pos_report_print_store_url,
                                                                 headers=headers_source).json()
                            if not pos_report_print_data.get("data"):
                                continue
                            pos_report_print_name = pos_report_print_data.get("data")[0]
                            report_id = pos_report_print_name["id"]
                        tax_list = {
                            'name': k.name,
                            'program_type': k.program_type,
                            'portal_point_name': k.portal_point_name,
                            'currency_id': k.currency_id.id,
                            'portal_visible': k.portal_visible,
                            'trigger': k.trigger,
                            'applies_on': k.applies_on,
                            'date_from': k.date_from.strftime('%Y-%m-%d') if k.date_from else None,
                            'date_to': k.date_to.strftime('%Y-%m-%d') if k.date_to else None,
                            'limit_usage': k.limit_usage,
                            'pos_ok': k.pos_ok,
                            'nhcl_id': k.nhcl_id,
                            'rule_ids': rule_ids_lst,
                            'reward_ids': rewards_lst,
                            'coupon_ids': coupon_lst,
                            'trigger_product_ids': trigger_product_lst,
                            'mail_template_id': mail_template_id,
                            'pos_report_print_id': report_id,
                            'payment_program_discount_product_id': payment_program_discount_product_id[
                                0] if payment_program_discount_product_id else False
                        }
                        ho_ip = line.store_id.nhcl_terminal_ip
                        ho_port = line.store_id.nhcl_port_no
                        ho_api_key = line.store_id.nhcl_api_key
                        headers_source = {
                            'api-key': ho_api_key,
                            'Content-Type': 'application/json'
                        }
                        search_store_url_data = f"http://{ho_ip}:{ho_port}/api/loyalty.program/search"
                        partner_domain = [('nhcl_id', '=', k.nhcl_id)]
                        store_url = f"{search_store_url_data}?domain={partner_domain}"
                        store_url_data = f"http://{ho_ip}:{ho_port}/api/loyalty.program/create"
                        try:
                            response = requests.get(store_url, headers=headers_source)
                            response.raise_for_status()  # Raises an HTTPError for bad responses

                            # Parse the JSON response
                            data = response.json()  # Now `data` is a dictionary
                            loyalty_data = data.get("data", [])
                            # Check if Loyalty Program already exists
                            if loyalty_data:
                                _logger.info(
                                    f" '{k.name}' Already exists as Loyalty Program on '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(
                                    f" '{k.name}' Already exists as Loyalty Program on '{ho_ip}' with partner '{ho_port}'.")
                                l.date_replication = True
                                k.update_replication = True
                                continue
                            try:
                                stores_data = requests.post(store_url_data, headers=headers_source, json=[tax_list])
                                # Raise an exception for HTTP errors
                                stores_data.raise_for_status()

                                # Access the JSON content from the response
                                response_json = stores_data.json()

                                # Access specific values from the response (e.g., "message" or "responseCode")
                                message = response_json.get("message", "No message provided")
                                response_code = response_json.get("responseCode", "No response code provided")
                                if response_json.get("success") == False:
                                    _logger.info(
                                        f"Failed to create Loyalty Program {k.name} {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                                    logging.error(
                                        f"Failed to create Loyalty Program {k.name}  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                                else:
                                    l.date_replication = True
                                    k.update_replication = True
                                    _logger.info(
                                        f"Successfully created Loyalty Program {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                    logging.info(
                                        f"Successfully created Loyalty Program {k.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            except requests.exceptions.RequestException as e:
                                _logger.warning(
                                    f"Failed to create Loyalty Program '{k.name}' at '{ho_ip}:{ho_port}'. Error: {e}")
                                l.date_replication = False
                        except requests.exceptions.RequestException as e:
                            _logger.info(
                                f" '{k.name}' Error checking Loyalty Program on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            logging.error(
                                f" '{k.name}' Error checking Loyalty Program on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class BulkProcessLine(models.TransientModel):
    _name = 'bulk.process.line'

    account_id = fields.Many2one('nhcl.bulk.account')
    tax_id = fields.Many2one('nhcl.bulk.tax')
    fin_year_id = fields.Many2one('nhcl.bulk.fin_year')
    partner_id = fields.Many2one('nhcl.bulk.contact')
    employee_id = fields.Many2one('nhcl.bulk.employee')
    product_temp_id = fields.Many2one('nhcl.bulk.product_temp')
    category_id = fields.Many2one('nhcl.bulk.category')
    product_prop_id = fields.Many2one('nhcl.bulk.product_prod')
    user_id = fields.Many2one('nhcl.bulk.user')
    attribute_id = fields.Many2one('nhcl.bulk.attribute')
    loyalty_id = fields.Many2one('nhcl.bulk.loyalty')
    store_id = fields.Many2one('nhcl.ho.store.master', string='Store', domain=[('nhcl_store_type','!=','ho'),('nhcl_active', '=', True)])
    is_required = fields.Selection([('yes', 'YES'), ('no', 'NO')], string='Is Required')
