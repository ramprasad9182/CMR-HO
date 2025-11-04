{
    "name": "Stock Inventory Counting",
    "version": "17.0",
    "author": "TechUltra Solutions Private Limited",
    'company': 'TechUltra Solutions Private Limited',
    "website": "https://www.techultrasolutions.com/",
    "category": "Inventory",
    "summary": """
        Inventory counting is a major operation in inventory management as daily basis for 3PL warehouse and
        Normal warehouse, Odoo provides this feature with
        limited functionality. Using the tech-ultra "Advance Inventory Counting" app, you may simplify
        inventory count with the responsible person. Scroll down to know more about our app.
    """,
    "description": """
        Stock inventory count
        Inventory counting
        Stock Count
        Inventory counting Report
        Stock Inventory Report
        Odoo Erp Stock Report
        Stock Report.
    """,
    "depends": ["stock", "product_expiry"],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_adjustment_view.xml",

        "views/stock_inventory_views.xml",
    ],
    "images": ["static/description/main_screen.gif"],
    "price": 28.99,
    "currency": "USD",
    "installable": True,
    "application": True,
    "license": "OPL-1",
}
