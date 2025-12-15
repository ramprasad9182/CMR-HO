{
    'name': 'Birthdaywishes',
    'version': '17.0',
    'category': 'Inventory',
    'summary': 'Birthdaywishes',
    'depends': ['base','hr','web'],
    'data': [
        "views/birthday_dashboard_action.xml",
    ],
    'assets': {
            'web.assets_backend': [
                'Birthday_Wishes/static/src/components/birthday_dashboard.js',
                'Birthday_Wishes/static/src/components/birthday_dashboard.xml',
                # 'Birthday_Wishes/static/src/components/**/*.scss',
            ],
    },
    'installable': True,
    'application': False,
}
