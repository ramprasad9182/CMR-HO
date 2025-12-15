{
    'name': 'HR Customizations',
    'author': 'Nhcl',
    'summery': 'HR Customizations',
    'version': '1.0',
    'depends': ['base', 'hr','hr_attendance','l10n_in_hr_payroll', 'web','hr_holidays'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_upload_views.xml',
        'views/hr_attendance_views.xml',
        'views/hr_payslip_views.xml',
        'views/hr_leave_views.xml',
        'reports/non_ctc_payslip.xml',
    ],
    'application': True,
    'auto_installable': False,
    'installable': True
}
