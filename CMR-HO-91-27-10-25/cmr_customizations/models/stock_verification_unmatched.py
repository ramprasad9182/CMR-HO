import json

import requests

from odoo import models, fields,api
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)

class StockVerificationUnmatched(models.Model):
    _name = 'stock.verification.unmatched'
    _description = 'Unmatched Scanned Barcodes'

    serial_number = fields.Char("Serial Number")
    barcode = fields.Char("Barcode")
    store_name = fields.Char(string="Scanned Store Name")
    store_receipt_number = fields.Char(string="Store Receipt Number")
    ho_delivery_number =  fields.Char(string="HO Delivery Doc")
    product_dest_location = fields.Char(string="Dest Location")
    sent_flag =  fields.Boolean(string="Verification Done")
    company_id = fields.Many2many('res.company', string="Actual Store Name")
    batch_schedule_date = fields.Datetime(string="Batch Schedule Date")
    store_date = fields.Datetime(string="Scanned Date in Store")



    def action_replicate(self):
        if not self.sent_flag:
            try:
                ho_store = self.env["nhcl.ho.store.master"].sudo().search([
                    ("nhcl_store_name.name", "=", self.store_name)
                ], limit=1)

                if ho_store:
                    store_ip = ho_store.nhcl_terminal_ip
                    store_port = ho_store.nhcl_port_no
                    store_api_key = ho_store.nhcl_api_key

                    headers_source = {
                        'api-key': f"{store_api_key}",
                        'Content-Type': 'application/json'
                    }

                    identifier = None
                    domain=[]
                    if self.serial_number:
                       identifier = self.serial_number
                       domain = [('stock_serial', '=', self.serial_number)]
                    elif self.barcode:
                        identifier = self.barcode
                        domain = [('stock_product_barcode', '=', self.barcode)]

                    # Build API URL
                    base_url = f"http://{store_ip}:{store_port}/api/last.scanned.serial.number/search"
                    location_data_url = f"{base_url}?domain={json.dumps(domain)}"

                    # Call API
                    response = requests.get(location_data_url, headers=headers_source)
                    response.raise_for_status()
                    location = response.json()

                    location_ids = location.get("data")
                    print("1111111",location_ids)
                    if location_ids:
                        # Take only first record
                        record_id = location_ids[0]["id"]
                        if record_id:
                            # Update remote record (set state=True)
                            update_url = f"http://{store_ip}:{store_port}/api/last.scanned.serial.number/{record_id}"
                            update_data = {"state": True}
                            update_response = requests.put(update_url, headers=headers_source, json=update_data)
                            update_response.raise_for_status()
                            _logger.info(f"Remote record {record_id} updated with state=True")

                            # After successful remote update, update local flag
                            self.sent_flag = True
                            _logger.info(f"Local record {self.id} marked as sent.")

                else:
                    _logger.warning(f"No HO Store found for Store Name: {self.store_name}")

            except requests.exceptions.RequestException as e:
                _logger.error(f"Request error while fetching/updating location for {identifier}: {e}")
            except Exception as e:
                _logger.error(f"Unexpected error for {identifier}: {e}")



    def action_check_same_store(self):
        """Ensure all selected records have the same store_name"""
        store_names = self.mapped('store_name')
        if len(set(store_names))> 1:
            raise ValidationError(
                "You cannot process multiple records with different Stores. "
                "Please select records with the same store only."
            )
        for rec in self:
            if rec.sent_flag:
                continue  # Skip already sent records

            try:
                ho_store = self.env["nhcl.ho.store.master"].sudo().search([
                    ("nhcl_store_name.name", "=", rec.store_name)
                ])

                if not ho_store:
                    _logger.warning(f"No HO Store found for Store Name: {rec.store_name}")
                    continue

                store_ip = ho_store.nhcl_terminal_ip
                store_port = ho_store.nhcl_port_no
                store_api_key = ho_store.nhcl_api_key

                headers_source = {
                    'api-key': f"{store_api_key}",
                    'Content-Type': 'application/json'
                }

                identifier = None
                domain = []
                if self.serial_number:
                    identifier = self.serial_number
                    domain = [('stock_serial', '=', self.serial_number)]
                elif self.barcode:
                    identifier = self.barcode
                    domain = [('stock_product_barcode', '=', self.barcode)]

                # Build API URL
                base_url = f"http://{store_ip}:{store_port}/api/last.scanned.serial.number/search"
                # domain = [('stock_serial', '=', rec.serial_number)]
                location_data_url = f"{base_url}?domain={json.dumps(domain)}"

                # Call API
                response = requests.get(location_data_url, headers=headers_source, timeout=10)
                response.raise_for_status()
                location = response.json()

                location_ids = location.get("data")
                if location_ids:
                    record_id = location_ids[0]["id"]
                    if record_id:
                        # Update remote record (set state=True)
                        update_url = f"http://{store_ip}:{store_port}/api/last.scanned.serial.number/{record_id}"
                        update_data = {"state": True}
                        update_response = requests.put(update_url, headers=headers_source, json=update_data)
                        update_response.raise_for_status()
                        _logger.info(f"Remote record {record_id} updated with state=True")

                        # After successful remote update, update local flag
                        rec.sent_flag = True
                        _logger.info(f"Local record {rec.id} marked as sent.")

            except requests.exceptions.RequestException as e:
                _logger.error(f"Request error while fetching/updating location for {identifier}: {e}")
            except Exception as e:
                _logger.error(f"Unexpected error for {identifier}: {e}")
        return {
            'type': 'ir.actions.act_window_close'
        }

    @api.model
    def create(self, vals):
        # Create the first record
        record = super(StockVerificationUnmatched, self).create(vals)

        if record.serial_number:
            lot = self.env['stock.quant'].search([
                ('lot_id.name', '=', record.serial_number),
                ('company_id.nhcl_company_bool', '=', False),
                ('quantity', '>', 0)
            ], limit=1)
            if lot:
                single_company_id= lot.lot_id.company_id.id
                record.company_id = [(6, 0, [single_company_id])]

        elif record.barcode:
            lots = self.env['stock.quant'].search([
                ('lot_id.ref', '=', record.barcode),
                ('company_id.nhcl_company_bool', '=', False),
                ('quantity', '>', 0)
            ])

            # Collect unique company_ids
            company_ids = lots.mapped('company_id').ids  # gets list of IDs

            # Assign to Many2many field
            record.company_id = [(6, 0, company_ids)]

        if record.ho_delivery_number:
            picking = self.env['stock.picking'].search([
                ('name', '=', record.ho_delivery_number),
                ('picking_type_id.code', '=', 'outgoing')  # only delivery orders
            ], limit=1)
            print("++++",picking)
            if picking:
                record.batch_schedule_date = picking.batch_id.scheduled_date

        return record
