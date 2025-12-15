import requests

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    is_sale_person = fields.Selection([('yes','Yes'), ('no','No')], string="Sale Person")
    update_replication = fields.Boolean(string="Creation Status")
    update_status = fields.Boolean(string="Update status")
    delete_status = fields.Boolean(string="Delete status")
    hr_employee_replication_id = fields.One2many('hr.employee.replication', 'hr_employee_replication_line_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')



    @api.model
    def get_pending_employee(self):
        pending_employee = self.search_count([('update_replication', '=', False)])
        return {
            'pending_employee': pending_employee,
        }


    def get_employee_stores(self):
        return {
            'name': _('Employee'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.employee',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_employee_view').id,
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
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM hr_employee")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(HrEmployee, self).create(vals)

    def get_stores_data(self):
        for line in self:
            replication_data = []
            existing_store_ids = line.hr_employee_replication_id.mapped('store_id.id')
            ho_store_id = self.env['nhcl.ho.store.master'].sudo().search(
                [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True),
                 ('nhcl_store_name.company_id.name', '=', line.company_id.name)])
            for rec in line.hr_employee_replication_id:
                if rec.nhcl_terminal_ip not in ho_store_id.mapped('nhcl_terminal_ip'):
                    rec.unlink()
                elif rec.nhcl_api_key not in ho_store_id.mapped('nhcl_api_key'):
                    rec.unlink()
            for i in ho_store_id:
                for j in i.nhcl_store_data_id:
                    if j.model_id.name == 'Employee' and j.nhcl_line_data == True:
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
            line.update({'hr_employee_replication_id': replication_data})


    def send_replication_data(self):
        for line in self.hr_employee_replication_id:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                store_get_url_data = f"http://{ho_ip}:{ho_port}/api/res.users/search"
                manager_data_base_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                parent_name = self.parent_id.nhcl_id
                work_email = self.parent_id.work_email
                work_email_user = self.work_email
                user_domain = f"?domain=[('login','=',\"{work_email_user}\")]"
                emp_manager_domain = f"?domain=[('nhcl_id','=',\"{parent_name}\"),('work_email','=',\"{work_email}\")]"
                emp_user_data = store_get_url_data + user_domain
                emp_manager_data = manager_data_base_url + emp_manager_domain
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                search_store_url_data = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                partner_domain = [('name', '=', self.name), ('work_phone', '=', self.work_phone), ('work_email', '=', self.work_email), ('nhcl_id', '=', self.nhcl_id)]
                store_url = f"{search_store_url_data}?domain={partner_domain}"
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()
                    data = response.json()
                    employee_id_data = data.get("data", [])
                    # Check if Employee already exists
                    if employee_id_data:
                        _logger.info(
                            f" '{self.name}' Already exists as Employee on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(
                            f" '{self.name}' Already exists as Employee on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        self.update_replication = True
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
                        if user_data:
                            user_id = user_data[0]['id']
                        else:
                            _logger.info(f"No user found with login '{work_email_user}'. Skipping replication.")
                            # continue
                        employee_list = {
                            'name': self.name if self.name else None,
                            'sale_employee': self.sale_employee,
                            'mobile_phone': self.mobile_phone if self.mobile_phone else None,
                            'work_phone': self.work_phone if self.work_phone else None,
                            'work_email': self.work_email if self.work_email else None,
                            'parent_id': manager_id if self.parent_id else False,
                            'coach_id': manager_id if self.parent_id else False,
                            'private_street': self.private_street if self.private_street else None,
                            'private_street2': self.private_street2 if self.private_street2 else None,
                            'private_city': self.private_city if self.private_city else None,
                            'private_state_id': self.private_state_id.id if self.private_state_id else False,
                            'private_zip': self.private_zip if self.private_zip else None,
                            'private_country_id': self.private_country_id.id if self.private_country_id else False,
                            'private_email': self.private_email if self.private_email else None,
                            'private_phone': self.private_phone if self.private_phone else None,
                            # 'bank_account_id': self.bank_account_id.id,
                            'km_home_work': self.km_home_work if self.km_home_work else None,
                            'private_car_plate': self.private_car_plate if self.private_car_plate else None,
                            'marital': self.marital if self.marital else None,
                            'emergency_contact': self.emergency_contact if self.emergency_contact else None,
                            'emergency_phone': self.emergency_phone if self.emergency_phone else None,
                            'certificate': self.certificate if self.certificate else None,
                            'identification_id': self.identification_id if self.identification_id else None,
                            'ssnid': self.ssnid if self.ssnid else None,
                            'passport_id': self.passport_id if self.passport_id else None,
                            'gender': self.gender if self.gender else None,
                            'study_field': self.study_field if self.study_field else None,
                            'study_school': self.study_school if self.study_school else None,
                            'visa_no': self.visa_no if self.visa_no else None,
                            'permit_no': self.permit_no if self.permit_no else None,
                            # 'birthday': self.birthday,
                            # 'country_of_birth': self.country_of_birth.id if self.country_of_birth else None,
                            'employee_type': self.employee_type if self.employee_type else None,
                            # 'user_id': user_id,
                            'pin': self.pin if self.pin else None,
                            'place_of_birth': self.place_of_birth if self.place_of_birth else None,
                            'children': self.children if self.children else None,
                            'mobility_card': self.mobility_card if self.mobility_card else None,
                            # 'hourly_cost': self.hourly_cost if self.hourly_cost else None,
                            'barcode': self.barcode,
                            "nhcl_id":self.nhcl_id,

                        }
                        try:
                            stores_data = requests.post(store_url_data, headers=headers_source, json=[employee_list])

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
                                if line.master_store_id.nhcl_sink == False:
                                    line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                    'add', 'failure', message)
                                else:
                                    line.master_store_id.create_cmr_old_store_replication_log(
                                        response_json['object_name'], self.id, 200, 'add', 'failure', message)

                            else:
                                line.date_replication = True
                                self.update_replication = True
                                _logger.info(f"Successfully created Employee {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(f"Successfully created Employee {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                if line.master_store_id.nhcl_sink == False:
                                    line.master_store_id.create_cmr_replication_log(response_json['object_name'],
                                                                                    self.id, 200,
                                                                                    'add', 'success', f"Successfully created Employee {self.name}")
                                else:
                                    line.master_store_id.create_cmr_old_store_replication_log(
                                        response_json['object_name'], self.id, 200, 'add', 'success', f"Successfully created Employee {self.name}")

                        except requests.exceptions.RequestException as e:
                            _logger.info(f"Failed to create Employee '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            logging.error(f"Failed to create Employee '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            line.date_replication = False
                            self.update_replication = False
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log('hr.employee',
                                                                                self.id, 500, 'add', 'failure',
                                                                                e)
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log('hr.employee',
                                                                                          self.id, 500, 'add', 'failure',
                                                                                          e)
                    except requests.exceptions.RequestException as e:
                        _logger.info(
                        f" '{self.name}' Error checking Employee on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                           f" '{self.name}' Error checking Employee on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                except requests.exceptions.RequestException as e:
                    _logger.info(

                        f" '{self.name}' Error checking Employee on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Employee on '{ho_ip}' with partner '{ho_port}'. Error: {e}")

    def update_emplouyee_data(self):
        for line in self.hr_employee_replication_id:
            # if not line.update_status:
            ho_ip = line.nhcl_terminal_ip
            ho_port = line.nhcl_port_no
            ho_api_key = line.nhcl_api_key
            manager_data_base_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
            employee_id = self.nhcl_id
            employee_domain = [('nhcl_id', '=', employee_id)]
            emp_manager_data = f"{manager_data_base_url}?domain={employee_domain}"
            headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}

            # Fetch manager data
            employee_get_data = requests.get(emp_manager_data, headers=headers_source).json()
            employee_data = employee_get_data.get("data", [])
            if employee_data:
                manager_id = employee_data[0]['id']
            else:
                _logger.info(
                    f"No manager found for '{self.name}' with email . Skipping replication.")
                continue  # Skip the current iteration if no manager is found
            employee_list = {
                'name': self.name,
                'mobile_phone': self.mobile_phone,
                'work_phone': self.work_phone,
                'sale_employee': self.sale_employee,
                'pin': self.pin,
                'barcode': self.barcode,
                'work_email': self.work_email,

            }
            try:
                store_url_data1 = f"http://{ho_ip}:{ho_port}/api/hr.employee/{manager_id}"
                update_response = requests.put(store_url_data1, headers=headers_source, json=employee_list)
                update_response.raise_for_status()
                line.update_status = True
                self.update_status = True
                _logger.info(f"Successfully Updated Employee '{ho_ip}' with partner '{ho_port}'.")
                logging.info(f"Successfully Updated Employee '{ho_ip}' with partner '{ho_port}'.")
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log('hr.employee',
                                                                    self.id, 200, 'update', 'success',
                                                                    f"Successfully Updated Employee {self.name}")
                else:
                    line.master_store_id.create_cmr_old_store_replication_log('hr.employee',
                                                                              self.id, 200, 'update', 'success',
                                                                              f"Successfully Updated Employee {self.name}")
            except requests.exceptions.RequestException as e:
                _logger.info(f"Failed to update Employee '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                logging.error(f"Failed to update Employee '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                line.update_status = False
                self.update_status = False
                if line.master_store_id.nhcl_sink == False:
                    line.master_store_id.create_cmr_replication_log('hr.employee',
                                                                    self.id, 500, 'update', 'failure',
                                                                    e)
                else:
                    line.master_store_id.create_cmr_old_store_replication_log('hr.employee',
                                                                              self.id, 500, 'update', 'failure',
                                                                              e)


    def send_replication_data_to_store(self,stores):
        for line in stores:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                store_get_url_data = f"http://{ho_ip}:{ho_port}/api/res.users/search"
                manager_data_base_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                parent_name = self.parent_id.nhcl_id
                work_email = self.parent_id.work_email
                work_email_user = self.work_email
                user_domain = f"?domain=[('login','=',\"{work_email_user}\")]"
                emp_manager_domain = f"?domain=[('nhcl_id','=',\"{parent_name}\"),('work_email','=',\"{work_email}\")]"
                emp_user_data = store_get_url_data + user_domain
                emp_manager_data = manager_data_base_url + emp_manager_domain
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                search_store_url_data = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                partner_domain = [('name', '=', self.name), ('work_phone', '=', self.work_phone), ('work_email', '=', self.work_email), ('nhcl_id', '=', self.nhcl_id)]
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
                            f" '{self.name}' Already exists as Employee on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(
                            f" '{self.name}' Already exists as Employee on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        continue
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/hr.employee/create"
                    try:
                    # Fetch manager data
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
                        if user_data:
                            user_id = user_data[0]['id']
                        else:
                            _logger.info(f"No user found with login '{work_email_user}'. Skipping replication.")
                            # continue
                        employee_list = {
                            'name': self.name if self.name else None,
                            'sale_employee': self.sale_employee,
                            'mobile_phone': self.mobile_phone if self.mobile_phone else None,
                            'work_phone': self.work_phone if self.work_phone else None,
                            'work_email': self.work_email if self.work_email else None,
                            'parent_id': manager_id if self.parent_id else False,
                            'coach_id': manager_id if self.parent_id else False,
                            'private_street': self.private_street if self.private_street else None,
                            'private_street2': self.private_street2 if self.private_street2 else None,
                            'private_city': self.private_city if self.private_city else None,
                            'private_state_id': self.private_state_id.id if self.private_state_id else False,
                            'private_zip': self.private_zip if self.private_zip else None,
                            'private_country_id': self.private_country_id.id if self.private_country_id else False,
                            'private_email': self.private_email if self.private_email else None,
                            'private_phone': self.private_phone if self.private_phone else None,
                            'km_home_work': self.km_home_work if self.km_home_work else None,
                            'private_car_plate': self.private_car_plate if self.private_car_plate else None,
                            'marital': self.marital if self.marital else None,
                            'emergency_contact': self.emergency_contact if self.emergency_contact else None,
                            'emergency_phone': self.emergency_phone if self.emergency_phone else None,
                            'certificate': self.certificate if self.certificate else None,
                            'identification_id': self.identification_id if self.identification_id else None,
                            'ssnid': self.ssnid if self.ssnid else None,
                            'passport_id': self.passport_id if self.passport_id else None,
                            'gender': self.gender if self.gender else None,
                            'study_field': self.study_field if self.study_field else None,
                            'study_school': self.study_school if self.study_school else None,
                            'visa_no': self.visa_no if self.visa_no else None,
                            'permit_no': self.permit_no if self.permit_no else None,
                            'employee_type': self.employee_type if self.employee_type else None,
                            'pin': self.pin if self.pin else None,
                            'place_of_birth': self.place_of_birth if self.place_of_birth else None,
                            'children': self.children if self.children else None,
                            'mobility_card': self.mobility_card if self.mobility_card else None,
                                                               'barcode': self.barcode,
                            "nhcl_id":self.nhcl_id,

                        }
                        try:
                            stores_data = requests.post(store_url_data, headers=headers_source, json=[employee_list])

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
                                if line.master_store_id.nhcl_sink == False:
                                    line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                    'add', 'failure', message)
                                else:
                                    line.master_store_id.create_cmr_old_store_replication_log(
                                        response_json['object_name'], self.id, 200, 'add', 'failure', message)

                            else:
                                line.date_replication = True
                                _logger.info(f"Successfully created Employee {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                logging.info(f"Successfully created Employee {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                                if line.master_store_id.nhcl_sink == False:
                                    line.master_store_id.create_cmr_replication_log(response_json['object_name'],
                                                                                    self.id, 200,
                                                                                    'add', 'success', f"Successfully created Employee {self.name}")
                                else:
                                    line.master_store_id.create_cmr_old_store_replication_log(
                                        response_json['object_name'], self.id, 200, 'add', 'success', f"Successfully created Employee {self.name}")

                        except requests.exceptions.RequestException as e:
                            _logger.info(f"Failed to create Employee '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            logging.error(f"Failed to create Employee '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                            line.date_replication = False
                            self.update_replication = False
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log('hr.employee',
                                                                                self.id, 500, 'add', 'failure',
                                                                                e)
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log('hr.employee',
                                                                                          self.id, 500, 'add', 'failure',
                                                                                          e)
                    except requests.exceptions.RequestException as e:
                        _logger.info(
                        f" '{self.name}' Error checking Employee on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(
                           f" '{self.name}' Error checking Employee on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                except requests.exceptions.RequestException as e:
                    _logger.info(

                        f" '{self.name}' Error checking Employee on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Employee on '{ho_ip}' with partner '{ho_port}'. Error: {e}")

class HrEmployeeReplication(models.Model):
    _name = 'hr.employee.replication'

    hr_employee_replication_line_id = fields.Many2one('hr.employee', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update status")
    delete_status = fields.Boolean(string="Delete status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    update_replication = fields.Boolean(string="Creation Status")
    update_status = fields.Boolean(string="Update status")
    delete_status = fields.Boolean(string="Delete status")
    hr_department_replication_id = fields.One2many('hr.department.replication', 'hr_department_replication_line_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')



    @api.model
    def get_pending_employee(self):
        pending_employee = self.search_count([('update_replication', '=', False)])
        return {
            'pending_employee': pending_employee,
        }


    def get_employee_stores(self):
        return {
            'name': _('Employee'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.employee',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_employee_view').id,
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
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM hr_department")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(HrDepartment, self).create(vals)

    def get_stores_data(self):
        for line in self:
            replication_data = []
            existing_store_ids = line.hr_department_replication_id.mapped('store_id.id')
            ho_store_id = self.env['nhcl.ho.store.master'].sudo().search(
                [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True),
                 ])
            for rec in line.hr_department_replication_id:
                if rec.nhcl_terminal_ip not in ho_store_id.mapped('nhcl_terminal_ip'):
                    rec.unlink()
                elif rec.nhcl_api_key not in ho_store_id.mapped('nhcl_api_key'):
                    rec.unlink()
            for i in ho_store_id:
                for j in i.nhcl_store_data_id:
                    if j.model_id.name == 'Department' and j.nhcl_line_data == True:
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
            line.update({'hr_department_replication_id': replication_data})

    def send_replication_data(self):
        for line in self.hr_department_replication_id:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                store_get_url_data = f"http://{ho_ip}:{ho_port}/api/hr.department/search"
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                department_domain = [('nhcl_id', '=', self.nhcl_id)]
                store_url = f"{store_get_url_data}?domain={department_domain}"
                get_manager_data_base_url = f"http://{ho_ip}:{ho_port}/api/hr.employee/search"
                manager_domain = f"?domain=[('nhcl_id','=',\"{self.manager_id.nhcl_id}\"),('work_email','=',\"{self.manager_id.work_email}\")]"
                emp_manager_data = get_manager_data_base_url + manager_domain
                # Check if the department already exists
                try:
                    # Fetch existing department data
                    department_manager = requests.get(emp_manager_data, headers=headers_source).json()
                    department_manager_data = department_manager.get("data", [])
                    if department_manager_data:
                        manager_id = department_manager_data[0]['id']
                    else:
                        _logger.info(
                            f"No manager found for '{self.manager_id.name}' with email '{self.manager_id.work_email}'. Skipping replication.")
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()
                    data = response.json()
                    department_id_data = data.get("data", [])
                    if department_id_data:
                        _logger.info(
                            f" '{self.name}' Already exists as Department on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(
                            f" '{self.name}' Already exists as Department on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        continue
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/hr.department/create"
                    department_list = {
                        'name': self.name,
                        'manager_id': manager_id if self.manager_id else False,
                        'nhcl_id': self.nhcl_id,
                    }
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[department_list])

                        # Raise an exception for HTTP errors
                        stores_data.raise_for_status()

                        # Access the JSON content from the response
                        response_json = stores_data.json()

                        # Access specific values from the response (e.g., "message" or "responseCode")
                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Department {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Department  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                    'add', 'failure', message)
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(
                                    response_json['object_name'], self.id, 200, 'add', 'failure', message)

                        else:
                            line.date_replication = True
                            self.update_replication = True
                            _logger.info(f"Successfully created Department {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(f"Successfully created Department {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                    except requests.exceptions.RequestException as e:
                        _logger.info(f"Failed to create Department '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(f"Failed to create Department '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('hr.department',
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('hr.department',
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Department on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Department on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class HrDepartmentReplication(models.Model):
    _name = 'hr.department.replication'

    hr_department_replication_line_id = fields.Many2one('hr.department', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update status")
    delete_status = fields.Boolean(string="Delete status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')

class HrJob(models.Model):
    _inherit = 'hr.job'

    update_replication = fields.Boolean(string="Creation Status")
    update_status = fields.Boolean(string="Update status")
    delete_status = fields.Boolean(string="Delete status")
    hr_job_replication_id = fields.One2many('hr.job.replication', 'hr_job_replication_line_id')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True, tracking=True)
    warning_message = fields.Char(compute='_compute_warning_message')



    @api.model
    def get_pending_employee(self):
        pending_employee = self.search_count([('update_replication', '=', False)])
        return {
            'pending_employee': pending_employee,
        }


    def get_employee_stores(self):
        return {
            'name': _('Employee'),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'nhcl.bulk.employee',
            'view_mode': 'form',
            'view_id': self.env.ref('nhcl_ho_store_cmr_integration.nhcl_bulk_employee_view').id,
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
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM hr_job")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        vals['nhcl_id'] = max_nhcl_id + 1
        return super(HrJob, self).create(vals)

    def get_stores_data(self):
        for line in self:
            replication_data = []
            existing_store_ids = line.hr_job_replication_id.mapped('store_id.id')
            ho_store_id = self.env['nhcl.ho.store.master'].sudo().search(
                [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True),
                 ])
            for rec in line.hr_job_replication_id:
                if rec.nhcl_terminal_ip not in ho_store_id.mapped('nhcl_terminal_ip'):
                    rec.unlink()
                elif rec.nhcl_api_key not in ho_store_id.mapped('nhcl_api_key'):
                    rec.unlink()
            for i in ho_store_id:
                for j in i.nhcl_store_data_id:
                    if j.model_id.name == 'Job Position' and j.nhcl_line_data == True:
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
            line.update({'hr_job_replication_id': replication_data})

    def send_replication_data(self):
        for line in self.hr_job_replication_id:
            if not line.date_replication:
                ho_ip = line.nhcl_terminal_ip
                ho_port = line.nhcl_port_no
                ho_api_key = line.nhcl_api_key
                store_get_url_data = f"http://{ho_ip}:{ho_port}/api/hr.job/search"
                headers_source = {'api-key': f"{ho_api_key}", 'Content-Type': 'application/json'}
                department_domain = [('nhcl_id', '=', self.nhcl_id)]
                store_url = f"{store_get_url_data}?domain={department_domain}"

                # Check if the department already exists
                try:
                    response = requests.get(store_url, headers=headers_source)
                    response.raise_for_status()
                    data = response.json()
                    department_id_data = data.get("data", [])
                    if department_id_data:
                        _logger.info(
                            f" '{self.name}' Already exists as Department on '{ho_ip}' with partner '{ho_port}'.")
                        logging.info(
                            f" '{self.name}' Already exists as Department on '{ho_ip}' with partner '{ho_port}'.")
                        line.date_replication = True
                        continue
                    store_url_data = f"http://{ho_ip}:{ho_port}/api/hr.job/create"
                    department_list = {
                        'name': self.name,
                        'nhcl_id': self.nhcl_id,
                    }
                    try:
                        stores_data = requests.post(store_url_data, headers=headers_source, json=[department_list])
                        # Raise an exception for HTTP errors
                        stores_data.raise_for_status()

                        # Access the JSON content from the response
                        response_json = stores_data.json()

                        # Access specific values from the response (e.g., "message" or "responseCode")
                        message = response_json.get("message", "No message provided")
                        response_code = response_json.get("responseCode", "No response code provided")
                        if response_json.get("success") == False:
                            _logger.info(
                                f"Failed to create Department {message} '{ho_ip}' with partner '{ho_port}'. Error: ")
                            logging.error(
                                f"Failed to create Department  {message} '{ho_ip}' with partner '{ho_port}'. Error:")
                            if line.master_store_id.nhcl_sink == False:
                                line.master_store_id.create_cmr_replication_log(response_json['object_name'], self.id, 200,
                                                                                    'add', 'failure', message)
                            else:
                                line.master_store_id.create_cmr_old_store_replication_log(
                                    response_json['object_name'], self.id, 200, 'add', 'failure', message)

                        else:
                            line.date_replication = True
                            self.update_replication = True
                            _logger.info(f"Successfully created Department {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                            logging.info(f"Successfully created Department {self.name} {message} '{ho_ip}' with partner '{ho_port}'.")
                    except requests.exceptions.RequestException as e:
                        _logger.info(f"Failed to create Department '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        logging.error(f"Failed to create Department '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                        line.date_replication = False
                        self.update_replication = False
                        if line.master_store_id.nhcl_sink == False:
                            line.master_store_id.create_cmr_replication_log('hr.department',
                                                                            self.id, 500, 'add', 'failure',
                                                                            e)
                        else:
                            line.master_store_id.create_cmr_old_store_replication_log('hr.department',
                                                                                      self.id, 500, 'add', 'failure',
                                                                                      e)
                except requests.exceptions.RequestException as e:
                    _logger.info(
                        f" '{self.name}' Error checking Department on '{ho_ip}' with partner '{ho_port}'. Error: {e}")
                    logging.error(
                        f" '{self.name}' Error checking Department on '{ho_ip}' with partner '{ho_port}'. Error: {e}")


class HrJobReplication(models.Model):
    _name = 'hr.job.replication'

    hr_job_replication_line_id = fields.Many2one('hr.job', string="Replication")
    store_id = fields.Many2one('stock.warehouse', string="Store")
    status = fields.Boolean(string="Active Status")
    date_replication = fields.Boolean(string="Store status")
    nhcl_terminal_ip = fields.Char('Terminal IP')
    nhcl_port_no = fields.Char('Port')
    nhcl_api_key = fields.Char(string='API Secret key')
    update_status = fields.Boolean(string="Update status")
    delete_status = fields.Boolean(string="Delete status")
    master_store_id = fields.Many2one('nhcl.ho.store.master', string='Master Store')


