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

class fleet_vehicle(models.Model):
    _inherit = 'fleet.vehicle'

    transpoter_id = fields.Many2one('dev.transport.details',string='Transporter')
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: