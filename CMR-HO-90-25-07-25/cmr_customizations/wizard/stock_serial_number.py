
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StockAssignSerialNumbers(models.TransientModel):
    _inherit = 'stock.assign.serial'

    nhcl_last_serial_number = fields.Char('Last Serial Number', readonly=True)

    @api.model
    def create(self, vals):
        """ Override to set the initial nhcl_last_serial_number when the wizard is opened """
        res = super(StockAssignSerialNumbers, self).create(vals)

        # Fetch the current nhcl_last_serial_number from the sequence master
        master_seq = self.env['nhcl.master.sequence'].search([
            ('nhcl_code', '=', 'Auto Serial Number'),
            ('nhcl_active', '=', True)
        ], limit=1)

        if master_seq:
            res.nhcl_last_serial_number = f"R{master_seq.nhcl_next_number - 1}"
        return res

    def generate_serial_numbers_production(self):
        """ Generate serial numbers without updating nhcl_last_serial_number immediately """
        # Fetch the nhcl_next_number from the sequence master
        master_seq = self.env['nhcl.master.sequence'].search([
            ('nhcl_code', '=', 'Auto Serial Number'),
            ('nhcl_active', '=', True)
        ], limit=1)

        if not master_seq:
            raise UserError(_("No active sequence found."))

        # Get the next serial number from the sequence master (start point)
        next_serial_number = master_seq.nhcl_next_number

        # Ensure that we generate serial numbers based on the next_serial_number
        if self.next_serial_number and self.next_serial_count:
            print(f"Generating serial numbers starting from: R{next_serial_number}")

            # Generate serial numbers based on the next_serial_number
            generated_serial_numbers = "\n".join(
                lot['lot_name'] for lot in
                self.env['stock.lot'].generate_lot_names(f"R{next_serial_number}", self.next_serial_count)
            )

            # Append the generated serial numbers
            self.serial_numbers = "\n".join(
                [self.serial_numbers, generated_serial_numbers]) if self.serial_numbers else generated_serial_numbers
            self._onchange_serial_numbers()


        action = self.env["ir.actions.actions"]._for_xml_id("mrp.act_assign_serial_numbers_production")
        action['res_id'] = self.id
        return action

    def _update_sequence_master_with_last_serial(self, last_generated_serial):
        """ Update the nhcl_next_number in the sequence master after generating serials """
        try:
            # Find the sequence master record
            master_seq = self.env['nhcl.master.sequence'].search([
                ('nhcl_code', '=', 'Auto Serial Number'),
                ('nhcl_active', '=', True)
            ], limit=1)

            if master_seq:
                # Update the nhcl_next_number to the last generated serial + 1
                prefix = master_seq.nhcl_prefix
                serial_no = last_generated_serial.split(prefix)
                if len(serial_no) > 1:
                    master_seq.nhcl_next_number = int(serial_no[1]) + 1
                    # print('last_no',last_no)
                # master_seq.sudo().write({'nhcl_next_number': last_generated_serial + 1})
                print(f"Updated nhcl_next_number in master sequence to: {last_generated_serial + 1}")
            else:
                raise UserError(_("No active sequence found."))

        except Exception as e:
            print(f"Error updating sequence master: {e}")

    def _assign_serial_numbers(self, cancel_remaining_quantity=False):
        serial_numbers = self._get_serial_numbers()
        productions = self.production_id._split_productions(
            {self.production_id: [1] * len(serial_numbers)}, cancel_remaining_quantity, set_consumed_qty=True)
        production_lots_vals = []
        for serial_name in serial_numbers:
            existing_lot = self.env['stock.lot'].search([('name','=',serial_name)])
            if existing_lot:
                self.serial_numbers = False
                raise UserError(
                    _('Existing Serial Numbers (%s) please remove existing numbers and generate new serial numbers',serial_name))

            production_lots_vals.append({
                'product_id': self.production_id.product_id.id,
                'company_id': self.production_id.company_id.id,
                'name': serial_name,
            })
        production_lots = self.env['stock.lot'].create(production_lots_vals)
        for production, production_lot in zip(productions, production_lots):
            production.lot_producing_id = production_lot.id
            production.qty_producing = production.product_qty
            for workorder in production.workorder_ids:
                workorder.qty_produced = workorder.qty_producing
        if production_lots:
            last_serial_no = production_lots[-1].name
            # After generating the serials, we update the sequence master
            self._update_sequence_master_with_last_serial(last_serial_no)

        if self.mark_as_done:
            productions.button_mark_done()
