# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_compare
from odoo.tools.misc import OrderedSet

from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG

from odoo import SUPERUSER_ID

_logger = logging.getLogger("Inventory Counting")


class Inventory(models.Model):
    """
    Inventory
    """

    _name = "stock.inventory"
    _description = "Inventory"
    _order = "date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        "Internal Reference",
        readonly=True,
        required=True,
        # states={"draft": [("readonly", False)]},
        default=lambda self: _("New"),
    )
    duration = fields.Float("Duration (Hours)", compute="compute_duration", store=True)
    total_product = fields.Integer("Total Product", compute="compute_total_product")
    start_date = fields.Datetime("Start Date", default=fields.date.today())
    end_date = fields.Datetime("End Date")
    barcode_scan = fields.Char(string="Scan Barcode")
    date = fields.Datetime(
        "Inventory Date",
        readonly=True,
        required=True,
        default=fields.Datetime.now,
        help="If the inventory adjustment is not validated, date at which the theoretical quantities have been checked.\n"
             "If the inventory adjustment is validated, date at which the inventory adjustment has been validated.",
    )
    line_ids = fields.Many2many(
        "stock.quant",
        string="Inventories",
        copy=False,
        readonly=False,
        # states={"done": [("readonly", True)]},
    )
    move_ids = fields.Many2many(
        "stock.move",
        string="Stock Move",
        copy=False,
        readonly=False,
        # states={"done": [("readonly", True)]},
    )
    state = fields.Selection(
        string="Status",
        selection=[
            ("draft", "Draft"),
            ("cancel", "Cancelled"),
            ("confirm", "In Progress"),
            ("done", "Validated"),
        ],
        copy=False,
        index=True,
        readonly=True,
        tracking=True,
        default="draft",
    )
    company_id = fields.Many2one(
        "res.company",
        "Company",
        readonly=True,
        index=True,
        required=True,
        # states={"draft": [("readonly", False)]},
        default=lambda self: self.env.company,
    )
    location_ids = fields.Many2many(
        "stock.location",
        string="Locations",
        check_company=True,
        # states={"draft": [("readonly", False)]},
        domain="[('company_id', '=', company_id), ('usage', '=', 'internal')]",
    )
    product_ids = fields.Many2many(
        "product.product",
        string="Products",
        check_company=True,
        domain="[('type', '=', 'product'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        readonly=True,
        # states={"draft": [("readonly", False)]},
        help="Specify Products to focus your inventory on particular Products.",
    )
    start_empty = fields.Boolean(
        "Empty Inventory", help="Allows to start with an empty inventory."
    )
    prefill_counted_quantity = fields.Selection(
        string="Counted Quantities",
        default="zero",
        help="Allows to start with a pre-filled counted quantity for each lines or "
             "with all counted quantities set to zero.",
        selection=[
            ("counted", "Default to stock on hand"),
            ("zero", "Default to zero"),
        ],
    )
    exhausted = fields.Boolean(
        "Include Exhausted Products",
        readonly=True,
        # states={"draft": [("readonly", False)]},
        help="Include also products with quantity of 0",
    )
    is_lock = fields.Boolean("Is Lock")
    inventory_line_ids = fields.One2many(
        "stock.inventory.line",
        "inventory_id",
        string="Inventories",
        copy=False,
        readonly=False,
    )
    user_id = fields.Many2one(
        "res.users", default=lambda self: self.env.uid, string="Responsible"
    )
    plan_name = fields.Char('Plan Name', copy=False)

    @api.model
    def create(self, vals):
        vals["name"] = self.env["ir.sequence"].next_by_code("stock.inventory") or "New"
        return super(Inventory, self).create(vals)

    def compute_total_product(self):
        for rec in self:
            rec.total_product = len(
                rec.inventory_line_ids
                and rec.inventory_line_ids.mapped("product_id")
                or []
            )

    @api.onchange('barcode_scan')
    def _onchange_barcode_scan(self):
        if self.barcode_scan:
            barcode = self.barcode_scan
            gs1_pattern = r'01(\d{14})21([A-Za-z0-9]+)'
            ean13_pattern = r'(\d{13})'
            custom_serial_pattern = r'^(R\d+)'
            if re.match(gs1_pattern, barcode):
                product_barcode, scanned_number = re.match(gs1_pattern, barcode).groups()
                inventory_line = self.inventory_line_ids.filtered(lambda x: x.prod_lot_id.name == scanned_number)
                if not inventory_line:
                    if self.product_ids:
                        lot = self.env['stock.lot'].search([('name','=',scanned_number),
                                                        ('product_id','in',self.product_ids.ids)])
                    elif self.stock_inventory_category:
                        lot = self.env['stock.lot'].search([('name', '=', scanned_number),
                                                            ('product_id.categ_id', '=', self.stock_inventory_category.id)])
                        if not lot:
                            self.env['stock.lot'].search([('name', '=', scanned_number),
                                                          ('product_id.categ_id.parent_id', '=',
                                                           self.stock_inventory_category.id)])
                            if not lot:
                                self.env['stock.lot'].search([('name', '=', scanned_number),
                                                              ('product_id.categ_id.parent_id.parent_id', '=',
                                                               self.stock_inventory_category.id)])
                                if not lot:
                                    self.env['stock.lot'].search([('name', '=', scanned_number),
                                                                  ('product_id.categ_id.parent_id.parent_id.parent_id', '=',
                                                                   self.stock_inventory_category.id)])

                    else:
                        raise ValidationError(f"No lots found with %s Name {scanned_number}.")
                    if lot:
                        line_values = {
                            "inventory_id": self.id,
                            "qty_done": 0
                            if self.prefill_counted_quantity == "zero"
                            else 0,
                            "theoretical_qty": 0,
                            "prod_lot_id": lot[0].id,
                            "product_id": lot[0].product_id.id,
                            "product_uom_id": lot[0].product_id.uom_id.id,
                            "location_id": lot[0].location_id.id,
                        }
                        self.env['stock.inventory.line'].create(line_values)
                    else:
                        raise ValidationError(f"No lots found with %s Name {scanned_number}.")
                elif inventory_line and inventory_line.product_id.tracking == 'lot':
                    inventory_line.qty_done += 1
                elif inventory_line and inventory_line.product_id.tracking == 'serial':
                    if inventory_line.qty_done >= 1:
                        raise ValidationError(f'lot/serial number qty Already Updated to {inventory_line.qty_done}.')
                    else:
                        inventory_line.qty_done += 1
            elif re.match(ean13_pattern, barcode):
                ean13_barcode = re.match(ean13_pattern, barcode).group(1)
                inventory_line = self.inventory_line_ids.filtered(lambda x: x.prod_lot_id.ref == ean13_barcode)
                if not inventory_line:
                    if self.product_ids:
                        lot = self.env['stock.lot'].search([('ref','=',ean13_barcode),
                                                        ('product_id','in',self.product_ids.ids)])
                    elif self.stock_inventory_category:
                        lot = self.env['stock.lot'].search([('ref', '=', ean13_barcode),
                                                            ('product_id.categ_id', '=', self.stock_inventory_category.id)])
                        if not lot:
                            self.env['stock.lot'].search([('ref', '=', ean13_barcode),
                                                          ('product_id.categ_id.parent_id', '=',
                                                           self.stock_inventory_category.id)])
                            if not lot:
                                self.env['stock.lot'].search([('ref', '=', ean13_barcode),
                                                              ('product_id.categ_id.parent_id.parent_id', '=',
                                                               self.stock_inventory_category.id)])
                                if not lot:
                                    self.env['stock.lot'].search([('ref', '=', ean13_barcode),
                                                                  ('product_id.categ_id.parent_id.parent_id.parent_id', '=',
                                                                   self.stock_inventory_category.id)])
                    else:
                        raise ValidationError(f"No lots found with EAN-13 barcode {ean13_barcode}.")
                    if lot:
                        line_values = {
                            "inventory_id": self.id,
                            "qty_done": 0
                            if self.prefill_counted_quantity == "zero"
                            else 0,
                            "theoretical_qty": 0,
                            "prod_lot_id": lot[0].id,
                            "product_id": lot[0].product_id.id,
                            "product_uom_id": lot[0].product_id.uom_id.id,
                            "location_id": lot[0].location_id.id,
                        }
                        self.env['stock.inventory.line'].create(line_values)
                    else:
                        raise ValidationError(f"No lots found with EAN-13 barcode {ean13_barcode}.")
                for line in inventory_line:
                    if line and line.product_id.tracking == 'lot':
                        if line.theoretical_qty != line.qty_done:
                            line.qty_done += 1
                            break
                    elif line and line.product_id.tracking == 'serial':
                        if line.qty_done != 1:
                            inventory_line.qty_done += 1
                            break
            elif re.match(custom_serial_pattern, barcode):
                prefix = re.match(custom_serial_pattern, barcode).group(1)
                # 1. Try exact match with `ref` like EAN-13
                inventory_line = self.inventory_line_ids.filtered(lambda x: x.prod_lot_id.name == prefix)
                # 2. If not found, fallback to `name` like GS1 serial fallback
                if not inventory_line:
                    inventory_line = self.inventory_line_ids.filtered(lambda x: x.prod_lot_id.ref == barcode
                                                                      )
                if not inventory_line:
                    if self.product_ids:
                        lot = self.env['stock.lot'].search([('name', '=', prefix),
                                                            ('product_id', 'in', self.product_ids.ids)])
                        if not lot:
                            lot = self.env['stock.lot'].search([('ref', '=', barcode),
                                                            ('product_id', 'in', self.product_ids.ids)])
                    elif self.stock_inventory_category:
                        lot = self.env['stock.lot'].search([('name', '=', prefix),
                                                            ('product_id.categ_id', '=',
                                                             self.stock_inventory_category.id)])
                        if not lot:
                            self.env['stock.lot'].search([('name', '=', prefix),
                                                          ('product_id.categ_id.parent_id', '=',
                                                           self.stock_inventory_category.id)])
                            if not lot:
                                self.env['stock.lot'].search([('name', '=', prefix),
                                                              ('product_id.categ_id.parent_id.parent_id', '=',
                                                               self.stock_inventory_category.id)])
                                if not lot:
                                    self.env['stock.lot'].search([('name', '=', prefix),
                                                                  ('product_id.categ_id.parent_id.parent_id.parent_id', '=',
                                                                   self.stock_inventory_category.id)])
                        if not lot:
                            lot = self.env['stock.lot'].search([('ref', '=', barcode),
                                                            ('product_id.categ_id', '=',
                                                             self.stock_inventory_category.id)])

                    else:
                        raise ValidationError(f"No lots found for custom barcode {prefix}")
                    if lot:
                        line_values = {
                            "inventory_id": self.id,
                            "qty_done": 0
                            if self.prefill_counted_quantity == "zero"
                            else 0,
                            "theoretical_qty": 0,
                            "prod_lot_id": lot[0].id,
                            "product_id": lot[0].product_id.id,
                            "product_uom_id": lot[0].product_id.uom_id.id,
                            "location_id": lot[0].location_id.id,
                        }
                        self.env['stock.inventory.line'].create(line_values)
                    else:
                        raise ValidationError(f"No lots found for custom barcode {prefix}")

                for line in inventory_line:
                    if line and line.product_id.tracking == 'lot':
                        if line.theoretical_qty != line.qty_done:
                            line.qty_done += 1
                            break
                    elif line and line.product_id.tracking == 'serial':
                        if line.qty_done != 1:
                            line.qty_done += 1
                            break
            else:
                raise ValidationError('Invalid barcode format.')
            self.barcode_scan = False

    @api.depends("start_date", "end_date")
    def compute_duration(self):
        for record in self:
            if record.start_date and record.end_date:
                record.duration = (
                                          fields.Datetime.from_string(record.end_date)
                                          - fields.Datetime.from_string(record.start_date)
                                  ).total_seconds() / 3600
            else:
                record.duration = 0

    def action_view_stock_inventory_line(self):
        view = self.env.ref("stock_inventory_count_tus.stock_inventory_line_tree")
        return {
            "type": "ir.actions.act_window",
            "name": _("Inventory Line"),
            "res_model": "stock.inventory.line",
            "views": [(view.id, "tree")],
            "domain": [("id", "in", self.inventory_line_ids.ids)],
            "context": {"active_ids": [self.id],
                        "search_default_difference_qty": 1,
                        },
            "view_mode": "tree",
            "view_id": view.id,
            "target": "self",

        }

    def button_recount_inventory_lines(self):
        self.line_ids = False
        self.inventory_line_ids.unlink()
        self.write({"state": "draft"})

    def lock_inventory_count(self):
        self.is_lock = True

    def unlock_inventory_count(self):
        self.is_lock = False

    def _product_of_stock_inventory_category(self):
        domain = [
            ("type", "=", "product"),
            "|",
            ("company_id", "=", False),
            ("company_id", "=", self.env.company.id),
        ]
        for rec in self:
            if rec.env.context.get("is_inventory_count"):
                product = self.env["product.product"].search(
                    [("categ_id", "=", rec.stock_inventory_category.id)]
                )
                if not product:
                    product = self.env['product.product'].search([
                                                  ('categ_id.parent_id', '=',
                                                   self.stock_inventory_category.id)])
                    if not product:
                        product = self.env['product.product'].search([
                                                      ('categ_id.parent_id.parent_id', '=',
                                                       self.stock_inventory_category.id)])
                        if not product:
                            product = self.env['product.product'].search([
                                                          ('categ_id.parent_id.parent_id.parent_id', '=',
                                                           self.stock_inventory_category.id)])
                if product:
                    domain.append(("id", "in", product.ids))
        return domain

    def action_view_count_stock_move_lines(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock.stock_move_line_action"
        )
        # Define domains and context
        move_domain = [
            ("location_dest_id.usage", "in", ["internal", "transit", "customer"]),
            ("company_id", "=", self.company_id.id),
        ]
        domain_loc = []
        if self.location_ids:
            domain_loc = [
                ("id", "in", self.location_ids.ids),
                ("company_id", "=", self.company_id.id),
            ]
        else:
            domain_loc = [
                ("company_id", "=", self.company_id.id),
                ("usage", "in", ["internal", "transit", "customer"]),
            ]
        if self.warehouse_id:
            domain_loc.append(("warehouse_id", "=", self.warehouse_id.id))
        locations_ids = [
            l["id"] for l in self.env["stock.location"].search_read(domain_loc, ["id"])
        ]
        if locations_ids:
            move_domain = expression.AND(
                [
                    move_domain,
                    [
                        "|",
                        ("location_id", "in", locations_ids),
                        ("location_dest_id", "in", locations_ids),
                    ],
                ]
            )
        product_ids = self._get_product_domain(is_start_inventory=True)
        if self.product_ids:
            move_domain = expression.AND(
                [move_domain, [("product_id", "in", self.product_ids.ids)]]
            )
        elif self.stock_inventory_category:
            move_domain = expression.AND(
                [move_domain, [("product_id.categ_id", "=", self.stock_inventory_category.id)]]
            )


        else:
            move_domain = expression.AND([move_domain, product_ids])
        if self.from_date_range:
            move_domain = expression.AND(
                [move_domain, [("date", ">=", self.from_date_range)]]
            )
        if self.to_date_range:
            move_domain = expression.AND(
                [move_domain, [("date", "<=", self.to_date_range)]]
            )
        action["domain"] = move_domain
        return action

    is_inventory_count = fields.Boolean(
        string="Is Inventory Count", copy=False, default=True
    )
    stock_inventory_category = fields.Many2one(
        "product.category",
        string="Category",
        tracking=True,
        domain="[('child_id', '!=', False)]"

    )
    from_date_range = fields.Datetime("From Date", tracking=True)
    to_date_range = fields.Datetime(
        "To Date", tracking=True, default=lambda self: fields.Datetime.now()
    )
    warehouse_id = fields.Many2one("stock.warehouse", string="Warehouse", tracking=True)

    @api.onchange("warehouse_id", "stock_inventory_category")
    def _onchange_domain_product_id(self):
        """
        Domain prepare for Product
        """
        domain = []
        if self.env.context.get("is_inventory_count"):
            domain = self._get_product_domain(is_start_inventory=False)
        domain = expression.AND(
            [
                domain,
                [
                    ("type", "=", "product"),
                    "|",
                    ("company_id", "=", False),
                    ("company_id", "=", self.env.company.id),
                ],
            ]
        )
        return {"domain": {"product_ids": domain}}

    def _get_product_domain(self, is_start_inventory=False):
        product_domain = [
            ("active", "in", [False, True]),
            "|",
            ("company_id", "!=", False),
            ("company_id", "=", self.company_id.id),
        ]
        domain = []
        if self.warehouse_id:
            product_ids = self.env["product.product"].search(product_domain)
            if product_ids and is_start_inventory:
                domain.append(("product_id", "in", product_ids.ids))
            elif product_ids:
                domain.append(("id", "in", product_ids.ids))
        if self.stock_inventory_category:
            product = self.env["product.product"].search(
                [("categ_id", "=", self.stock_inventory_category.id)]
            )
            if not product:
                product = self.env["product.product"].search(
                    [("categ_id.parent_id", "=", self.stock_inventory_category.id)]
                )
                if not product:
                    product = self.env["product.product"].search(
                        [("categ_id.parent_id.parent_id", "=", self.stock_inventory_category.id)]
                    )
                    if not product:
                        product = self.env["product.product"].search(
                            [("categ_id.parent_id.parent_id.parent_id", "=", self.stock_inventory_category.id)]
                        )
            if product and is_start_inventory:
                domain.append(("product_id", "in", product.ids))
            elif product:
                domain.append(("id", "in", product.ids))
        return domain

    @api.model
    def default_get(self, fields):
        is_inventory_count = self.env.context.get("is_inventory_count")
        vals = super(Inventory, self).default_get(fields)
        vals["is_inventory_count"] = is_inventory_count
        return vals

    def _get_quantities(self):
        """Return quantities group by product_id, location_id, lot_id, package_id and owner_id

        :return: a dict with keys as tuple of group by and quantity as value
        :rtype: dict
        """
        self.ensure_one()

        # Define domains and context
        domain = [
            ("location_id.usage", "in", ["internal", "transit", "customer"]),
            ("company_id", "=", self.company_id.id),
        ]
        move_domain = [
            ("location_dest_id.usage", "in", ["internal", "transit", "customer"]),
            ("company_id", "=", self.company_id.id),
        ]
        if self.location_ids:
            domain_loc = [
                ("id", "in", self.location_ids.ids),
                ("company_id", "=", self.company_id.id),
            ]
        else:
            domain_loc = [
                ("company_id", "=", self.company_id.id),
                ("usage", "in", ["internal", "transit", "customer"]),
            ]
        if self.warehouse_id:
            domain_loc.append(("warehouse_id", "=", self.warehouse_id.id))
        locations_ids = [
            l["id"] for l in self.env["stock.location"].search_read(domain_loc, ["id"])
        ]
        if locations_ids:
            domain.append(("location_id", "in", locations_ids))
            move_domain = expression.AND(
                [
                    move_domain,
                    [
                        "|",
                        ("location_id", "in", locations_ids),
                        ("location_dest_id", "in", locations_ids),
                    ],
                ]
            )
        product_ids = self._get_product_domain(is_start_inventory=True)
        if self.product_ids:
            domain = expression.AND(
                [domain, [("product_id", "in", self.product_ids.ids)]]
            )
            move_domain = expression.AND(
                [move_domain, [("product_id", "in", self.product_ids.ids)]]
            )
        else:
            domain = expression.AND([domain, product_ids])
            move_domain = expression.AND([move_domain, product_ids])
        if self.from_date_range:
            domain = expression.AND([domain, [("in_date", ">=", self.from_date_range)]])
            move_domain = expression.AND(
                [move_domain, [("date", ">=", self.from_date_range)]]
            )
        if self.to_date_range:
            domain = expression.AND([domain, [("in_date", "<=", self.to_date_range)]])
            move_domain = expression.AND(
                [move_domain, [("date", "<=", self.to_date_range)]]
            )
        fields = [
            "product_id",
            "location_id",
            "lot_id",
            "package_id",
            "owner_id",
            "use_expiration_date",
            "quantity:sum",
        ]
        group_by = ["product_id", "location_id", "lot_id", "package_id", "owner_id"]
        move_ids = self.env["stock.move.line"].search(move_domain)
        if move_ids:
            locations_ids = move_ids.location_dest_id + move_ids.location_id
            locations_ids = locations_ids.filtered(
                lambda l: l.usage == "internal"
                          and l.name not in ["Staging", "Shipping Staging", "Input", "Output"]
            )
            domain = [
                ("product_id", "in", move_ids.product_id.ids),
                ("location_id", "in", locations_ids.ids),
            ]
        quants = self.env["stock.quant"].read_group(
            domain, fields, group_by, lazy=False
        )
        return [
            {
                (
                    quant["product_id"] and quant["product_id"][0] or False,
                    quant["location_id"] and quant["location_id"][0] or False,
                    quant["lot_id"] and quant["lot_id"][0] or False,
                    quant["package_id"] and quant["package_id"][0] or False,
                    quant["owner_id"] and quant["owner_id"][0] or False,
                ): quant["quantity"]
                for quant in quants
            },
            move_ids,
        ]

    @api.onchange("company_id")
    def _onchange_company_id(self):
        # If the multiplication group is not active, default the location to the one of the main
        # warehouse.
        if not self.user_has_groups("stock.group_stock_multi_locations"):
            warehouse = self.env["stock.warehouse"].search(
                [("company_id", "=", self.company_id.id)], limit=1
            )
            if warehouse:
                self.location_ids = warehouse.lot_stock_id

    def copy_data(self, default=None):
        name = _("%s (copy)") % (self.name)
        default = dict(default or {}, name=name)
        return super(Inventory, self).copy_data(default)

    def unlink(self):
        for inventory in self:
            if inventory.state not in ("draft", "cancel") and not self.env.context.get(
                    MODULE_UNINSTALL_FLAG, False
            ):
                raise UserError(
                    _(
                        "You can only delete a draft inventory adjustment. If the inventory adjustment is not done, you can cancel it."
                    )
                )
        return super(Inventory, self).unlink()

    def action_validate(self):
        self.state = "done"
        self.end_date = fields.Datetime.now()
        self.user_id = self.env.uid
        for line in self.inventory_line_ids:
            line.prod_lot_id.is_under_plan = False
        return True

    def action_check(self):
        """Checks the inventory and computes the stock move to do"""
        # tde todo: clean after _generate_moves
        for inventory in self.filtered(lambda x: x.state not in ("done", "cancel")):
            # first remove the existing stock moves linked to this inventory
            inventory.with_context(prefetch_fields=False).mapped("move_ids").unlink()
            inventory.line_ids._generate_moves()

    def action_cancel_draft(self):
        """Cancel the inventory"""
        self.line_ids = False
        self.inventory_line_ids.unlink()
        self.write({"state": "draft"})

    def action_start(self):
        self.ensure_one()
        self._action_start()
        self._check_company()
        res = self.with_context(start_inventory=True).action_open_inventory_lines()
        return True

    def _action_start(self):
        """Confirms the Inventory Adjustment and generates its inventory lines
        if its state is draft and don't have already inventory lines (can happen
        with demo data or tests).
        """
        for inventory in self:
            if inventory.state != "draft":
                continue
            vals = {
                "state": "confirm",
                "date": fields.Datetime.now(),
                "start_date": fields.Datetime.now(),
                "user_id": self.env.user.id,
            }
            inventory.write(vals)

    def action_open_inventory_lines(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "view_mode": "tree",
            "name": _("Inventory Lines"),
            "res_model": "stock.inventory.line",
        }
        context = {
            "is_inventory_count": True,
            "default_is_editable": True,
            "default_company_id": self.company_id.id,
        }

        action["view_id"] = self.env.ref(
            "stock_inventory_count_tus.stock_inventory_line_tree"
        ).id
        if not self.inventory_line_ids:
            lines = self.env["stock.inventory.line"].create(self._get_inventory_lines_values())
            for line in lines:
                line.prod_lot_id.is_under_plan = True
        action["context"] = context
        action["domain"] = [("inventory_id", "=", self.id)]
        return action

    def action_print(self):
        return self.env.ref("stock.action_report_inventory").report_action(self)

    def _get_exhausted_inventory_lines_vals(self, non_exhausted_set):
        """Return the values of the inventory lines to create if the user
        wants to include exhausted products. Exhausted products are products
        without quantities or quantity equal to 0.

        :param non_exhausted_set: set of tuple (product_id, location_id) of non-exhausted product-location
        :return: a list containing the `stock.quant` values to create
        :rtype: list
        """
        self.ensure_one()
        if self.product_ids:
            product_ids = self.product_ids.ids
        elif self.stock_inventory_category:
            product_ids = self.env["product.product"].search(
                [("categ_id", "=", self.stock_inventory_category.id)])
        else:
            product_ids = self.env["product.product"].search_read(
                [
                    "|",
                    ("company_id", "=", self.company_id.id),
                    ("company_id", "=", False),
                    ("type", "=", "product"),
                    ("active", "=", True),
                ],
                ["id"],
            )
            product_ids = [p["id"] for p in product_ids]

        if self.location_ids:
            location_ids = self.location_ids.ids
        else:
            location_ids = (
                self.env["stock.warehouse"]
                .search([("company_id", "=", self.company_id.id)])
                .lot_stock_id.ids
            )

        vals = []
        for product_id in product_ids:
            p_id = self.env["product.product"].browse(product_id)
            for location_id in location_ids:
                if (product_id, location_id) not in non_exhausted_set:
                    vals.append(
                        {
                            "inventory_id": self.id,
                            "product_id": product_id,
                            "product_uom_id": p_id
                                              and p_id.uom_id
                                              and p_id.uom_id.id
                                              or False,
                            "location_id": location_id,
                            "theoretical_qty": 0,
                        }
                    )
        return vals

    def _get_inventory_lines_values(self):
        """Return the values of the inventory lines to create for this inventory.

        :return: a list containing the `stock.quant` values to create
        :rtype: list
        """
        self.ensure_one()
        get_quantities = self._get_quantities()
        quants_groups = get_quantities[0]
        move_ids = get_quantities[1]
        vals = []
        product_ids = OrderedSet()
        for (
                product_id,
                location_id,
                lot_id,
                package_id,
                owner_id,
        ), quantity in quants_groups.items():
            temp_lines = move_ids.filtered(lambda m: m.product_id.id == product_id)
            temp_location_ids = temp_lines.mapped("location_id") + temp_lines.mapped(
                "location_dest_id"
            )
            if location_id in temp_location_ids.ids:
                if location_id in self.location_ids.ids:
                    line_values = {
                        "inventory_id": self.id,
                        "qty_done": 0
                        if self.prefill_counted_quantity == "zero"
                        else quantity,
                        "theoretical_qty": quantity,
                        "prod_lot_id": lot_id,
                        "partner_id": owner_id,
                        "product_id": product_id,
                        "location_id": location_id,
                        "package_id": package_id,
                    }
                    product_ids.add(product_id)
                    vals.append(line_values)
        product_id_to_product = dict(
            zip(product_ids, self.env["product.product"].browse(product_ids))
        )
        for val in vals:
            val["product_uom_id"] = product_id_to_product[
                val["product_id"]
            ].product_tmpl_id.uom_id.id
        if self.exhausted:
            vals += self._get_exhausted_inventory_lines_vals(
                {(l["product_id"], l["location_id"]) for l in vals}
            )
        return vals

    def _get_stock_inventory_lines_values(self, move_ids):
        """Return the values of the inventory lines to create for this inventory.

        :return: a list containing the `stock.inventory.line` values to create
        :rtype: list
        """
        self.ensure_one()
        vals = []
        product_ids = OrderedSet()
        prefill_counted_quantity = self.prefill_counted_quantity != "zero"
        for move in move_ids:
            existing_updated = False
            for val in vals:
                if move.product_id.id == val.get(
                        "product_id"
                ) and move.location_dest_id.id == val.get("location_dest_id"):
                    val["qty_done"] += prefill_counted_quantity and move.qty_done or 0
                    val["theoretical_qty"] += move.qty_done or 0
                    existing_updated = True
                    break
            if existing_updated:
                continue
            line_values = {
                "inventory_id": self.id,
                "qty_done": prefill_counted_quantity and move.qty_done or 0,
                "theoretical_qty": move.qty_done,
                "prod_lot_id": move.lot_id.id,
                "product_id": move.product_id.id,
                "location_id": move.location_id.id,
                "location_dest_id": move.location_dest_id.id,
                "package_id": move.package_id.id,
            }
            product_ids.add(move.product_id.id)
            vals.append(line_values)
        product_id_to_product = dict(
            zip(product_ids, self.env["product.product"].browse(product_ids))
        )
        for val in vals:
            val["product_uom_id"] = product_id_to_product[
                val["product_id"]
            ].product_tmpl_id.uom_id.id
        if self.exhausted:
            vals += self._get_exhausted_inventory_lines_vals(
                {(l["product_id"], l["location_dest_id"]) for l in vals}
            )
        return vals


