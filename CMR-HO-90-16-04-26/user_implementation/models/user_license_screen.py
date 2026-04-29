from odoo import models, fields,api
from cryptography.fernet import Fernet
import base64
from odoo.exceptions import UserError, ValidationError
import zlib



class LicenseKey(models.Model):
    _name = 'license.key'
    _description = 'License Key'
    _rec_name = "doc_number"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    doc_number = fields.Char(string='Document Number', default=lambda self: 'New')
    doc_date = fields.Date(string='Document Date', default=fields.Date.today,required=True)
    expiry_date = fields.Date(string="Expiry Date", default=fields.Date.today,required=True)

    user_type = fields.Selection([
        ('temporary', 'Temporary User'),
        ('permanent', 'Permanent User'),
    ], string='User Type', required=True)

    store_id = fields.Many2one('nhcl.ho.store.master', string='Company',required=True, domain = [('nhcl_store_type', '!=', 'ho')] )
    license_count = fields.Integer(string="License Count",compute='_compute_total_license_count',store=True,required=True)
    email = fields.Char(string='Emails')
    state = fields.Selection([
        ('open', 'Open'),
        ('closed', 'Closed'),('cancel', 'Cancel'),
    ], string='Status', default='open', tracking=True)
    cashier_count = fields.Integer(string="Cashier users",required=True)
    backend_count = fields.Integer(string="Backend users",required=True)
    encryption_key = fields.Char("License Keys", readonly=True)
    note = fields.Text(string='License Data', readonly=True)
    license_key = fields.Char("License key",readonly=True)


    @api.depends('cashier_count','backend_count')
    def _compute_total_license_count(self):
        for record in self:
            record.license_count = sum([record.cashier_count or 0,record.backend_count or 0])

    @api.constrains('license_count', 'cashier_count', 'backend_count')
    def _check_license_counts(self):
        for rec in self:
            if rec.license_count <= 0:
                raise ValidationError("Total License Count must be greater than zero.")

    def button_open_license_key_wizard(self):
        for rec in self:
            required_fields = [
                rec.doc_date, rec.expiry_date, rec.user_type,
                rec.store_id, rec.license_count
            ]
            if not all(required_fields):
                raise UserError("Please fill all required fields before generating a license key.")

            return {
                'name': 'Generate License Key',
                'type': 'ir.actions.act_window',
                'res_model': 'generate.license.key.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_confirm_text': 'Do you want to generate a license key?',
                    'active_id': rec.id,
                }
            }

    def action_for_generate_license_key(self):
        # pass;
        for record in self:
            data = f"{record.doc_number}|{record.doc_date}|{record.user_type}|{record.store_id.nhcl_store_name.name}|{record.email}|{record.license_count}|{record.cashier_count}|{record.backend_count}|{record.expiry_date}"
            key = Fernet.generate_key()
            fernet = Fernet(key)
            compressed_data = zlib.compress(data.encode())
            encrypted_data = fernet.encrypt(compressed_data)

            # Convert encrypted parts to base64 to make them string-safe
            encrypted_data_b64 = base64.urlsafe_b64encode(encrypted_data).decode()
            key_b64 = base64.urlsafe_b64encode(key).decode()

            license_key_combined = f"{key_b64}:{encrypted_data_b64}"
            record.license_key = license_key_combined
            record.note = encrypted_data_b64
            record.encryption_key = key_b64
            if record.doc_number == 'New':
                sequence_number = self.env['ir.sequence'].next_by_code('license.key.generation.seq')
                record.doc_number = sequence_number
        self.state = 'closed'

    def action_for_send_license_key_mail(self):
        self.ensure_one()
        if not self.email:
            raise ValidationError("Email is required before sending the license key.")
        if not self.encryption_key:
            raise ValidationError("License key is required before sending the mail")

        template_id = self.env.ref('user_implementation.email_template_license_key', raise_if_not_found=False)

        ctx = {
            'default_model': 'license.key',
            'default_res_ids': [int(self.id)],
            'default_use_template': bool(template_id),
            'default_template_id': template_id.id if template_id else False,
            'default_composition_mode': 'comment',
            'force_email': True,
        }

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'target': 'new',
            'context': ctx,
        }
