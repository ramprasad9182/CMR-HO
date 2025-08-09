{
    "name": "Recruitment Interview Form",
    "version": "1.0",
    "depends": ["base", "website", "mail"],
    "author": "Your Name",
    "category": "Human Resources",
    "data": [
        "security/interview_form_groups.xml",
        "security/ir.model.access.csv",
        "data/email_template.xml",
        "wizard/survey_wizard_views.xml",
        "views/interview_form_views.xml",
        "views/website_form_templates.xml",
        "views/hr_applicant_views.xml",
        "views/thank_you.xml",

    ],
    'assets': {
            'web.assets_frontend': [
                'recruitment_interview_form/static/src/js/interview_form.js',
            ],
        },
    "installable": True,
    "application": True,
}