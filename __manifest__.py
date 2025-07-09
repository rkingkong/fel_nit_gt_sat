{
    'name': 'FEL Guatemala - Factura Electrónica en Línea',
    'version': '17.0.3.1.0',  # Increment version
    'category': 'Accounting/Localizations/EDI',
    'sequence': 1,
    'summary': 'Guatemala Electronic Invoice (FEL) Integration with SAT',
    'author': 'Kesiyos Restaurant Systems',
    'website': 'https://github.com/rkingkong/fel_nit_gt_sat',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',
        'sale',
        'purchase',
        'stock',
        'point_of_sale',
        'l10n_gt',
    ],
    'external_dependencies': {
        'python': [
            'requests',
            'xmltodict',
            'lxml',
            'cryptography',
        ],
    },
    'data': [
        # Security files MUST come first
        'security/fel_security.xml',
        'security/ir.model.access.csv',
        
        # Data files
        'data/fel_document_types.xml',
        
        # Views - in dependency order
        'views/fel_certification_provider_views.xml',
        'views/fel_document_type_views.xml',
        'views/fel_config_views.xml',
        'views/fel_dashboard_views.xml',
        'views/fel_document_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/pos_order_views.xml',
        'views/pos_config_views.xml',
        'views/fel_tax_phrase_views.xml',
        
        # Wizards
        'wizard/fel_nit_verification_wizard_views.xml',
        'wizard/fel_document_send_views.xml',
        
        # Menu (MUST be last)
        'menu/fel_menu.xml',
        
        # Reports
        'reports/fel_report_actions.xml',
        'reports/fel_invoice_report.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'fel_nit_gt_sat/static/src/js/fel_pos.js',
            'fel_nit_gt_sat/static/src/xml/fel_pos_templates.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    #'post_init_hook': 'post_init_hook', temporarily disabled for testing
}