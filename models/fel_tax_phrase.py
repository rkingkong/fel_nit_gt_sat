# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

class FelTaxPhrase(models.Model):
    _name = 'fel.tax.phrase'
    _description = 'FEL Tax Phrase'
    _order = 'sequence, id'
    
    # Basic Information
    
    active = fields.Boolean(
    string='Active',
    default=True,
    help='Indicates if this document type is active'
    )
    
    document_phrase_ids = fields.One2many(
        'fel.document.phrase', 'tax_phrase_id', string='Document Phrases'
    )
    
    name = fields.Char(
        string='Name',
        required=True,
        help='Name of the tax phrase'
    )
    
    code = fields.Char(
        string='Code',
        required=True,
        help='SAT code for this phrase'
    )
    
    phrase_type = fields.Char(
        string='Phrase Type',
        required=True,
        help='Type of phrase as defined by SAT'
    )
    
    scenario_code = fields.Char(
        string='Scenario Code',
        required=True,
        help='Scenario code as defined by SAT'
    )
    
    text = fields.Text(
        string='Phrase Text',
        help='Text content of the phrase (if applicable)'
    )
    
    description = fields.Text(
        string='Description',
        help='Description of when to use this phrase'
    )

    # ✅ Newly added fields to match the XML definitions
    apply_to_fact = fields.Boolean(
        string='Apply to FACT',
        default=False,
        help='Apply this phrase to FACTURA (FACT) documents'
    )
    
    apply_to_fcam = fields.Boolean(
        string='Apply to FCAM',
        default=False,
        help='Apply this phrase to Factura de Cambio (FCAM)'
    )
    
    apply_to_fesp = fields.Boolean(
        string='Apply to FESP',
        default=False,
        help='Apply this phrase to FESP (Factura Especial) documents'
    )
    
    apply_to_ncre = fields.Boolean(
    string='Apply to NCRE',
    default=False,
    help='Apply this phrase to Nota de Crédito (NCRE)'
    )

    apply_to_ndeb = fields.Boolean(
        string='Apply to NDEB',
        default=False,
        help='Apply this phrase to Nota de Débito (NDEB)'
    )

    apply_to_fpeq = fields.Boolean(
        string='Apply to FPEQ',
        default=False,
        help='Apply this phrase to Factura Pequeño Contribuyente (FPEQ)'
    )

    
    condition_type = fields.Selection(
    selection=[
        ('always', 'Always'),
        ('conditional', 'Conditional'),
        ('never', 'Never')
    ],
    string='Condition Type',
    default='always',
    help='Defines under what condition this phrase applies'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order in which phrases are displayed'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help='Company for this phrase'
    )
    
    _sql_constraints = [
        ('unique_code_company', 
         'UNIQUE(code, scenario_code, company_id)', 
         'Code and scenario must be unique per company!')
    ]
    
    @api.model
    def create_standard_phrases(self):
        """Create standard tax phrases for Guatemala"""
        phrases = [
            {
                'name': 'Sujeto a retención definitiva ISR',
                'code': '1',
                'phrase_type': '1',
                'scenario_code': '1',
                'description': 'Aplicable a facturas con retención definitiva de ISR',
                'apply_to_fact': True,
                'apply_to_fcam': True,
                'apply_to_fesp': True,
            },
            {
                'name': 'Exento de IVA',
                'code': '2',
                'phrase_type': '2',
                'scenario_code': '1',
                'description': 'Aplicable a facturas exentas de IVA',
            },
            {
                'name': 'Operación exenta según Artículo 7',
                'code': '3',
                'phrase_type': '3',
                'scenario_code': '1',
                'description': 'Para operaciones exentas según artículo 7 de la ley del IVA',
            },
            {
                'name': 'Agente de retención',
                'code': '4',
                'phrase_type': '4',
                'scenario_code': '1',
                'description': 'Cuando el emisor es agente de retención',
            },
        ]
        
        for phrase_data in phrases:
            if not self.search([
                ('code', '=', phrase_data['code']),
                ('scenario_code', '=', phrase_data['scenario_code']),
                ('company_id', '=', self.env.company.id)
            ]):
                phrase_data['company_id'] = self.env.company.id
                self.create(phrase_data)
        
        _logger.info("Standard FEL tax phrases created")


class FelDocumentPhrase(models.Model):
    _name = 'fel.document.phrase'
    _description = 'FEL Document Type - Tax Phrase Relation'
    _rec_name = 'tax_phrase_id'
    _order = 'sequence, id'
    
    document_type_id = fields.Many2one(
        'fel.document.type',
        string='Document Type',
        required=True,
        ondelete='cascade',
        help='FEL document type that uses this phrase'
    )
    
    tax_phrase_id = fields.Many2one(
        'fel.tax.phrase',
        string='Tax Phrase',
        required=True,
        ondelete='cascade',
        help='Tax phrase to include in this document type'
    )
    
    is_mandatory = fields.Boolean(
        string='Mandatory',
        default=True,
        help='Whether this phrase is mandatory for this document type'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order in which phrases appear in the document'
    )
    
    condition = fields.Text(
        string='Additional Condition',
        help='Additional Python expression to evaluate if phrase should be included'
    )
    
    _sql_constraints = [
        ('unique_doc_phrase', 
         'UNIQUE(document_type_id, tax_phrase_id)', 
         'This tax phrase is already assigned to this document type.')
    ]
    
    @api.model
    def get_phrases_for_document(self, document_type_id, source_doc=None):
        """Get applicable tax phrases for a document"""
        phrases = self.search([
            ('document_type_id', '=', document_type_id)
        ], order='sequence')
        
        result = []
        for phrase_rel in phrases:
            include = phrase_rel.is_mandatory
            
            if phrase_rel.condition and source_doc:
                try:
                    include = bool(eval(phrase_rel.condition, {
                        'doc': source_doc,
                        'self': phrase_rel,
                    }))
                except Exception as e:
                    _logger.warning(f"Error evaluating phrase condition: {e}")
                    include = phrase_rel.is_mandatory
            
            if include:
                result.append({
                    'type': phrase_rel.tax_phrase_id.phrase_type,
                    'code': phrase_rel.tax_phrase_id.scenario_code,
                    'text': phrase_rel.tax_phrase_id.text or '',
                })
        
        return result
