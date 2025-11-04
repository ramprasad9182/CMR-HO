# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class dev_transport_details(models.Model):
    _name = 'dev.transport.details'
    _inherit = ['mail.thread']
    _description = 'Transport Details'
    _order = 'id desc'
    _inherit = ['mail.thread']

    image_1920 = fields.Binary(string='Image')
    name = fields.Char(string='Name')
    contact_name = fields.Char(string='Contact Name',track_visibility='always')
    comment = fields.Char(string='Comment')
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile',track_visibility='always')
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Street 2..')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state',string='State')
    zip = fields.Char(string='Zip')
    country_id = fields.Many2one('res.country',string='Country')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True, default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Users',index=True, tracking=2, default=lambda self: self.env.user)
    vehicle_count = fields.Integer(string='Expense', compute='_compute_fleet_vehicle')
    delivery_order_count = fields.Integer(string='Expense', compute='_compute_delivery_order')
    
    def _compute_delivery_order(self):
        for order in self:
            picking_ids = self.env['stock.picking'].search([('transpoter_id','=',self.id)])
            order.delivery_order_count = len(picking_ids)

    def _compute_fleet_vehicle(self):
        for order in self:
            vehicle_ids = self.env['fleet.vehicle'].search([('transpoter_id','=',self.id)])
            order.vehicle_count = len(vehicle_ids)
            
    def action_view_delivery_order(self):
        action = self.env.ref('stock.stock_picking_action_picking_type').read()[0]
        picking_ids = self.env['stock.picking'].search([('transpoter_id','=',self.id)])
        if len(picking_ids) > 1:
            action['domain'] = [('id', 'in', picking_ids.ids)]
        elif picking_ids:
            action['views'] = [(self.env.ref('stock.view_picking_form').id, 'form')]
            action['res_id'] = picking_ids.id
        return action
    
    def action_view_vehicles_details(self):
        action = self.env.ref('fleet.fleet_vehicle_action').read()[0]
        vehicle_ids = self.env['fleet.vehicle'].search([('transpoter_id','=',self.id)])
        if len(vehicle_ids) > 1:
            action['domain'] = [('id', 'in', vehicle_ids.ids)]
        elif vehicle_ids:
            action['views'] = [(self.env.ref('fleet.fleet_vehicle_view_form').id, 'form')]
            action['res_id'] = vehicle_ids.id
        return action
        


    
    

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
