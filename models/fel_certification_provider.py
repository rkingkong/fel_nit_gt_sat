# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class FelCertificationProvider(models.Model):
    _name = 'fel.certification.provider'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Add this line
    _description = 'FEL Certification Provider'
    _rec_name = 'name'
    _order = 'sequence, name'
    
    api_url = fields.Char(
    string='API URL',
    help='General API URL for the certification provider'
    )

    environment = fields.Selection(
    selection=[('test', 'Test'), ('production', 'Production')],
    string='Environment',
    default='test',
    required=True
    )

    username = fields.Char(string='Username')
    password = fields.Char(string='Password')
    api_token = fields.Char(string='API Token')
    timeout = fields.Integer(string='Timeout')
    website = fields.Char(string='Website')
    support_email = fields.Char(string='Support Email')
    support_phone = fields.Char(string='Support Phone')
    support_hours = fields.Char(string='Support Hours')
    
    daily_dte_limit = fields.Integer(
        string='Daily DTE Limit',
        help='Maximum number of DTEs allowed per day'
    )

    credit_days = fields.Integer(
        string='Credit Days',
        help='Number of credit days allowed before payment is due'
    )

    supported_document_types = fields.Many2many(
        'fel.document.type',
        'fel_cert_provider_doc_type_rel',
        'provider_id',
        'doc_type_id',
        string='Supported Document Types',
        help='List of DTE types supported by this provider'
    )

    certificate_file = fields.Binary(
        string='Certificate File',
        attachment=True,
        help='Upload the .pfx or .pem certificate file'
    )

    certificate_filename = fields.Char(
        string='Certificate Filename',
        help='Stores the name of the uploaded certificate file'
    )

    certificate_password = fields.Char(
        string='Certificate Password',
        help='Password to decrypt the certificate file'
    )

    additional_config = fields.Text(
        string='Additional Configuration',
        help='JSON-formatted configuration for advanced provider options'
    )


    #check for active provider
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Indicates if this provider is currently active.",
        tracking=True  # Add tracking for audit trail
    )

    # Basic Information
    name = fields.Char(
        string='Provider Name', 
        required=True,
        help='Name of the FEL certification provider',
        tracking=True  # Add tracking
    )
    
    code = fields.Char(
        string='Provider Code', 
        required=True,
        help='Unique code for the provider (e.g., infile, guatefact, etc.)',
        tracking=True  # Add tracking
    )
    
    description = fields.Text(
        string='Description',
        help='Detailed description of the provider and services'
    )
    
    website = fields.Char(
        string='Website',
        help='Provider website URL'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Sequence order for displaying providers'
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
    
    support_hours = fields.Char(
        string='Support Hours',
        help='Support hours (e.g., Lunes a Viernes 8:00 - 17:00)'
    )
    
    # Status
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Whether this provider is currently active',
        tracking=True  # Add tracking
    )
    
    # Pricing Information (from INFILE proposal)
    setup_cost = fields.Float(
        string='Setup Cost',
        help='One-time setup cost in GTQ'
    )
    
    monthly_cost = fields.Float(
        string='Monthly Cost',
        help='Monthly cost in GTQ (if applicable)'
    )
    
    annual_cost = fields.Float(
        string='Annual Cost',
        help='Annual cost in GTQ'
    )
    
    cost_per_dte = fields.Float(
        string='Cost per DTE',
        help='Cost per document in GTQ'
    )
    
    annual_dte_limit = fields.Integer(
        string='Annual DTE Limit',
        help='Maximum DTEs per year included in base price'
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
    
    # Company and Currency
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True,
        help='Currency used for pricing'
    )
    
    # Notes
    notes = fields.Text(
        string='Notes',
        help='Additional notes or information about this provider'
    )
    
    @api.model
    def get_infile_provider(self):
        """Get or create INFILE provider based on the proposal document"""
        provider = self.search([('code', '=', 'infile')], limit=1)
        if not provider:
            provider = self.create({
                'name': 'INFILE, S.A.',
                'code': 'infile',
                'description': 'FEL Provider - INFILE GUATEMALA',
                'website': 'https://www.infile.com.gt',
                'api_base_url': 'https://api.infile.com.gt',
                'contact_name': 'Zayda Karina Sontay Herrera',
                'contact_email': 'zherrera@infile.com.gt',
                'contact_phone': '2208-2208 Ext 2426',
                'support_hours': 'Lunes a Viernes 8:00 - 17:00',
                'supports_nit_verification': True,
                'supports_xml_generation': True,
                'supports_digital_signature': True,
                'supports_pdf_generation': True,
                # Pricing from proposal
                'setup_cost': 995.00,
                'monthly_cost': 0.00,
                'annual_cost': 396.00,
                'cost_per_dte': 0.33,
                'annual_dte_limit': 1200,
                # API URLs
                'test_api_url': 'https://certificador.test.infile.com.gt',
                'production_api_url': 'https://certificador.feel.com.gt',
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
    
    @api.constrains('contact_email')
    def _check_email(self):
        """Validate email format"""
        for record in self:
            if record.contact_email:
                import re
                if not re.match(r"[^@]+@[^@]+\.[^@]+", record.contact_email):
                    raise ValidationError(_('Invalid email format for contact email.'))
    
    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            name = record.name
            if record.code:
                name = f'[{record.code.upper()}] {name}'
            result.append((record.id, name))
        return result