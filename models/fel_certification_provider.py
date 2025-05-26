# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class FelCertificationProvider(models.Model):
    _name = 'fel.certification.provider'
    _description = 'FEL Certification Provider'
    _rec_name = 'name'
    
    name = fields.Char(
        string='Provider Name', 
        required=True,
        help='Name of the FEL certification provider'
    )
    
    code = fields.Char(
        string='Provider Code', 
        required=True,
        help='Unique code for the provider (e.g., infile, guatefact, etc.)'
    )
    
    website = fields.Char(
        string='Website',
        help='Provider website URL'
    )
    
    # API Configuration
    api_base_url = fields.Char(
        string='API Base URL',
        help='Base URL for the provider API'
    )
    
    api_version = fields.Char(
        string='API Version',
        default='1.0',
        help='API version supported'
    )
    
    # Supported Features
    supports_nit_verification = fields.Boolean(
        string='Supports NIT Verification', 
        default=True,
        help='Whether this provider supports NIT verification with SAT'
    )
    
    supports_xml_generation = fields.Boolean(
        string='Supports XML Generation', 
        default=True,
        help='Whether this provider supports XML generation'
    )
    
    supports_digital_signature = fields.Boolean(
        string='Supports Digital Signature', 
        default=True,
        help='Whether this provider supports digital signature'
    )
    
    supports_pdf_generation = fields.Boolean(
        string='Supports PDF Generation',
        default=True,
        help='Whether this provider can generate PDF documents'
    )
    
    # Contact Information
    contact_name = fields.Char(
        string='Contact Name',
        help='Main contact person at the provider'
    )
    
    contact_email = fields.Char(
        string='Contact Email',
        help='Contact email for support'
    )
    
    contact_phone = fields.Char(
        string='Contact Phone',
        help='Contact phone number'
    )
    
    # Status
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this provider is currently active'
    )
    
    # Pricing Information (from INFILE proposal)
    setup_cost = fields.Float(
        string='Setup Cost',
        help='One-time setup cost in GTQ'
    )
    
    cost_per_dte = fields.Float(
        string='Cost per DTE',
        help='Cost per document in GTQ'
    )
    
    annual_dte_limit = fields.Integer(
        string='Annual DTE Limit',
        help='Maximum DTEs per year included in base price'
    )
    
    annual_cost = fields.Float(
        string='Annual Cost',
        help='Annual cost in GTQ'
    )
    
    # Technical Configuration
    test_api_url = fields.Char(
        string='Test API URL',
        help='URL for testing environment'
    )
    
    production_api_url = fields.Char(
        string='Production API URL',
        help='URL for production environment'
    )
    
    @api.model
    def get_infile_provider(self):
        """Get or create INFILE provider based on the proposal document"""
        provider = self.search([('code', '=', 'infile')], limit=1)
        if not provider:
            provider = self.create({
                'name': 'INFILE, S.A.',
                'code': 'infile',
                'website': 'https://www.infile.com',
                'api_base_url': 'https://api.infile.com.gt',
                'contact_name': 'Zayda Karina Sontay Herrera',
                'contact_email': 'zherrera@infile.com.gt',
                'contact_phone': '2208-2208 Ext 2426',
                'supports_nit_verification': True,
                'supports_xml_generation': True,
                'supports_digital_signature': True,
                'supports_pdf_generation': True,
                # Pricing from proposal
                'setup_cost': 995.00,
                'cost_per_dte': 0.33,
                'annual_dte_limit': 1200,
                'annual_cost': 396.00,
                'is_active': True,
            })
        return provider
    
    @api.model
    def get_active_provider(self):
        """Get the first active provider"""
        return self.search([('is_active', '=', True)], limit=1)
    
    def test_connection(self):
        """Test connection to the provider"""
        self.ensure_one()
        # This will be implemented based on each provider's API
        return True
    
    @api.constrains('code')
    def _check_unique_code(self):
        """Ensure provider codes are unique"""
        for record in self:
            if self.search_count([('code', '=', record.code), ('id', '!=', record.id)]) > 0:
                raise ValidationError(_('Provider code must be unique. Code "%s" already exists.') % record.code)
