from odoo import models, fields

from odoo import models, fields, api

class GenerateLicenseKeyWizard(models.TransientModel):
    _name = 'generate.license.key.wizard'
    _description = 'Generate License Key Wizard'


    def action_confirm(self):
        active_id = self.env.context.get('active_id')
        record = self.env['license.key'].browse(active_id)
        record.action_for_generate_license_key()
        return {'type': 'ir.actions.act_window_close'}

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}


