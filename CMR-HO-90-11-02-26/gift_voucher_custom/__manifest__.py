{
    "name": "Gift Voucher (Custom)",
    "version": "1.0",
    "summary": "Create and print gift vouchers (3 per A4)",
    "category": "Accounting",
    "author": "You",
    "license": "LGPL-3",
    "depends": ['loyalty',
                'base',
                'web',
                ],
    "data": [
        "security/ir.model.access.csv",
        "data/sequence_data.xml",

        # Reports first
        "report/gift_voucher_report.xml",
        "report/gift_voucher_template.xml",
        'report/loyalty_card_report.xml',
        'report/loyalty_card_template.xml',

        # Then views
        "views/gift_voucher_views.xml",
        "views/report_view.xml",

    ],
    "installable": True,
    "application": False,
}
