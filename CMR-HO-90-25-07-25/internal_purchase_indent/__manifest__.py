{
    'name': 'Internal Purchase Indent',
    'version': '1.0',
    'category': 'Purchases',
    'summary': 'Handles internal purchase indents with PO lines',
    'depends': ['base', 'purchase', 'stock', 'cmr_customizations', ],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/internal_purchase_indent_views.xml',
        'report/pipogrc.xml',
    ],
    'installable': True,
    'application': True,
    'auto_installable': False,
}