class InventoryLine(models.Model):
    """A line of inventory"""

    _name = "stock.inventory.line"
    _description = "Inventory Line"
    _order = "product_id, inventory_id, prod_lot_id"

    @api.model
    def _domain_location_id(self):
        if self.env.context.get("active_model") == "stock.inventory":
            inventory = self.env["stock.inventory"].browse(
                self.env.context.get("active_id")
            )
            if inventory.exists() and inventory.location_ids:
                return (
                        "[('company_id', '=', company_id), ('usage', 'in', ['internal', 'transit']), ('id', 'child_of', %s)]"
                        % inventory.location_ids.ids
                )
        return "[('company_id', '=', company_id), ('usage', 'in', ['internal', 'transit'])]"

    @api.model
    def _domain_product_id(self):
        if self.env.context.get("active_model") == "stock.inventory":
            inventory = self.env["stock.inventory"].browse(
                self.env.context.get("active_id")
            )
            if inventory.exists() and len(inventory.product_ids) > 1:
                return (
                        "[('type', '=', 'product'), '|', ('company_id', '=', False), ('company_id', '=', company_id), ('id', 'in', %s)]"
                        % inventory.product_ids.ids
                )
        return "[('type', '=', 'product'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]"

    def _search_difference_qty(self, operator, value):
        if not self._context.get("active_ids"):
            raise NotImplementedError(
                _(
                    "Unsupported search on %s outside of an Inventory Adjustment",
                    "difference_qty",
                )
            )
        value = abs(float(value or 0))
        lines = self.search([("inventory_id", "in", self._context.get("active_ids"))])
        if operator == "=":
            line_ids = lines.filtered(lambda l: abs(l.difference_qty) == value)
        elif operator == "!=":
            line_ids = lines.filtered(lambda l: abs(l.difference_qty) != value)
        elif operator == ">":
            line_ids = lines.filtered(lambda l: abs(l.difference_qty) > value)
        elif operator == "<":
            line_ids = lines.filtered(lambda l: abs(l.difference_qty) < value)
        elif operator == ">=":
            line_ids = lines.filtered(lambda l: abs(l.difference_qty) >= value)
        elif operator == "<=":
            line_ids = lines.filtered(lambda l: abs(l.difference_qty) <= value)
        else:
            line_ids = lines.filtered(lambda l: abs(l.difference_qty) == value)
        return [("id", "in", line_ids.ids)]

    is_editable = fields.Boolean(help="Technical field to restrict editing.")
    inventory_id = fields.Many2one(
        "stock.inventory",
        "Inventory",
        check_company=True,
        index=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one("res.partner", "Owner", check_company=True)
    product_id = fields.Many2one(
        "product.product",
        "Product",
        check_company=True,
        domain=lambda self: self._domain_product_id(),
        index=True,
        required=True,
    )
    product_uom_id = fields.Many2one(
        "uom.uom", "Product Unit of Measure", required=True, readonly=True
    )
    qty_done = fields.Float(
        "Counted Quantity",
        # states={"done": [("readonly", False)]},
        digits="Product Unit of Measure",
        default=0,
    )
    categ_id = fields.Many2one(related="product_id.categ_id", store=True)
    location_id = fields.Many2one(
        "stock.location", "Location", check_company=True, index=True, required=True
    )
    location_dest_id = fields.Many2one(
        "stock.location",
        "Destination Location",
        check_company=True,
        domain=lambda self: self._domain_location_id(),
        index=True,
        required=False,
    )
    package_id = fields.Many2one(
        "stock.quant.package", "Pack", index=True, check_company=True
    )
    prod_lot_id = fields.Many2one(
        "stock.lot",
        "Lot/Serial Number",
        check_company=True,
        domain="[('product_id','=',product_id), ('company_id', '=', company_id)]",
    )
    company_id = fields.Many2one(
        "res.company",
        "Company",
        related="inventory_id.company_id",
        index=True,
        readonly=True,
        store=True,
    )
    state = fields.Selection(string="Status", related="inventory_id.state")
    theoretical_qty = fields.Float(
        "Theoretical Quantity", digits="Product Unit of Measure", readonly=True
    )
    difference_qty = fields.Float(
        "Difference",
        compute="_compute_difference",
        help="Indicates the gap between the product's theoretical quantity and its newest quantity.",
        readonly=True,
        digits="Product Unit of Measure",
        search="_search_difference_qty",
    )
    inventory_date = fields.Datetime(
        "Inventory Date",
        readonly=True,
        default=fields.Datetime.now,
        help="Last date at which the On Hand Quantity has been computed.",
    )
    outdated = fields.Boolean(
        string="Quantity outdated",
        compute="_compute_outdated",
        search="_search_outdated",
    )
    product_tracking = fields.Selection(
        string="Tracking", related="product_id.tracking", readonly=True
    )
    expiration_date = fields.Datetime(
        string="Expiration Date",
        related="prod_lot_id.expiration_date",
        store=True,
        help="This is the date on which the goods with this Serial Number may become dangerous and must not be consumed.",
    )
    is_adjusted = fields.Boolean('Adjusted', default=False)
    inventory_quantity_set = fields.Boolean(store=True, compute='_compute_qty_done_set', readonly=False, default=False)

    @api.depends('qty_done')
    def _compute_qty_done_set(self):
        for line in self:
            line.inventory_quantity_set = True

    @api.depends("qty_done", "theoretical_qty")
    def _compute_difference(self):
        for line in self:
            line.difference_qty = line.qty_done - line.theoretical_qty

    @api.depends(
        "inventory_date",
        "product_id.stock_move_ids",
        "theoretical_qty",
        "product_uom_id.rounding",
    )
    def _compute_outdated(self):
        quants_by_inventory = {
            inventory: inventory._get_quantities()[0] for inventory in self.inventory_id
        }
        for line in self:
            if line.inventory_id:
                quants = quants_by_inventory[line.inventory_id]
                if line.state == "done" or not line.id:
                    line.outdated = False
                    continue
                qty = quants.get(
                    (
                    line.product_id.id,
                    line.location_dest_id.id,
                    line.prod_lot_id.id,
                    line.package_id.id,
                    line.partner_id.id,
                ),
                0,
                )
                if (
                    float_compare(
                        qty,
                        line.theoretical_qty,
                        precision_rounding=line.product_uom_id.rounding,
                    )
                    != 0
            ):
                    line.outdated = True
                else:
                    line.outdated = False
            else:
                line.outdated = False

    def _search_outdated(self, operator, value):
        if operator != "=":
            if operator == "!=" and isinstance(value, bool):
                value = not value
            else:
                raise NotImplementedError()
        if not self.env.context.get("default_inventory_id"):
            raise NotImplementedError(
                _(
                    "Unsupported search on %s outside of an Inventory Adjustment",
                    "outdated",
                )
            )
        lines = self.search(
            [("inventory_id", "=", self.env.context.get("default_inventory_id"))]
        )
        line_ids = lines.filtered(lambda line: line.outdated == value).ids
        return [("id", "in", line_ids)]

    def _get_inventory_move_values(self, qty, location_id, location_dest_id, package_id=False, package_dest_id=False):
        """ Called when user manually set a new quantity (via `inventory_quantity`)
        just before creating the corresponding stock move.

        :param location_id: `stock.location`
        :param location_dest_id: `stock.location`
        :param package_id: `stock.quant.package`
        :param package_dest_id: `stock.quant.package`
        :return: dict with all values needed to create a new `stock.move` with its move line.
        """
        self.ensure_one()
        if self.env.context.get('inventory_name'):
            name = self.env.context.get('inventory_name')
        elif fields.Float.is_zero(qty, 0, precision_rounding=self.product_uom_id.rounding):
            name = _('Product Quantity Confirmed')
        else:
            name = _('Product Quantity Updated')
        if self.env.user and self.env.user.id != SUPERUSER_ID:
            name += f' ({self.env.user.display_name})'

        return {
            'name': name,
            'product_id': self.product_id.id,
            'product_uom': self.product_uom_id.id,
            'product_uom_qty': qty,
            'company_id': self.company_id.id or self.env.company.id,
            'state': 'confirmed',
            'location_id': location_id.id,
            'location_dest_id': location_dest_id.id,
            'restrict_partner_id': self.partner_id.id,
            'is_inventory': True,
            'picked': True,
            'move_line_ids': [(0, 0, {
                'product_id': self.product_id.id,
                'product_uom_id': self.product_uom_id.id,
                'quantity': qty,
                'location_id': location_id.id,
                'location_dest_id': location_dest_id.id,
                'company_id': self.company_id.id or self.env.company.id,
                'lot_id': self.prod_lot_id.id,
                'package_id': package_id.id if package_id else False,
                'result_package_id': package_dest_id.id if package_dest_id else False,
                'owner_id': self.partner_id.id,
            })]
        }

    def _apply_inventory(self):
        move_vals = []
        if not self.user_has_groups('stock.group_stock_manager'):
            raise UserError(_('Only a stock manager can validate an inventory adjustment.'))
        for line in self:
            # Create and validate a move so that the quant matches its `inventory_quantity`.
            if float_compare(line.difference_qty, 0, precision_rounding=line.product_uom_id.rounding) > 0:
                move_vals.append(
                    line._get_inventory_move_values(line.difference_qty,
                                                    line.product_id.with_company(
                                                        line.company_id).property_stock_inventory,
                                                    line.location_id, package_dest_id=line.package_id))
            else:
                move_vals.append(
                    line._get_inventory_move_values(-line.difference_qty,
                                                    line.location_id,
                                                    line.product_id.with_company(
                                                        line.company_id).property_stock_inventory,
                                                    package_id=line.package_id))
        moves = self.env['stock.move'].with_context(inventory_mode=False).create(move_vals)
        moves._action_done()
        self.location_id.write({'last_inventory_date': fields.Date.today()})
        date_by_location = {loc: loc._get_next_inventory_date() for loc in self.mapped('location_id')}
        for quant in self:
            quant.inventory_date = date_by_location[quant.location_id]
            quant.theoretical_qty = quant.qty_done

    def action_apply_inventory(self):
        products_tracked_without_lot = []
        all_quant_ids = self.env['stock.quant']
        for line in self:
            rounding = line.product_uom_id.rounding
            rec_quant = self.env['stock.quant'].with_company(line.company_id).search(
                [('product_id', '=', line.product_id.id), ('location_id', '=', line.location_id.id),
                 ('lot_id', '=', line.prod_lot_id.id)])
            all_quant_ids += rec_quant
            if fields.Float.is_zero(line.difference_qty, precision_rounding=rounding) \
                    and fields.Float.is_zero(line.qty_done, precision_rounding=rounding) \
                    and fields.Float.is_zero(line.theoretical_qty, precision_rounding=rounding):
                continue
            if line.product_id.tracking in ['lot', 'serial'] and \
                    not line.prod_lot_id and line.qty_done != line.theoretical_qty and not line.theoretical_qty:
                products_tracked_without_lot.append(line.product_id.id)
        # for some reason if multi-record, env.context doesn't pass to wizards...
        ctx = dict(self.env.context or {})
        quants_outdated = all_quant_ids.filtered(lambda quant: quant.is_outdated)
        if quants_outdated:
            ctx['default_quant_ids'] = all_quant_ids.ids
            ctx['default_quant_to_fix_ids'] = quants_outdated and quants_outdated.ids or []
            return {
                'name': _('Conflict in Inventory Adjustment'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'views': [(False, 'form')],
                'res_model': 'stock.inventory.conflict',
                'target': 'new',
                'context': ctx,
            }
        if products_tracked_without_lot:
            ctx['default_product_ids'] = products_tracked_without_lot
            return {
                'name': _('Tracked Products in Inventory Adjustment'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'views': [(False, 'form')],
                'res_model': 'stock.track.confirmation',
                'target': 'new',
                'context': ctx,
            }
        self._apply_inventory()

    def action_set_counted_qty_to_onhand(self):
        self.qty_done = self.theoretical_qty


class StockLot(models.Model):
    """Inherited stock.lot class to add fields and functions"""
    _inherit = 'stock.lot'

    is_under_plan = fields.Boolean('Is Under Plan', copy=False)
