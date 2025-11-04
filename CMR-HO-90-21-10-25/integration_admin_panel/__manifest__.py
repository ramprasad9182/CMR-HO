{
    'name': 'Integration Admin Panel',
    'version': '1.0',
    'category': 'Tally Integration Screen',
    'depends': ['mail', 'base', 'get_journal_entries', ],
    'data': ['security/ir.model.access.csv',
             'views/tally_integration.xml',
             'data/sequence.xml', ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}
