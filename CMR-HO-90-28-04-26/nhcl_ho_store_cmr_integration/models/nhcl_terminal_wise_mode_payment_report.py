from odoo import models,fields,api,_
import requests
from datetime import datetime, time
import pytz

from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
import base64
import io

import xlsxwriter
from odoo.tools import format_date
from collections import defaultdict


class NhclTreminalMOPReport(models.Model):
    _name = 'nhcl.teminal.mop.report'
    _description = "Terminal wise MOP Report"
    _rec_name  = 'name'

    def _default_from_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(3, 30, 0))
        )


    def _default_to_date(self):
        today = fields.Date.context_today(self)
        return fields.Datetime.to_datetime(
            datetime.combine(today, time(18, 30, 0))
        )


    from_date = fields.Datetime(
        string='From Date',
        default=_default_from_date
    )
    to_date = fields.Datetime(
        string='To Date',
        default=_default_to_date
    )
    nhcl_terminal_wise_mop_report_ids = fields.One2many('nhcl.teminal.mop.report.line', 'nhcl_terminal_wise_mop_report_id')
    nhcl_store_id = fields.Many2many('nhcl.ho.store.master', string='Company')
    name = fields.Char('Name', default="Terminal Wise MOP Report")
    config_id = fields.Many2one('pos.config', string='Terminal')
    payment_method = fields.Many2one('pos.payment.method', string='MOP')
    total_cash = fields.Float(compute="_compute_nhcl_show_totals", string='Total Cash')
    total_axis = fields.Float(compute="_compute_nhcl_show_totals", string='Total Axis')
    total_hdfc = fields.Float(compute="_compute_nhcl_show_totals", string='Total HDFC')
    total_kotak = fields.Float(compute="_compute_nhcl_show_totals", string='Total Kotak')
    total_paytm = fields.Float(compute="_compute_nhcl_show_totals", string='Total Paytm')
    total_sbi = fields.Float(compute="_compute_nhcl_show_totals", string='Total SBI')
    total_bajaj = fields.Float(compute="_compute_nhcl_show_totals", string='Total Bajaj')
    total_mobikwik = fields.Float(compute="_compute_nhcl_show_totals", string='Total Mobikwik')
    total_cheque = fields.Float(compute="_compute_nhcl_show_totals", string='Total Cheque')
    total_gift_voucher = fields.Float(compute="_compute_nhcl_show_totals", string='Total Gift Voucher')
    total_credit_note_settlement = fields.Float(compute="_compute_nhcl_show_totals",
                                                string='Total Credit Note Settlement')
    grand_total = fields.Float(compute="_compute_nhcl_show_totals", string='Grand Total')

    def _compute_nhcl_show_totals(self):
        for rec in self:
            lines = rec.nhcl_terminal_wise_mop_report_ids
            rec.total_cash = sum(lines.mapped('cash'))
            rec.total_axis = sum(lines.mapped('axis'))
            rec.total_hdfc = sum(lines.mapped('hdfc'))
            rec.total_kotak = sum(lines.mapped('kotak'))
            rec.total_paytm = sum(lines.mapped('paytm'))
            rec.total_sbi = sum(lines.mapped('sbi'))
            rec.total_bajaj = sum(lines.mapped('bajaj'))
            rec.total_mobikwik = sum(lines.mapped('mobikwik'))
            rec.total_cheque = sum(lines.mapped('cheque'))
            rec.total_gift_voucher = sum(lines.mapped('gift_voucher'))
            rec.total_credit_note_settlement = sum(lines.mapped('credit_note_settlement'))
            rec.grand_total = sum(lines.mapped('grand_total'))


    # @api.model
    # def default_get(self, fields_list):
    #     res = super(NhclTreminalMOPReport, self).default_get(fields_list)
    #     replication_data = []
    #     ho_store_id = self.env['nhcl.ho.store.master'].search(
    #         [('nhcl_store_type', '!=', 'ho'), ('nhcl_active', '=', True)])
    #     for i in ho_store_id:
    #         vals = {
    #             'nhcl_store_id': i.nhcl_store_name.id,
    #         }
    #         replication_data.append((0, 0, vals))
    #     res.update({'nhcl_store_id': replication_data})
    #     return res

    @api.model
    def _default_nhcl_stores(self):
        stores = self.env['nhcl.ho.store.master'].search([
            ('nhcl_store_type', '!=', 'ho'),
            ('nhcl_active', '=', True)
        ])
        return stores.mapped('nhcl_store_name').ids

    def get_terminal_wise_mop_report(self):
        for each in self:

            # ✅ safer clear
            each.nhcl_terminal_wise_mop_report_ids = [(5, 0, 0)]

            from_date = fields.Datetime.to_datetime(each.from_date)
            to_date = fields.Datetime.to_datetime(each.to_date)

            for rec in each.nhcl_store_id:

                orders = self.env['pos.order'].search([
                    ('date_order', '>=', from_date),
                    ('date_order', '<=', to_date),
                    ('company_id', '=', rec.nhcl_store_name.id)
                ])

                terminal_data = defaultdict(lambda: {
                    'cash': 0.0,
                    'axis': 0.0,
                    'hdfc': 0.0,
                    'kotak': 0.0,
                    'paytm': 0.0,
                    'sbi': 0.0,
                    'bajaj': 0.0,
                    'mobikwik': 0.0,
                    'cheque': 0.0,
                    'gift_voucher': 0.0,
                    'credit_note_settlement': 0.0,
                })

                # -----------------------------
                # POS PAYMENTS
                # -----------------------------
                for order in orders:
                    terminal = order.config_id.id

                    for payment in order.payment_ids:
                        if each.payment_method:
                            if payment.payment_method_id.id != each.payment_method.id:
                                continue
                        method = (payment.payment_method_id.name or '').lower()
                        amount = payment.amount

                        if 'cash' in method:
                            terminal_data[terminal]['cash'] += amount
                        elif 'axis' in method:
                            terminal_data[terminal]['axis'] += amount
                        elif 'hdfc' in method:
                            terminal_data[terminal]['hdfc'] += amount
                        elif 'kotak' in method:
                            terminal_data[terminal]['kotak'] += amount
                        elif 'paytm' in method:
                            terminal_data[terminal]['paytm'] += amount
                        elif 'sbi' in method:
                            terminal_data[terminal]['sbi'] += amount
                        elif 'bajaj' in method:
                            terminal_data[terminal]['bajaj'] += amount
                        elif 'mobikwik' in method:
                            terminal_data[terminal]['mobikwik'] += amount
                        elif 'cheque' in method:
                            terminal_data[terminal]['cheque'] += amount
                        elif 'gift' in method or 'voucher' in method:
                            terminal_data[terminal]['gift_voucher'] += amount
                        elif 'credit note' in method:
                            terminal_data[terminal]['credit_note_settlement'] += amount

                # -----------------------------
                # CREDIT NOTE ISSUES
                # -----------------------------
                credit_moves = self.env['account.move'].search([
                    ('invoice_date', '>=', from_date),
                    ('invoice_date', '<=', to_date),
                    ('company_id', '=', rec.nhcl_store_name.id),
                    ('journal_id.name', '=', 'Credit Note Issue')
                ])

                for move in credit_moves:
                    pos_order = self.env['pos.order'].search(
                        [('name', '=', move.invoice_origin)],
                        limit=1
                    )

                    if not pos_order:
                        continue

                    if rec.config_id and pos_order.config_id.id != rec.config_id.id:
                        continue
                    terminal = pos_order.config_id.id
                    terminal_data[terminal]['credit_note_issues'] += move.amount_total

                # -----------------------------
                # CREATE LINES
                # -----------------------------
                vals_list = []

                for terminal_id, values in terminal_data.items():
                    grand_total = (
                            values['cash'] +
                            values['axis'] +
                            values['hdfc'] +
                            values['kotak'] +
                            values['paytm'] +
                            values['sbi'] +
                            values['bajaj'] +
                            values['mobikwik'] +
                            values['cheque'] +
                            values['gift_voucher'] +
                            values['credit_note_settlement']
                    )
                    vals_list.append({
                        'nhcl_terminal_wise_mop_report_id': each.id,  # ✅ FIXED
                        'config_id': terminal_id,
                        'nhcl_store_id': rec.id,
                        'cash': values['cash'],
                        'axis': values['axis'],
                        'hdfc': values['hdfc'],
                        'kotak': values['kotak'],
                        'paytm': values['paytm'],
                        'sbi': values['sbi'],
                        'bajaj': values['bajaj'],
                        'mobikwik': values['mobikwik'],
                        'cheque': values['cheque'],
                        'gift_voucher': values['gift_voucher'],
                        'credit_note_settlement': values['credit_note_settlement'],
                        'grand_total': grand_total,

                    })

                if vals_list:
                    self.env['nhcl.teminal.mop.report.line'].create(vals_list)

    def action_to_reset(self):
        self.write({
            'nhcl_store_id': False,
            'from_date': False,
            'to_date': False
        })
        for each in self:
            each.nhcl_terminal_wise_mop_report_ids.unlink()


    def action_mop_detailed_report(self):
        self.ensure_one()

        return {
            'type': 'ir.actions.act_window',
            'name': 'Terminal Wise Mode Of Payment Report',
            'res_model': 'nhcl.teminal.mop.report.line',
            'view_mode': 'tree,pivot',
            'domain': [('nhcl_terminal_wise_mop_report_id', '=', self.id)],
            'context': {
                'default_nhcl_terminal_wise_mop_report_id': self.id
            }
        }

class NhclTreminalMOPLine(models.Model):
    _name = 'nhcl.teminal.mop.report.line'
    _description = "Terminal wise MOP Report Line"

    nhcl_terminal_wise_mop_report_id = fields.Many2one('nhcl.teminal.mop.report', string="MOP Report")
    config_id = fields.Many2one('pos.config', string='Terminal')
    nhcl_store_id = fields.Many2one('nhcl.ho.store.master', string='Company')
    cash = fields.Float(string='Cash')
    axis = fields.Float(string='Axis')
    hdfc = fields.Float(string='HDFC')
    kotak = fields.Float(string='Kotak')
    paytm = fields.Float(string='Paytm')
    sbi = fields.Float(string='SBI')
    bajaj = fields.Float(string='Bajaj')
    mobikwik = fields.Float(string='Mobikwik')
    cheque = fields.Float(string='Cheque')
    gift_voucher = fields.Float(string='Gift Voucher')
    credit_note_settlement = fields.Float(string='Credit Note Settlement')
    grand_total = fields.Float(string='Grand Total')