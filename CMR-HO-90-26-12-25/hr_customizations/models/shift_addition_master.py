from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ShiftAdditionMaster(models.Model):
    _name = "shift.addition.master"
    _description = "Shift Addition Master"

    shift_id = fields.Many2one(
        'resource.calendar',
        string="Shift",
        required=True,
        domain="['|', ('company_id', '=', False), ('company_id', 'in', allowed_company_ids)]"
    )

    addition_type = fields.Selection(
        [('lunch', 'Lunch Addition')],
        default="lunch",
        required=True
    )

    month = fields.Selection([
        ('1', 'January'),
        ('2', 'February'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
    ], string="Applicable Month", required=True)

    year = fields.Integer("Applicable Year", required=True)

    slab_ids = fields.One2many(
        'shift.addition.slab',
        'master_id',
        string="Addition Slabs",
    )

    @api.constrains('shift_id', 'month', 'year')
    def _check_unique_master(self):
        for rec in self:
            dup = self.search([
                ('shift_id', '=', rec.shift_id.id),
                ('month', '=', rec.month),
                ('year', '=', rec.year),
                ('id', '!=', rec.id)
            ], limit=1)

            if dup:
                raise ValidationError(
                    f"Shift '{rec.shift_id.name}' already has addition configured for "
                    f"{dict(self._fields['month'].selection).get(rec.month)} {rec.year}."
                )


class ShiftAdditionSlab(models.Model):
    _name = "shift.addition.slab"
    _description = "Shift Addition Slab"

    master_id = fields.Many2one(
        'shift.addition.master',
        string="Master",
        required=True,
        ondelete="cascade"
    )

    from_time = fields.Char("From Time (HH:MM)", required=True)
    to_time = fields.Char("To Time (HH:MM)", required=True)
    amount = fields.Float("Addition Amount", required=True)
