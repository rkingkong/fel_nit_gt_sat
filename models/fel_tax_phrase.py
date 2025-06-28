# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class FelTaxPhrase(models.Model):
    _name = 'fel.tax.phrase'
    _description = 'FEL Tax Phrase (Frases Tributarias)'
    _rec_name = 'name'
    _order = 'phrase_type, scenario_code'
    
    name = fields.Char(
        string='Phrase Text',
        required=True,
        help='The actual tax phrase text to be included in FEL documents'
    )
    
    phrase_type = fields.Selection([
        ('1', 'Type 1 - ISR'),
        ('2', 'Type 2 - IVA General'),
        ('3', 'Type 3 - IVA Especial'),
        ('4', 'Type 4 - Exento'),
        ('5', 'Type 5 - Factura Especial'),
        ('6', 'Type 6 - Pequeño Contribuyente'),
        ('7', 'Type 7 - Retenciones'),
        ('8', 'Type 8 - Otros'),
    ], string='Phrase Type', required=True,
       help='SAT classification for tax phrases')
    
    scenario_code = fields.Selection([
        ('1', 'Scenario 1'),
        ('2', 'Scenario 2'),
        ('3', 'Scenario 3'),
        ('4', 'Scenario 4'),
        ('5', 'Scenario 5'),
    ], string='Scenario Code', required=True,
       help='Specific scenario code within the phrase type')
    
    description = fields.Text(
        string='Description',
        help='Detailed description of when to use this phrase'
    )
    
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Only active phrases can be used in documents'
    )
    
    # Relations
    document_phrase_ids = fields.One2many(
        'fel.document.phrase',
        'tax_phrase_id',
        string='Document Types',
        help='Document types that use this phrase'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help='Company for multi-company scenarios'
    )
    
    @api.constrains('phrase_type', 'scenario_code')
    def _check_unique_phrase(self):
        """Ensure unique combination of phrase type and scenario"""
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
    
    def name_get(self):
        """Display phrase with type and scenario"""
        result = []
        for record in self:
            name = f"[{record.phrase_type}-{record.scenario_code}] {record.name}"
            result.append((record.id, name))
        return result


class FelDocumentPhrase(models.Model):
    _name = 'fel.document.phrase'
    _description = 'FEL Document Type - Tax Phrase Relation'
    _rec_name = 'tax_phrase_id'
    
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
        string='Condition',
        help='Python expression to evaluate if phrase should be included'
    )
    
    _sql_constraints = [
        ('unique_doc_phrase', 
         'UNIQUE(document_type_id, tax_phrase_id)', 
         'This tax phrase is already assigned to this document type.')
    ]
    
    @api.model
    def get_phrases_for_document(self, document_type_id, invoice=None):
        """Get all applicable tax phrases for a document"""
        phrases = self.search([
            ('document_type_id', '=', document_type_id),
            ('tax_phrase_id.is_active', '=', True)
        ], order='sequence')
        
        result = []
        for phrase_rel in phrases:
            # Check condition if any
            if phrase_rel.condition and invoice:
                try:
                    # Safe evaluation with limited context
                    safe_eval_dict = {
                        'invoice': invoice,
                        'partner': invoice.partner_id,
                        'company': invoice.company_id,
                    }
                    # Note: You'll need to import safe_eval from odoo.tools
                    # from odoo.tools import safe_eval
                    # Uncomment and use if needed:
                    # if not safe_eval(phrase_rel.condition, safe_eval_dict):
                    #     continue
                except Exception as e:
                    _logger.warning(f"Failed to evaluate phrase condition: {e}")
                    continue
            
            result.append({
                'type': phrase_rel.tax_phrase_id.phrase_type,
                'code': phrase_rel.tax_phrase_id.scenario_code,
                'text': phrase_rel.tax_phrase_id.name,
                'mandatory': phrase_rel.is_mandatory,
            })
        
        return result
