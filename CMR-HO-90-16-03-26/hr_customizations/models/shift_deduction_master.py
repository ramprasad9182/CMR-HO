from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ShiftDeductionMaster(models.Model):
    _name = "shift.deduction.master"
    _description = "Shift Deduction Master"


    shift_id = fields.Many2one(
        'resource.calendar',
        string="Shift",
        required=True,
        domain="['|', ('company_id', '=', False), ('company_id', 'in', allowed_company_ids)]"
    )
    category = fields.Selection([
        ('general_employee', 'General Employee'),
        ('female_supervisor', 'Female Supervisor'),
        ('female_senior', 'Female Senior'),
        ('male_supervisor', 'Male Supervisor'),
        ('male_senior', 'Male Senior'),
    ],string="Category", required=True)

    slab_ids = fields.One2many(
        'shift.deduction.slab',
        'master_id',
        string="Time Slabs"
    )
    break_type = fields.Selection([
        ('lunch', 'Lunch Break'),
        ('evening', 'Evening Break'),
    ], string="Break Type", required=True)

    @api.constrains('shift_id', 'break_type')
    def _check_unique_shift_break(self):
        for rec in self:
            if not rec.shift_id or not rec.break_type:
                continue

            # Search for another record with same combination
            dup = self.search([
                ('shift_id', '=', rec.shift_id.id),
                ('break_type', '=', rec.break_type),
                ('id', '!=', rec.id)
            ], limit=1)

            if dup:
                raise ValidationError(
                    f"A record already exists for Shift '{rec.shift_id.name}' "
                    f"with Break Type '{rec.break_type}'. "
                    f"Duplicate combinations are not allowed."
                )


class ShiftDeductionSlab(models.Model):
    _name = "shift.deduction.slab"
    _description = "Shift Deduction Slab"

    master_id = fields.Many2one(
        'shift.deduction.master',
        string="Master"
    )

    from_time = fields.Char("From Time (HH:MM)", required=True)
    to_time = fields.Char("To Time (HH:MM)", required=True)
    amount = fields.Float("Amount", required=True)

    #
    # from_minutes = fields.Integer(
    #     "From Minutes", compute="_compute_minutes", store=True)
    # to_minutes = fields.Integer(
    #     "To Minutes", compute="_compute_minutes", store=True)

    # @api.depends('from_time', 'to_time')
    # def _compute_minutes(self):
    #     for rec in self:
    #         rec.from_minutes = rec._convert_to_minutes(rec.from_time)
    #         rec.to_minutes = rec._convert_to_minutes(rec.to_time)
    #
    # def _convert_to_minutes(self, time_str):
    #     """Convert HH:MM → Minutes"""
    #     if not time_str:
    #         return 0
    #     try:
    #         h, m = time_str.split(':')
    #         return int(h) * 60 + int(m)
    #     except:
    #         return 0