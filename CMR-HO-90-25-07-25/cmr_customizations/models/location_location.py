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

class location_location(models.Model):
    _name = 'dev.location.location'
    _inherit = ['mail.thread']
    _description = 'Location'
    _order = 'id desc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Location')
    
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: