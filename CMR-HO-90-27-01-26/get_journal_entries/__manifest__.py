{
    'name': 'NHCL JE',
    'version': '1.0',
    'sequence': 4,
    'category': 'Accounting',
    "author": "New Horizons Cybersoft Ltd",
    "website": "https://www.nhclindia.com/",
    'summary': 'JE',
    'description': """
This module contains all the common features of Transport and Check.
    """,
    'depends': ['base','account','l10n_in','cmr_customizations'],
    'data': [
        'security/ir.model.access.csv',
        'views/account_group_view.xml',
        'views/state_company_master_views.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
