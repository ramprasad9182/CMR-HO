# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request, content_disposition
import base64
import os, os.path
import csv
from os import listdir
import sys

class Download_xls(http.Controller):
    
    @http.route('/web/binary/download_document', type='http', auth="public")
    def download_document(self,model,id, **kw):

        Model = request.env[model]
        res = Model.browse(int(id))

        if res.sample_option == 'xls':
            invoice_xls = request.env['ir.attachment'].search([('name','=','sale_order_line.xls')])
            filecontent = invoice_xls.datas
            filename = 'Sale Order Line.xls'
            filecontent = base64.b64decode(filecontent)

        elif res.sample_option == 'csv':
            invoice_xls = request.env['ir.attachment'].search([('name','=','sale_order_line.csv')])
            filecontent = invoice_xls.datas
            filename = 'Sale Order Line.csv'
            filecontent = base64.b64decode(filecontent)
         
        if model == 'import.po.line.wizard' and res.sample_option == 'xls':
            invoice_xls = request.env['ir.attachment'].search([('name', '=', 'purchase_order_line.xls')])
            filecontent = invoice_xls.datas
            filename = 'Purchase Order Line.xls'
            filecontent = base64.b64decode(filecontent)

        elif model == 'import.po.line.wizard' and res.sample_option == 'csv':
            invoice_xls = request.env['ir.attachment'].search([('name','=','purchase_order_line.csv')])
            filecontent = invoice_xls.datas
            filename = 'Purchase Order Line.csv'
            filecontent = base64.b64decode(filecontent)

        if model == 'import.invoice.wizard' and res.sample_option == 'xls':
            invoice_xls = request.env['ir.attachment'].search([('name','=','import_invoice_line.xls')])
            filecontent = invoice_xls.datas
            filename = 'import_invoice_lines.xls'
            filecontent = base64.b64decode(filecontent)

        elif model == 'import.invoice.wizard' and res.sample_option == 'csv':
            invoice_xls = request.env['ir.attachment'].search([('name','=','import_invoice_line.csv')])
            filecontent = invoice_xls.datas
            filename = 'import_invoice_lines.csv'
            filecontent = base64.b64decode(filecontent)    

        return request.make_response(filecontent,
            [('Content-Type', 'application/octet-stream'),
            ('Content-Disposition', content_disposition(filename))])
        
        
