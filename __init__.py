# -*- coding: utf-8 -*-

from . import models
from . import wizard

def post_init_hook(cr, registry):
    """Post installation hook to setup default data"""
    # Import here to avoid circular imports
    env = registry['ir.environment'].with_context(active_test=False)
    
    # Create default INFILE provider if it doesn't exist
    provider_model = env['fel.certification.provider']
    if not provider_model.search([('code', '=', 'infile')]):
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
        })
    
    # Create default document types based on the INFILE proposal
    document_types = [
        {'name': 'Factura', 'code': 'FACT', 'is_invoice': True, 'available_for_general': True, 'available_for_pequeno': False, 'available_for_especial': True},
        {'name': 'Factura Cambiaria', 'code': 'FCAM', 'is_invoice': True, 'available_for_general': True, 'available_for_pequeno': False, 'available_for_especial': True},
        {'name': 'Factura Pequeño Contribuyente', 'code': 'FPEQ', 'is_invoice': True, 'available_for_general': False, 'available_for_pequeno': True, 'available_for_especial': False},
        {'name': 'Factura Cambiaria Pequeño Contribuyente', 'code': 'FCAP', 'is_invoice': True, 'available_for_general': False, 'available_for_pequeno': True, 'available_for_especial': False},
        {'name': 'Factura Especial', 'code': 'FESP', 'is_invoice': True, 'available_for_general': False, 'available_for_pequeno': False, 'available_for_especial': True},
        {'name': 'Nota de Abono', 'code': 'NABN', 'is_credit_note': True, 'available_for_general': True, 'available_for_pequeno': True, 'available_for_especial': True},
        {'name': 'Recibo por Donación', 'code': 'RDON', 'is_receipt': True, 'available_for_general': True, 'available_for_pequeno': True, 'available_for_especial': True},
        {'name': 'Recibo', 'code': 'RECI', 'is_receipt': True, 'available_for_general': True, 'available_for_pequeno': True, 'available_for_especial': True},
        {'name': 'Nota de Débito', 'code': 'NDEB', 'is_debit_note': True, 'available_for_general': True, 'available_for_pequeno': True, 'available_for_especial': True},
        {'name': 'Nota de Crédito', 'code': 'NCRE', 'is_credit_note': True, 'available_for_general': True, 'available_for_pequeno': True, 'available_for_especial': True},
    ]
    
    doc_type_model = env['fel.document.type']
    for doc_type_data in document_types:
        if not doc_type_model.search([('code', '=', doc_type_data['code'])]):
            doc_type_model.create(doc_type_data)
