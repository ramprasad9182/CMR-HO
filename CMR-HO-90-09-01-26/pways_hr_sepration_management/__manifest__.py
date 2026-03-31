# -*- coding: utf-8 -*-
{
    'name': 'End of Service Management',
    'version': '17.0',
    'summary': """Create separation request and link it with gratuity record and create employee final settlement which includes (gratuity, leaves ,salary, overtime, notice peroid amount and other earnings)
                    Main Features are
                    Employee Resignation
                    Employee Gratuity
                    Employe Separation
                    Employee Settlement
                    Employee Closer
                    End of Service
                    Final Settlement """,
    'description': """  Employee Resignation
                        Employee Gratuity
                        Employe Separation
                        Employee Settlement
                        Employee Closer
                        End of Service
                        Final Settlement 
    """,
    'category': 'Generic Modules/Human Resources',
    'author':'Preciseways',
    'depends': ['hr_holidays', 'hr_attendance', 'account','hr_work_entry_contract'],
    'data': ['security/ir.model.access.csv',
             'data/hr_sequence.xml',
             'data/hr_resign.xml',
             'views/hr_employee_view.xml',
             'views/hr_sepration_view.xml',
             'views/hr_gratuity_view.xml',
             'views/hr_settlement_view.xml',
             'views/res_config_settings_view.xml',
             'report/report_action.xml',
             'report/sepration_template.xml',
    ],
    'installable': True,
    'application': True,
    'price': 41.0,
    'currency': 'EUR',
    'images':['static/description/banner.png'],
    'license': 'OPL-1',
}
