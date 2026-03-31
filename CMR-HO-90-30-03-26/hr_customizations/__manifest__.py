{
    'name': 'HR Customizations',
    'author': 'Nhcl',
    'summery': 'HR Customizations',
    'version': '1.0',
    'depends': ['base', 'hr', 'hr_attendance', 'l10n_in_hr_payroll', 'web', 'hr_holidays', 'cmr_new_recruitments','planning'],
    'data': [
        'security/ir.model.access.csv',
        'security/hr_upload_record_rule.xml',
        'security/security.xml',
        'views/hr_upload_views.xml',
        'views/hr_attendance_views.xml',
        'reports/non_ctc_payslip.xml',
        'views/hr_payslip_views.xml',
        'views/hr_leave_views.xml',
        'views/shift_deduction_master_views.xml',
        'views/shift_addition_master_views.xml',
        'views/lunch_deduction_summary_views.xml',
        'views/break_deduction_summary_views.xml',
        'views/lunch_addition_summary_views.xml',

    ],
    'application': True,
    'auto_installable': False,
    'installable': True
}
