# -*- coding: utf-8 -*-
{
    'name': "BeaCukai",

    'summary': """
        BeaCukai documents, BeaCukai reports""",

    'description': """
        
    """,

    'author': "Hendra Saputra - hendrasaputra0501@gmail.com",
    'website': "-",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Beacukai',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','product','account','master_data_custom'],

    # always loaded
    'data': [
        'view/beacukai_view.xml',
        'view/beacukai_line_view.xml',
        'view/wizard_product_income_view.xml',
        'view/wizard_product_outgoing_view.xml',
        'view/wizard_product_mutation_view.xml',
        'view/wizard_product_work_in_process_view.xml',
        'view/beacukai_state_view.xml',
        'view/menuitem.xml',
        'security/beacukai_security.xml',
        'security/ir.model.access.csv',
        'report/report_view.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo.xml',
    ],
}