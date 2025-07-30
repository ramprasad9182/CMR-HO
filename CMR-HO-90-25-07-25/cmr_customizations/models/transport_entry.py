# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields, api, _
from datetime import date
from odoo.exceptions import ValidationError

class transport_entry(models.Model):
    _name = 'dev.transport.entry'
    _inherit = ['mail.thread']
    _description = 'Transport Entry'
    _order = 'id desc'
    _inherit = ['mail.thread']

    @api.onchange('transport_details_id')
    def onchange_transport_details_id(self):
        domain = {}
        domain['vehicle_id'] = [('name', '=', 'odoo,dev,getodoo,etc#124')]
        if self.transport_details_id:
            domain['vehicle_id'] = [('transpoter_id', '=', self.transport_details_id.id)]
        return {'domain': domain}

    def unlink(self):
        if any('start' != rec.state for rec in self):
            raise ValidationError(_('''Only 'START' entry can be deleted'''))
        return super(transport_entry, self).unlink()

    name = fields.Char(string='Number')
    transport_date = fields.Datetime(string='Transport Date',default=date.today())
    picking_id = fields.Many2one('stock.picking',string='Delivery Order',track_visibility='always')
    lr_number = fields.Char(string='LR Number',track_visibility='always')
    partner_id = fields.Many2one('res.partner',string='Customer',track_visibility='always')
    contact_name = fields.Char(string='Contact Name')
    no_of_parcel = fields.Integer(string='No Of Parcels',track_visibility='always')
    vehicle_id = fields.Many2one('fleet.vehicle',string='Transport Vehicle')
    transport_details_id = fields.Many2one('dev.transport.details',string='Transport By')
    note = fields.Text(string='Note')
    state = fields.Selection([('start','Start'),('waiting','Waiting'),
                              ('in_progress','In-Progress'),('done','Done'),
                              ('cancel','Cancel')],string='State',track_visibility='always',default='start')
    transport_location_line = fields.One2many('transport.location.details','transport_entry_id',string='Transport Location')
    
    def action_start(self):
        for data in self:
            for line in data.transport_location_line:
                line.start_time = fields.Date.today()
            data.state = 'in_progress'
        return True
    def action_cancel(self):
        for data in self:
            for line in data.transport_location_line:
                line.start_time = False
                line.end_time = False
            data.state = 'cancel'
        return True
    def action_waiting(self):
        for data in self:
            data.state = 'waiting'
        return True
    
    def action_re_start(self):
        for data in self:
            data.state = 'start'
        return True
        
    def action_done(self):
        for data in self:
            for line in data.transport_location_line:
                line.end_time = fields.Date.today()
            data.state = 'done'
        return True
    

class transport_location_details(models.Model):
    _name = 'transport.location.details'
    
    transport_entry_id = fields.Many2one('dev.transport.entry',string='Transport Entry')
    picking_id = fields.Many2one('stock.picking',string='Delivery Order')
    source_location_id = fields.Many2one('dev.location.location',string='Source Location')
    destination_location_id = fields.Many2one('dev.location.location',string='Destination Location')
    distance = fields.Float(string='Distance(KM)')
    transport_charges = fields.Float(string='Transport Charges')
    time_hour = fields.Char(string='Time Hours')
    start_time = fields.Datetime(string='Start Time')
    end_time = fields.Datetime(string='End Time')
    tracking_number = fields.Char(string='Tracking Number')
    state = fields.Selection(string='State' , related='transport_entry_id.state',store=True)
    
    
    
    
    
        


    
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
