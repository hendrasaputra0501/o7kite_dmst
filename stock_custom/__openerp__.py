# -*- coding: utf-8 -*-
{
    'name': "stock_custom",

    'summary': """
        Finish Goods Category Moves, """,

    'description': """
        
    """,

    'author': "Hendra Saputra - hendrasaputra0501@gmail.com",
    'website': "-",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Warehouse',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','beacukai','master_data_custom'],

    # always loaded
    'data': [
        'sequence.xml',
        'product_view.xml',
        'stock_view.xml',
        'report/report_view.xml',
        'wizard_product_mutation_view.xml',
        'wizard_product_work_in_process_view.xml',
        'wizard_product_rm_issue_view.xml',
        'wizard_product_fg_receipt_view.xml',
        'security/stock_custom_security.xml',
        'security/ir.model.access.csv',
    ],
    # only loaded in demonstration mode
    'demo': [
    ],
}