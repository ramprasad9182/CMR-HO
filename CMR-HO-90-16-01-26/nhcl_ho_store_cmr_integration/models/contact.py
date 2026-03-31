import requests

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class Contact(models.Model):
    _inherit = "res.partner"

    update_replication = fields.Boolean(string="Flag")
    contact_replication_id = fields.One2many('res.partner.replication', 'contact_replication_line_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")

    @api.model
    def get_pending_partner(self):
        pending_partner = self.search_count([('update_replication', '=', False)])
        return {
            'pending_partner': pending_partner,
        }

    def get_contact_stores(self):
        return {
            'name': _('Contact'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.contact',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_contact_view').id,
            'context': {'create': False, 'delete': False, 'duplicate': False,'default_nhcl_selected_ids': self.ids},
        }


    @api.model
    def create(self, vals):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM res_partner")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(Contact, self).create(vals)

    @api.depends('name')
    def _compute_warning_message(self):
        self.warning_message = ''
        if self.update_replication == False:
            self.warning_message = 'Oops! Integration has not been completed.'
        else:
            self.warning_message = 'Integration is Complete!'

    def get_stores_data(self):
        replication_data = []
        existing_store_ids = self.contact_replication_id.mapped('store_id.id')
        ho_store_id = self.env['nhcl.ho.store.master'].search([('nhcl_store_type', '!=', 'ho'),('nhcl_active', '=', True)])
        for i in ho_store_id:
            for j in i.nhcl_store_data_id:
                if j.model_id.name == 'Contact' and j.nhcl_line_data == True:
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
        self.update({'contact_replication_id': replication_data})

    def send_replication_data(self):
        for line in self.contact_replication_id:
            if line.date_replication == False:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                search_store_url_data = f"http://{ho_ip}:{ho_port}/api/res.partner/search"
                partner_domain = [('nhcl_id', '=', self.nhcl_id), ('mobile', '=', self.mobile),('email', '=', self.email)]
                store_url = f"{search_store_url_data}?domain={partner_domain}"
                partner_category_search_url = f"http://{ho_ip}:{ho_port}/api/res.partner.category/search"
                partner_category_domain = [('name', '=', self.group_contact.name), ('nhcl_id', '=', self.group_contact.nhcl_id)]
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
                        _logger.info(f" '{self.name}' Already exists as Contact on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(f" '{self.name}' Already exists as Contact on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        continue
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/res.partner/create"
                    partner_list = {
                        'name': self.name,
                        'company_type': self.company_type,
                        'street': self.street if self.street else None,
                        'street2': self.street2 if self.street2 else None,
                        'city': self.city if self.city else None,
                        'state_id': self.state_id.id if self.state_id else False,
                        'zip': self.zip if self.zip else None,
                        'country_id': self.country_id.id if self.country_id else False,
                        'vat': self.vat if self.vat else None,
                        'function': self.function if self.function else None,
                        'phone': self.phone if self.phone else None,
                        'mobile': self.mobile if self.mobile else None,
                        'email': self.email if self.email else None,
                        'website': self.website if self.website else None,
                        'contact_sequence': self.contact_sequence if self.contact_sequence else None,
                        'lang': self.lang if self.lang else None,
                        'barcode': self.barcode if self.barcode else None,
                        'ref': self.ref if self.ref else None,
                        'company_registry': self.company_registry if self.company_registry else None,
                        'receipt_reminder_email': self.receipt_reminder_email if self.receipt_reminder_email else None,
                        'l10n_in_pan': self.l10n_in_pan if self.l10n_in_pan else None,
                        'l10n_in_gst_treatment': self.l10n_in_gst_treatment if self.l10n_in_gst_treatment else None,
                        'nhcl_id': self.nhcl_id,
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
                            _logger.info(
                                f"Successfully created Partner {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(
                                f"Successfully created Partner {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                'add', 'success', f"Successfully created Partner {self.name}")
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(response_json['object_name'],
                                                                                          self.id, 200, 'add', 'success',
                                                                                          f"Successfully created Partner {self.name}")
                    except requests.exceptions.RequestException as e:
                        _logger.info(f"Failed to create Partner '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(f"Failed to create Partner '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        line.date_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('res.partner',
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('res.partner',
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Contact on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Contact on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


    def update_contact_replication_data(self):
        for line in self.contact_replication_id:
            ho_ip = line.nhcl_terminal_ip
            ho_port = line.nhcl_port_no
            ho_api_key = line.nhcl_api_key
            store_url_data = f"http://{ho_ip}:{ho_port}/api/res.partner/search"
            partner_domain = self.nhcl_id
            contact_domain = [('nhcl_id', '=', partner_domain)]
            store_url = f"{store_url_data}?domain={contact_domain}"
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
            try:
                response = requests.get(store_url, headers=headers_source)
                response.raise_for_status()  # Raises an HTTPError for bad responses

                # Parse the JSON response
                data = response.json()  # Now `data` is a dictionary
                contact_id_data = data.get("data", [])

                if not contact_id_data:
                    continue

                partner_id = contact_id_data[0]['id']
                partner_list = {
                    'name': self.name,
                    'street': self.street,
                    'street2': self.street2,
                    'city': self.city,
                    'state_id': self.state_id.id,
                    'zip': self.zip,
                    'vat': self.vat,
                    'phone': self.phone,
                    'mobile': self.mobile,
                    'website': self.website,
                }

                store_url_data1 = f"http://{ho_ip}:{ho_port}/api/res.partner/{partner_id}"

                # Update the product category
                update_response = requests.put(store_url_data1, headers=headers_source, json=partner_list)
                update_response.raise_for_status()

                # Update the status after successful request
                line.update_status = True
                self.update_status = True
                _logger.info(
                    f"'{self.name}' Successfully updated contact '{ho_ip}' with partner '{ho_port}'.")
                logging.info(
                    f"'{self.name}' Successfully updated contact '{ho_ip}' with partner '{ho_port}'.")

                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log('res.partner',
                                                                    self.id, 200, 'update', 'success',
                                                                    f"'{self.name}' Successfully updated contact")
                else:
                    line.master_store_id.create_cmr_old_store_replication_log('res.partner',
                                                                              self.id, 200, 'update', 'success',
                                                                              f"'{self.name}' Successfully updated contact")
            except requests.exceptions.RequestException as e:
                _logger.error(
                    f"'{self.name}' Failed to update contact '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                logging.error(
                    f"'{self.name}' Failed to update contact '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                line.update_status = False
                self.update_status = False
                line.date_replication = False
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log('res.partner',
                                                                    self.id, 500, 'update', 'failure',
                                                                    e)
                else:
                    line.master_store_id.create_cmr_old_store_replication_log('res.partner',
                                                                              self.id, 500, 'update', 'failure',
                                                                              e)


class ContactReplication(models.Model):
    _name = 'res.partner.replication'

    contact_replication_line_id = fields.Many2one('res.partner', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update Status")
    delete_status = fields.Boolean(string="Delete Status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')



