{
    "name": "Odoo Rest Api",
    "summary": """The module create RESTful API for Odoo and allows you to access and modify data using HTTP requests to manage fetch and manage data from the Odoo.""",
    "category": "Extra Tools",
    "version": "17.0",
    "author": "New Horizons Cybersoft Ltd",
    "license": "Other proprietary",
    "website": "https://www.nhclindia.com/",
    "description": """Odoo Rest Api
Add record to database
Delete record to Database
Modify data in Odoo database
Use HTTP to modify data
RESTful API in Odoo
Use HTTP requests to fetch data in Odoo""",
    # "live_test_url"        :  "https://store.webkul.com/Odoo-REST-API.html#",
    "depends": ['base'],
    "data": [
        'security/ir.model.access.csv',
        'views/rest_api_views.xml',
        'views/templates.xml',
    ],
    "demo": ['demo/demo.xml'],
    "images": ['static/description/odoo_restapi_banner.png'],
    "application": True,
    "installable": True,
    "price": 94,
    "currency": "USD",
}
