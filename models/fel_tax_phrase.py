# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class FelTaxPhrase(models.Model):
    _name = 'fel.tax.phrase'
    _description = 'FEL Tax Phrase (Frases Tributarias)'
    _rec_name = 'display_name'
    _order = 'phrase_type, scenario_code'
    
    # Display name computed field
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    # Main fields
    name = fields.Text(
        string='Phrase Text',
        required=True,
        help='The actual tax phrase text to be included in FEL documents'
    )
    
    phrase_type = fields.Selection([
        ('1', 'ISR - Impuesto Sobre la Renta'),
        ('2', 'IVA General'),
        ('3', 'IVA Pequeño Contribuyente'),
        ('4', 'IVA Exento'),
        ('5', 'Factura Especial'),
        ('6', 'Pequeño Contribuyente'),
        ('7', 'Retenciones'),
        ('8', 'Otros'),
    ], string='Phrase Type', 
       required=True,
       help='SAT classification for tax phrases')
    
    scenario_code = fields.Selection([
        ('1', 'Escenario 1'),
        ('2', 'Escenario 2'),
        ('3', 'Escenario 3'),
        ('4', 'Escenario 4'),
        ('5', 'Escenario 5'),
        ('6', 'Escenario 6'),
        ('7', 'Escenario 7'),
        ('8', 'Escenario 8'),
        ('9', 'Escenario 9'),
        ('10', 'Escenario 10'),
    ], string='Scenario Code', 
       required=True,
       help='Specific scenario code within the phrase type')
    
    # SAT reference fields
    sat_phrase_id = fields.Char(
        string='SAT Phrase ID',
        help='Official SAT ID for this phrase (e.g., 134153)'
    )
    
    resolution_number = fields.Char(
        string='Resolution Number',
        help='SAT resolution number if applicable'
    )
    
    resolution_date = fields.Date(
        string='Resolution Date',
        help='Date of SAT resolution'
    )
    
    # Configuration
    description = fields.Text(
        string='Description',
        help='Detailed description of when to use this phrase'
    )
    
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Only active phrases can be used in documents'
    )
    
    is_default = fields.Boolean(
        string='Is Default',
        default=False,
        help='Default phrases are automatically included based on document type'
    )
    
    # Document type restrictions
    apply_to_fact = fields.Boolean(
        string='Apply to FACT',
        default=True,
        help='Use this phrase for standard invoices'
    )
    
    apply_to_fcam = fields.Boolean(
        string='Apply to FCAM',
        default=False,
        help='Use this phrase for exchange invoices'
    )
    
    apply_to_fpeq = fields.Boolean(
        string='Apply to FPEQ',
        default=False,
        help='Use this phrase for small taxpayer invoices'
    )
    
    apply_to_fcap = fields.Boolean(
        string='Apply to FCAP',
        default=False,
        help='Use this phrase for small taxpayer exchange invoices'
    )
    
    apply_to_fesp = fields.Boolean(
        string='Apply to FESP',
        default=False,
        help='Use this phrase for special invoices'
    )
    
    apply_to_ncre = fields.Boolean(
        string='Apply to NCRE',
        default=False,
        help='Use this phrase for credit notes'
    )
    
    apply_to_ndeb = fields.Boolean(
        string='Apply to NDEB',
        default=False,
        help='Use this phrase for debit notes'
    )
    
    apply_to_nabn = fields.Boolean(
        string='Apply to NABN',
        default=False,
        help='Use this phrase for payment notes'
    )
    
    # Relations
    document_phrase_ids = fields.One2many(
        'fel.document.phrase',
        'tax_phrase_id',
        string='Document Usage',
        help='Document types that use this phrase'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help='Company for multi-company scenarios'
    )
    
    # Conditions
    condition_type = fields.Selection([
        ('always', 'Always Include'),
        ('tax_regime', 'Based on Tax Regime'),
        ('amount', 'Based on Amount'),
        ('custom', 'Custom Condition'),
    ], string='Condition Type',
       default='always',
       help='When to include this phrase')
    
    condition_tax_regime = fields.Selection([
        ('general', 'General'),
        ('pequeno', 'Pequeño Contribuyente'),
        ('especial', 'Especial'),
    ], string='Tax Regime Condition',
       help='Include only for this tax regime')
    
    condition_amount_min = fields.Float(
        string='Minimum Amount',
        help='Include only if invoice amount is greater than this'
    )
    
    condition_custom = fields.Text(
        string='Custom Condition',
        help='Python expression to evaluate (advanced users only)'
    )
    
    @api.depends('name', 'phrase_type', 'scenario_code')
    def _compute_display_name(self):
        """Compute display name"""
        for record in self:
            type_name = dict(self._fields['phrase_type'].selection).get(record.phrase_type, '')
            record.display_name = f"[{record.phrase_type}-{record.scenario_code}] {type_name}"
            if len(record.name) > 50:
                record.display_name += f" - {record.name[:50]}..."
            else:
                record.display_name += f" - {record.name}"
    
    @api.constrains('phrase_type', 'scenario_code', 'company_id')
    def _check_unique_phrase(self):
        """Ensure unique combination of phrase type and scenario per company"""
        for record in self:
            domain = [
                ('phrase_type', '=', record.phrase_type),
                ('scenario_code', '=', record.scenario_code),
                ('company_id', '=', record.company_id.id),
                ('id', '!=', record.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(
                    _('A tax phrase with type %s and scenario %s already exists for this company.')
                    % (record.phrase_type, record.scenario_code)
                )
    
    def should_apply_to_document(self, document):
        """Check if this phrase should apply to a given document"""
        self.ensure_one()
        
        # Check document type
        doc_type = document.fel_document_type_id.code if hasattr(document, 'fel_document_type_id') else ''
        
        if doc_type:
            field_map = {
                'FACT': 'apply_to_fact',
                'FCAM': 'apply_to_fcam',
                'FPEQ': 'apply_to_fpeq',
                'FCAP': 'apply_to_fcap',
                'FESP': 'apply_to_fesp',
                'NCRE': 'apply_to_ncre',
                'NDEB': 'apply_to_ndeb',
                'NABN': 'apply_to_nabn',
            }
            
            field_name = field_map.get(doc_type)
            if field_name and not getattr(self, field_name, False):
                return False
        
        # Check condition type
        if self.condition_type == 'always':
            return True
        
        elif self.condition_type == 'tax_regime':
            if hasattr(document, 'partner_id') and document.partner_id:
                partner_regime = document.partner_id.tax_regime_gt or 'general'
                return partner_regime == self.condition_tax_regime
            return False
        
        elif self.condition_type == 'amount':
            if hasattr(document, 'amount_total'):
                return document.amount_total >= self.condition_amount_min
            return False
        
        elif self.condition_type == 'custom' and self.condition_custom:
            try:
                # Safe evaluation with limited context
                from odoo.tools import safe_eval
                safe_eval_dict = {
                    'document': document,
                    'partner': document.partner_id if hasattr(document, 'partner_id') else None,
                    'company': document.company_id if hasattr(document, 'company_id') else None,
                    'amount': document.amount_total if hasattr(document, 'amount_total') else 0,
                }
                return safe_eval(self.condition_custom, safe_eval_dict)
            except Exception as e:
                _logger.warning(f"Failed to evaluate phrase condition: {e}")
                return False
        
        return True
    
    @api.model
    def get_default_phrases(self):
        """Get all default phrases"""
        return self.search([
            ('is_active', '=', True),
            ('is_default', '=', True)
        ])
    
    @api.model
    def create_standard_phrases(self):
        """Create standard SAT phrases"""
        standard_phrases = [
            {
                'name': 'Sujeto a retención definitiva ISR',
                'phrase_type': '1',
                'scenario_code': '1',
                'sat_phrase_id': '134153',
                'description': 'Frase estándar para retención del ISR',
                'is_default': True,
                'apply_to_fact': True,
                'apply_to_fcam': True,
                'apply_to_fesp': True,
            },
            {
                'name': 'IVA Régimen General',
                'phrase_type': '2',
                'scenario_code': '1',
                'description': 'Frase para contribuyentes del régimen general',
                'condition_type': 'tax_regime',
                'condition_tax_regime': 'general',
                'apply_to_fact': True,
                'apply_to_fcam': True,
            },
            {
                'name': 'Pequeño Contribuyente',
                'phrase_type': '3',
                'scenario_code': '1',
                'description': 'Frase para pequeños contribuyentes',
                'condition_type': 'tax_regime',
                'condition_tax_regime': 'pequeno',
                'apply_to_fpeq': True,
                'apply_to_fcap': True,
            },
            {
                'name': 'Exento de IVA',
                'phrase_type': '4',
                'scenario_code': '1',
                'description': 'Frase para operaciones exentas de IVA',
                'apply_to_fact': True,
                'apply_to_fesp': True,
            },
            {
                'name': 'Sujeto a pagos trimestrales ISR',
                'phrase_type': '1',
                'scenario_code': '2',
                'description': 'Para contribuyentes con pagos trimestrales',
                'apply_to_fact': True,
                'apply_to_fcam': True,
            },
        ]
        
        for phrase_data in standard_phrases:
            if not self.search([
                ('phrase_type', '=', phrase_data['phrase_type']),
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
    def get_phrases_for_document(self, document_type_id, document=None):
        """Get all applicable tax phrases for a document"""
        phrases = self.search([
            ('document_type_id', '=', document_type_id),
            ('tax_phrase_id.is_active', '=', True)
        ], order='sequence')
        
        result = []
        for phrase_rel in phrases:
            # Check if phrase should apply
            if document and not phrase_rel.tax_phrase_id.should_apply_to_document(document):
                continue
            
            # Check additional condition if any
            if phrase_rel.condition and document:
                try:
                    from odoo.tools import safe_eval
                    safe_eval_dict = {
                        'document': document,
                        'partner': document.partner_id if hasattr(document, 'partner_id') else None,
                        'company': document.company_id if hasattr(document, 'company_id') else None,
                    }
                    if not safe_eval(phrase_rel.condition, safe_eval_dict):
                        continue
                except Exception as e:
                    _logger.warning(f"Failed to evaluate document phrase condition: {e}")
                    continue
            
            result.append({
                'type': phrase_rel.tax_phrase_id.phrase_type,
                'code': phrase_rel.tax_phrase_id.scenario_code,
                'text': phrase_rel.tax_phrase_id.name,
                'mandatory': phrase_rel.is_mandatory,
            })
        
        # Also add default phrases that aren't already included
        if document:
            default_phrases = phrase_rel.tax_phrase_id.get_default_phrases()
            for default_phrase in default_phrases:
                if default_phrase.should_apply_to_document(document):
                    # Check if not already included
                    exists = any(p['type'] == default_phrase.phrase_type and 
                               p['code'] == default_phrase.scenario_code 
                               for p in result)
                    if not exists:
                        result.append({
                            'type': default_phrase.phrase_type,
                            'code': default_phrase.scenario_code,
                            'text': default_phrase.name,
                            'mandatory': True,
                        })
        
        return result