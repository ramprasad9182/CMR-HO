{
    'name': 'Dynamic Label Upload or Download',
    'version': '1.0',
    'summary': 'Manage upload and download of dynamic labels',
    'category': 'Tools',
    'author': 'NHCL',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/dynamic_label_views.xml',
    ],
    'installable': True,
    'application': True,
}
