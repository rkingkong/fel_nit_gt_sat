from . import models
from . import wizard

def post_init_hook(cr, registry):
    """Post installation hook"""
    # Create default FEL document types
    env = registry['ir.environment']['res.users'].browse(cr, 1).env
    
    # Create INFILE provider
    provider = env['fel.certification.provider'].get_infile_provider()
    
    # Create default document types
    document_types = [
        {'name': 'Factura', 'code': 'FACT', 'is_invoice': True},
        {'name': 'Factura Cambiaria', 'code': 'FCAM', 'is_invoice': True},
        {'name': 'Factura Pequeño Contribuyente', 'code': 'FPEQ', 'is_invoice': True},
        {'name': 'Factura Cambiaria Pequeño Contribuyente', 'code': 'FCAP', 'is_invoice': True},
        {'name': 'Factura Especial', 'code': 'FESP', 'is_invoice': True},
        {'name': 'Nota de Abono', 'code': 'NABN'},
        {'name': 'Recibo por Donación', 'code': 'RDON', 'is_receipt': True},
        {'name': 'Recibo', 'code': 'RECI', 'is_receipt': True},
        {'name': 'Nota de Débito', 'code': 'NDEB', 'is_debit_note': True},
        {'name': 'Nota de Crédito', 'code': 'NCRE', 'is_credit_note': True},
    ]
    
    for doc_type_data in document_types:
        existing = env['fel.document.type'].search([('code', '=', doc_type_data['code'])])
        if not existing:
            env['fel.document.type'].create(doc_type_data)
