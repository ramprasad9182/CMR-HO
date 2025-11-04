import uuid
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LoyaltyGenerateWizard(models.TransientModel):
    _inherit = 'loyalty.generate.wizard'

    @api.depends('customer_ids', 'customer_tag_ids', 'mode')
    def _compute_coupon_qty(self):
        for wizard in self:
            if wizard.mode == 'anonymous':
                wizard.coupon_qty = wizard.coupon_qty or 0
            else:
                wizard.coupon_qty = wizard.coupon_qty

    def generate_coupons(self):
        if any(not wizard.program_id for wizard in self):
            raise ValidationError(_("Can not generate coupon, no program is set."))
        if any(wizard.coupon_qty <= 0 for wizard in self):
            raise ValidationError(_("Invalid quantity."))

        cr = self.env.cr
        today = fields.Date.today()
        for wizard in self:
            if wizard.mode == 'selected' and not wizard.customer_ids:
                raise ValidationError("Please Select Customer")
            base_vals = {
                'program_id': wizard.program_id.id,
                'points': wizard.points_granted,
                'expiration_date': wizard.valid_until or None,
                'create_uid': self.env.uid,
                'create_date': today,
                'write_uid': self.env.uid,
                'write_date': today,
            }

            if wizard.mode == 'anonymous':
                values = [
                    dict(base_vals, partner_id=None,
                         code=str(uuid.uuid4()).replace('-', '').upper()[:10])
                    for _ in range(wizard.coupon_qty)
                ]
            else:
                partners = wizard._get_partners()
                if not partners:
                    raise ValidationError(_("Please select at least one customer."))
                values = []
                for partner in partners:
                    values.extend([
                        dict(base_vals, partner_id=partner.id,
                             code=str(uuid.uuid4()).replace('-', '').upper()[:10])
                        for _ in range(wizard.coupon_qty)
                    ])

            if values:
                columns = list(values[0].keys())
                query = """
                    INSERT INTO loyalty_card ({cols})
                    VALUES {vals}
                """.format(
                    cols=', '.join(columns),
                    vals=', '.join([
                        '(' + ','.join(['%s'] * len(columns)) + ')'
                        for _ in values
                    ])
                )
                params = []
                for v in values:
                    for c in columns:
                        val = v[c]
                        params.append(val if val is not False else None)
                cr.execute(query, params)

        return True
