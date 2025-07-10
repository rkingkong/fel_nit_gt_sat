# -*- coding: utf-8 -*-

from . import models
from . import wizard
from . import reports
from . import monkey_patches

from odoo import api, SUPERUSER_ID

def post_init_hook(cr, registry):
    """Post installation hook to setup default data"""
    # Create environment properly
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Create default INFILE provider if it doesn't exist
    provider_model = env['fel.certification.provider']
    existing_provider = provider_model.search([('code', '=', 'infile')], limit=1)
    
    if not existing_provider:
        provider_model.create({
            'name': 'INFILE, S.A.',
            'code': 'infile',
            'website': 'https://www.infile.com',
            'api_base_url': 'https://api.infile.com.gt',
            'contact_email': 'zherrera@infile.com.gt',
            'contact_phone': '2208-2208',
            'supports_nit_verification': True,
            'supports_xml_generation': True,
            'supports_digital_signature': True,
            # Add default pricing if your model has these fields
            'setup_cost': 995.00,
            'annual_cost': 396.00,
            'cost_per_dte': 0.33,
            'annual_dte_quota': 1200,
        })
    
    # Create default document types based on the INFILE proposal
    document_types = [
        {
            'name': 'Factura',
            'code': 'FACT',
            'is_invoice': True,
            'available_for_general': True,
            'available_for_pequeno': False,
            'available_for_especial': True,
            'sequence': 10,
        },
        {
            'name': 'Factura Cambiaria',
            'code': 'FCAM',
            'is_invoice': True,
            'available_for_general': True,
            'available_for_pequeno': False,
            'available_for_especial': True,
            'sequence': 20,
        },
        {
            'name': 'Factura Pequeño Contribuyente',
            'code': 'FPEQ',
            'is_invoice': True,
            'available_for_general': False,
            'available_for_pequeno': True,
            'available_for_especial': False,
            'sequence': 30,
        },
        {
            'name': 'Factura Cambiaria Pequeño Contribuyente',
            'code': 'FCAP',
            'is_invoice': True,
            'available_for_general': False,
            'available_for_pequeno': True,
            'available_for_especial': False,
            'sequence': 40,
        },
        {
            'name': 'Factura Especial',
            'code': 'FESP',
            'is_invoice': True,
            'available_for_general': False,
            'available_for_pequeno': False,
            'available_for_especial': True,
            'sequence': 50,
        },
        {
            'name': 'Nota de Abono',
            'code': 'NABN',
            'is_credit_note': True,
            'available_for_general': True,
            'available_for_pequeno': True,
            'available_for_especial': True,
            'sequence': 60,
        },
        {
            'name': 'Recibo por Donación',
            'code': 'RDON',
            'is_receipt': True,
            'available_for_general': True,
            'available_for_pequeno': True,
            'available_for_especial': True,
            'sequence': 70,
        },
        {
            'name': 'Recibo',
            'code': 'RECI',
            'is_receipt': True,
            'available_for_general': True,
            'available_for_pequeno': True,
            'available_for_especial': True,
            'sequence': 80,
        },
        {
            'name': 'Nota de Débito',
            'code': 'NDEB',
            'is_debit_note': True,
            'available_for_general': True,
            'available_for_pequeno': True,
            'available_for_especial': True,
            'sequence': 90,
        },
        {
            'name': 'Nota de Crédito',
            'code': 'NCRE',
            'is_credit_note': True,
            'available_for_general': True,
            'available_for_pequeno': True,
            'available_for_especial': True,
            'sequence': 100,
        },
    ]
    
    doc_type_model = env['fel.document.type']
    for doc_type_data in document_types:
        existing_type = doc_type_model.search([('code', '=', doc_type_data['code'])], limit=1)
        if not existing_type:
            doc_type_model.create(doc_type_data)
    
    # Create default tax phrases if your model has this
    if 'fel.tax.phrase' in env:
        tax_phrase_model = env['fel.tax.phrase']
        default_phrases = [
            {
                'code': 'ISR',
                'description': 'Sujeto a retención definitiva ISR',
                'active': True,
            },
            {
                'code': 'IVA_RET',
                'description': 'Agente de retención IVA',
                'active': True,
            },
            {
                'code': 'EXENTO',
                'description': 'Exento de IVA según Artículo 29',
                'active': True,
            },
        ]
        
        for phrase_data in default_phrases:
            existing_phrase = tax_phrase_model.search([('code', '=', phrase_data['code'])], limit=1)
            if not existing_phrase:
                tax_phrase_model.create(phrase_data)