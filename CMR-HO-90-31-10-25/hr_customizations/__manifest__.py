{
    'name': 'HR Customizations',
    'author': 'Nhcl',
    'summery': 'HR Customizations',
    'version': '1.0',
    'depends': ['base', 'hr','hr_attendance','l10n_in_hr_payroll', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_upload_views.xml',
        'views/hr_attendance_views.xml',
        'views/hr_payslip_views.xml',
    ],
    'application': True,
    'auto_installable': False,
    'installable': True
}
