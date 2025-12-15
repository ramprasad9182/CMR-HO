{
    'name': 'NHCL Transport Dashboard',
    'Version': '1.0',
    'category': 'Transport of Dashboard',
    'author': 'New Horizons CyberSoft Ltd',
    'company': 'New Horizons CyberSoft Ltd',
    'maintainer': 'New Horizons CyberSoft Ltd',
    'website': "https://www.nhclindia.com",
    'depends': [ 'web', 'stock','product'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/stock.xml',
        'views/transport_dashboard_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'transport_dashboard/static/src/js/Transport_dashboard.js',
            'transport_dashboard/static/src/js/multiselect.js',
            'transport_dashboard/static/src/js/LR_dashboard.js',
            'transport_dashboard/static/src/xml/LR_dashboard.xml',
            'transport_dashboard/static/src/xml/Transport_dashboard.xml',
            'transport_dashboard/static/src/css/style.css',
        ],
    },
    'licence': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
