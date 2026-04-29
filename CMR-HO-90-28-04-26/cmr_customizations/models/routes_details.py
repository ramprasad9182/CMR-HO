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

class routes_details(models.Model):
    _name = 'dev.routes.details'
    _inherit = ['mail.thread']
    _description = 'Routes Details'
    _order = 'id desc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Name')
    transpoter_id = fields.Many2one('dev.transport.details',string='Transporter',tracking=2)
    location_details_ids = fields.One2many('routes.location.details','routes_detail_id')
    

class routes_location_details(models.Model):
    _name = 'routes.location.details'
    _description = "Routes Location Details"
    
    routes_detail_id = fields.Many2one('dev.routes.details',string='Routes Detail')
    
    source_location_id = fields.Many2one('dev.location.location',string='Source Location')
    destination_location_id = fields.Many2one('dev.location.location',string='Destination Location')
    distance = fields.Float(string='Distance(KM)')
    transport_charges = fields.Float(string='Transport Charges')
    time_hour = fields.Char(string='Time Hours')
    nhcl_id = fields.Integer(string="Nhcl Id", copy=False, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        self.env.cr.execute("SELECT MAX(nhcl_id) FROM routes_location_details")
        max_nhcl_id = self.env.cr.fetchone()[0] or 0
        next_id = max_nhcl_id + 1
        for vals in vals_list:
            vals['nhcl_id'] = next_id
            next_id += 1
        return super().create(vals_list)
    
    
    
    
        


    
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
