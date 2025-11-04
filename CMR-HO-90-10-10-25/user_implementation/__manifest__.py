
{
    "name": "License Key Generater",
    "depends": [
        "base",'nhcl_ho_store_cmr_integration','web'
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/user_license_screen_views.xml",
        "data/email_template.xml",
        'wizard/license_key_generation_views.xml',
        "data/ir_sequence_data.xml"
    ],


}
