# -*- coding: utf-8 -*-
{
    'name': 'FEL Guatemala - Factura Electrónica en Línea',
    'version': '17.0.3.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Guatemala Electronic Invoice (FEL) Integration with SAT',
    'description': """
        Guatemala Electronic Invoice (FEL) Integration
        ==============================================
        
        This module provides:
        * NIT verification with SAT
        * Electronic invoice generation (FEL)
        * Integration with certified providers (INFILE, etc.)
        * Support for all Guatemala tax document types
        * Automatic XML generation and validation
        * Digital signature and transmission to SAT
        
        Supported Document Types:
        * FACT - Factura
        * FCAM - Factura Cambiaria  
        * FPEQ - Factura Pequeño Contribuyente
        * FCAP - Factura Cambiaria Pequeño Contribuyente
        * FESP - Factura Especial
        * NABN - Nota de Abono
        * RDON - Recibo por Donación
        * RECI - Recibo
        * NDEB - Nota de Débito
        * NCRE - Nota de Crédito
    """,
    'author': 'Kesiyos Restaurant Systems',
    'website': 'https://github.com/rkingkong/factura_electronica_gt',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',
        'sale',
        'purchase',
        'stock',
        'point_of_sale',
        'l10n_gt',  # Guatemala localization
    ],
    'data': [
        'security/fel_security.xml',
        'security/ir.model.access.csv',
        'data/fel_document_types.xml',
        'views/fel_dashboard_views.xml',
        'views/fel_config_views.xml',
        'views/fel_document_views.xml',
        'views/fel_tax_phrase_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/pos_order_views.xml',
        'views/pos_config_views.xml',
        'views/fel_certification_provider_views.xml',
        'views/fel_document_type_views.xml',
        'wizard/fel_nit_verification_views.xml',
        'wizard/fel_document_send_views.xml',
        'reports/fel_invoice_report.xml',
        'menu/fel_menu.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'fel_nit_gt_sat/static/src/js/fel_pos.js',
            'fel_nit_gt_sat/static/src/xml/fel_pos_templates.xml',
        ],
    },
    'external_dependencies': {
        'python': [
            'requests',
            'xmltodict',
            'lxml',
            'cryptography',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}