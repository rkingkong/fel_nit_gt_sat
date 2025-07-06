# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class FelDocumentType(models.Model):
    _name = 'fel.document.type'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'FEL Document Type'
    _rec_name = 'name'
    _order = 'sequence, name'
    
    
    requires_reference_doc = fields.Boolean(
        string="Requires Reference Document",
        help="Indicates whether a reference document is required for this type (e.g., credit note, debit note)."
    )

    
    xml_template_name = fields.Char(
        string="XML Template Name",
        help="Technical name of the XML template to be used, e.g., 'fel_fact_template'"
    )

    active = fields.Boolean(
    string='Active',
    default=True,
    help='Indicates if this document type is active'
    )

    sat_code = fields.Char(
        string='SAT Code',
        help='Código interno del documento según SAT'
    )

    is_other = fields.Boolean(string="Other Document Type", default=False)
    usage_notes = fields.Text(string="Usage Notes", help="Add any specific notes about when and how to use this document type.")
    
    
    # Basic Information
    name = fields.Char(
        string='Document Name', 
        required=True,
        tracking=True,
        help='Full name of the document type (e.g., Factura, Nota de Crédito)'
    )
    
    code = fields.Char(
        string='SAT Code', 
        required=True,
        help='Official SAT code for this document type (e.g., FACT, NCRE, FPEQ)'
    )
    
    description = fields.Text(
        string='Description',
        help='Detailed description of when to use this document type'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of display in lists'
    )

    # Tax Phrase Relations
    document_phrase_ids = fields.One2many(
        'fel.document.phrase',
        'document_type_id',
        string='Tax Phrases',
        help='Tax phrases required for this document type'
    )
    
    def get_required_phrases(self):
        """Get all required tax phrases for this document type"""
        self.ensure_one()
        return self.document_phrase_ids.filtered(lambda p: p.is_mandatory and p.tax_phrase_id.is_active)
        
    # Document Type Classification
    is_invoice = fields.Boolean(
        string='Is Invoice',
        help='Check if this document type is an invoice'
    )
    
    is_credit_note = fields.Boolean(
        string='Is Credit Note',
        help='Check if this document type is a credit note'
    )
    
    is_debit_note = fields.Boolean(
        string='Is Debit Note',
        help='Check if this document type is a debit note'
    )
    
    is_receipt = fields.Boolean(
        string='Is Receipt',
        help='Check if this document type is a receipt'
    )
    
    is_donation_receipt = fields.Boolean(
        string='Is Donation Receipt',
        help='Check if this document type is for donations'
    )
    
    # Tax Regime Compatibility (from INFILE proposal)
    available_for_general = fields.Boolean(
        string='Available for General Regime',
        default=True,
        help='Can be used by companies in Régimen General'
    )
    
    available_for_pequeno = fields.Boolean(
        string='Available for Pequeño Contribuyente',
        default=True,
        help='Can be used by Pequeño Contribuyente companies'
    )
    
    available_for_especial = fields.Boolean(
        string='Available for Special Regime',
        default=True,
        help='Can be used by companies in Régimen Especial'
    )
    
    # Technical Configuration
    xml_template = fields.Text(
        string='XML Template',
        help='XML template for generating documents of this type'
    )
    
    requires_reference_document = fields.Boolean(
        string='Requires Reference Document',
        help='Check if this document type requires a reference to another document (e.g., credit notes)'
    )
    
    allows_negative_amounts = fields.Boolean(
        string='Allows Negative Amounts',
        help='Check if this document type can have negative line amounts'
    )
    
    # Status
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this document type is currently available for use'
    )
    
    # Related Models
    fel_document_ids = fields.One2many(
        'fel.document',
        'document_type_id',
        string='FEL Documents',
        help='Documents generated with this type'
    )
    
    # Computed Fields
    document_count = fields.Integer(
        string='Document Count',
        compute='_compute_document_count',
        help='Number of documents created with this type'
    )
    
    @api.depends('fel_document_ids')
    def _compute_document_count(self):
        """Compute the number of documents for each type"""
        for record in self:
            record.document_count = len(record.fel_document_ids)
    
    @api.model
    def get_document_type_by_code(self, code):
        """Get document type by SAT code"""
        return self.search([('code', '=', code), ('is_active', '=', True)], limit=1)
    
    @api.model
    def get_invoice_types(self):
        """Get all invoice document types"""
        return self.search([('is_invoice', '=', True), ('is_active', '=', True)])
    
    @api.model
    def get_credit_note_types(self):
        """Get all credit note document types"""
        return self.search([('is_credit_note', '=', True), ('is_active', '=', True)])
    
    @api.model
    def get_debit_note_types(self):
        """Get all debit note document types"""
        return self.search([('is_debit_note', '=', True), ('is_active', '=', True)])
    
    def get_available_for_regime(self, tax_regime):
        """Get document types available for a specific tax regime"""
        domain = [('is_active', '=', True)]
        
        if tax_regime == 'general':
            domain.append(('available_for_general', '=', True))
        elif tax_regime == 'pequeno':
            domain.append(('available_for_pequeno', '=', True))
        elif tax_regime == 'especial':
            domain.append(('available_for_especial', '=', True))
        
        return self.search(domain)
    
    def get_default_invoice_type_for_regime(self, tax_regime):
        """Get the default invoice type for a tax regime"""
        if tax_regime == 'pequeno':
            return self.get_document_type_by_code('FPEQ')
        elif tax_regime == 'especial':
            return self.get_document_type_by_code('FESP')
        else:
            return self.get_document_type_by_code('FACT')
    
    @api.constrains('code')
    def _check_unique_code(self):
        """Ensure document type codes are unique"""
        for record in self:
            if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('Document type code must be unique. Code "%s" already exists.') % record.code)
    
    @api.constrains('is_invoice', 'is_credit_note', 'is_debit_note', 'is_receipt')
    def _check_document_type_classification(self):
        """Ensure only one document type classification is selected"""
        for record in self:
            classifications = [
                record.is_invoice,
                record.is_credit_note, 
                record.is_debit_note,
                record.is_receipt
            ]
            
            if sum(classifications) != 1:
                raise ValidationError(_('Each document type must have exactly one classification (Invoice, Credit Note, Debit Note, or Receipt).'))
    
    def action_view_documents(self):
        """Action to view all documents of this type"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('FEL Documents - %s') % self.name,
            'res_model': 'fel.document',
            'view_mode': 'tree,form',
            'domain': [('document_type_id', '=', self.id)],
            'context': {'default_document_type_id': self.id},
        }
