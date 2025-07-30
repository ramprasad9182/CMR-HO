# -*- coding: utf-8 -*-
{
    'name': 'Sticky list Headers in Odoo',
    'version': '17.0.0.1',
    'summary': """Keeps list view headers visible while scrolling – improves clarity and navigation. Sticky list view headers Odoo guide,Customize sticky list headers in Odoo,Benefits of sticky list headers in Odoo forms,Step-by-step guide to sticky list headers in Odoo,Odoo sticky list header customization experts,Odoo sticky header feature for businesses,Sticky list header setup for Odoo forms.""",
    'description': """Keeps list view headers visible while scrolling – improves clarity and navigation. Sticky list view headers Odoo guide,Customize sticky list headers in Odoo,Benefits of sticky list headers in Odoo forms,Step-by-step guide to sticky list headers in Odoo,Odoo sticky list header customization experts,Odoo sticky header feature for businesses,Sticky list header setup for Odoo forms.""",
    'category': 'Tools',
    'author': 'Reliution',
    'website': "https://www.reliution.com",
    'license': 'LGPL-3',
    'images': ['static/description/banner.gif'],
    'depends': ['base'],
    'assets': {
        'web.assets_backend': [
            "rcs_list_sticky_header/static/src/scss/list_sticky_header.scss",
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
