{
    "name": "checklist",
    "version": "1.0",
    'depends': ['base', 'hr'],
    'data': ['security/ir.model.access.csv',
             'views/checklist_cmr.xml',
             'data/sequence.xml',
             'report/checklistscmr.xml', ],
    # 'images': ['static/description/icon.png'],
    'installable': True,
    'applicable': True
}
