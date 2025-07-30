from odoo import models, fields, api, _
import requests
import logging
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class LoyaltyCard(models.Model):
    _inherit = 'loyalty.card'

    _sql_constraints = []

    @api.constrains('code', 'company_id')
    def _check_code_unique_per_company(self):
        for record in self:
            domain = [
                ('code', '=', record.code),
                ('company_id', '=', record.company_id.id),
                ('id', '!=', record.id)
            ]
            if self.search_count(domain):
                raise ValidationError('A coupon/loyalty card must have a unique code per company.')

    nhcl_used_card = fields.Boolean(string="Used Card", copy=False)

    def get_stores_loyalty_card_data(self, store_ip, store_port, store_api_key, loyalty_card_domain):
        headers_source = {'api-key': f"{store_api_key}", 'Content-Type': 'application/json'}
        loyalty_card_search = f"http://{store_ip}:{store_port}/api/loyalty.card/search"
        loyalty_card_url = f"{loyalty_card_search}?domain={loyalty_card_domain}"
        loyalty_card_data = requests.get(loyalty_card_url, headers=headers_source).json()
        loyalty_card = loyalty_card_data.get("data")
        return loyalty_card

    def update_loyalty_card(self):
        gift_cards = self.search([('points','>',0)])
        for rec in gift_cards.filtered(lambda x:x.program_id.update_replication == True and x.program_id.active):
            if rec.points > 0 and rec.program_id.active == True and rec.program_id.update_replication == True:
                for program in rec.program_id.loyalty_program_id.filtered(lambda x: x.date_replication == True):
                    store = program.master_store_id
                    store_ip = program.nhcl_terminal_ip
                    store_port = program.nhcl_port_no
                    store_api_key = program.nhcl_api_key
                    print('code',rec.code)
                    loyalty_card_domain = [('points', '=', 0), ('code', '=', rec.code)]
                    used_loyalty_card = rec.get_stores_loyalty_card_data(store_ip, store_port, store_api_key,
                                                                         loyalty_card_domain)

                    if used_loyalty_card:
                        for card in used_loyalty_card:
                            points = card.get("points")
                            card_points = {
                                'points': points,
                                'nhcl_used_card': True

                            }
                            for program_id in rec.program_id.loyalty_program_id.filtered(
                                    lambda x: x.date_replication == True and x.nhcl_terminal_ip != store_ip):

                                print('program_id', program_id.nhcl_terminal_ip)
                                print('program_id', program_id.nhcl_port_no)
                                print('nhcl_api_key',  program_id.nhcl_api_key)
                                loyalty_card_domain = [('points', '>', 0), ('code', '=', rec.code)]
                                loyalty_card = rec.get_stores_loyalty_card_data(program_id.nhcl_terminal_ip,
                                                                                program_id.nhcl_port_no, program_id.nhcl_api_key,
                                                                                loyalty_card_domain)
                                headers_source = {'api-key': f"{program_id.nhcl_api_key}", 'Content-Type': 'application/json'}
                                if loyalty_card:
                                    print('store_ip',store_ip)
                                    print('store_port',store_port)
                                    loyalty_card_update = f"http://{program_id.nhcl_terminal_ip}:{program_id.nhcl_port_no}/api/loyalty.card/{loyalty_card[0]['id']}"
                                    response = requests.put(loyalty_card_update, headers=headers_source,
                                                            json=card_points)
                                    response.raise_for_status()
                                    response_json = response.json()

                                    message = response_json.get("message", "No message provided")
                                    response_code = response_json.get("responseCode", "No response code provided")
                                    if response_json.get("success") == False:
                                        _logger.info(
                                            f"Failed to update Gift Card {message} '{store_ip}' with partner '{store_port}'. Error: ")
                                        logging.error(
                                            f"Failed to update Gift Card  {message} '{store_ip}' with partner '{store_port}'. Error:")
                                        store.create_cmr_store_server_replication_log('success', message)
                                        store.create_cmr_store_replication_log(response_json['object_name'], rec.id, 200,
                                                                               'update', 'failure', message)

                                    else:
                                        _logger.info(
                                            f"Successfully update Gift Card {rec.code} {message} '{store_ip}' with partner '{store_port}'.")
                                        logging.info(
                                            f"Successfully update Gift Card {rec.code} {message} '{store_ip}' with partner '{store_port}'.")
                                        store.create_cmr_store_server_replication_log('success', message)
                                        store.create_cmr_store_replication_log(response_json['object_name'], rec.id, 200,
                                                                               'update', 'success', f"Successfully update Gift Card {rec.code}")
                            rec.points = 0
                            rec.nhcl_used_card = True
