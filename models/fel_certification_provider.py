# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import requests
import json

_logger = logging.getLogger(__name__)

class FelCertificationProvider(models.Model):
    _name = 'fel.certification.provider'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'FEL Certification Provider'
    _rec_name = 'name'
    _order = 'sequence, name'
    
    # Standard Odoo fields
    active = fields.Boolean(
        string="Active",
        default=True,
        help="If unchecked, it will allow you to hide the provider without removing it.",
        tracking=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Sequence order for displaying providers'
    )
    
    # Basic Information
    name = fields.Char(
        string='Provider Name', 
        required=True,
        help='Name of the FEL certification provider',
        tracking=True
    )
    
    code = fields.Char(
        string='Provider Code', 
        required=True,
        help='Unique code for the provider (e.g., infile, guatefact)',
        tracking=True
    )
    
    description = fields.Text(
        string='Description',
        help='Detailed description of the provider and services'
    )
    
    website = fields.Char(
        string='Website',
        help='Provider website URL'
    )
    
    # Contact Information
    contact_name = fields.Char(
        string='Contact Name',
        help='Primary contact person'
    )
    
    contact_email = fields.Char(
        string='Contact Email',
        help='Primary contact email'
    )
    
    contact_phone = fields.Char(
        string='Contact Phone',
        help='Primary contact phone'
    )
    
    support_email = fields.Char(
        string='Support Email'
    )
    
    support_phone = fields.Char(
        string='Support Phone'
    )
    
    support_hours = fields.Char(
        string='Support Hours'
    )
    
    # API Configuration
    api_url = fields.Char(
        string='API URL',
        help='General API URL for the certification provider'
    )
    
    api_base_url = fields.Char(
        string='API Base URL',
        help='Base URL for the provider API'
    )
    
    test_api_url = fields.Char(
        string='Test API URL',
        help='Test environment API URL'
    )
    
    production_api_url = fields.Char(
        string='Production API URL',
        help='Production environment API URL'
    )
    
    api_version = fields.Char(
        string='API Version',
        default='1.0',
        help='API version supported'
    )
    
    environment = fields.Selection(
        selection=[
            ('test', 'Test'),
            ('production', 'Production')
        ],
        string='Environment',
        default='test',
        required=True
    )
    
    # Authentication
    username = fields.Char(
        string='Username'
    )
    
    password = fields.Char(
        string='Password'
    )
    
    api_token = fields.Char(
        string='API Token'
    )
    
    timeout = fields.Integer(
        string='Timeout (seconds)',
        default=30
    )
    
    # Certificate Configuration
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
        help='Whether this provider supports PDF generation'
    )
    
    # Pricing Information
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.ref('base.GTQ'),
        required=True
    )
    
    setup_cost = fields.Monetary(
        string='Setup Cost',
        currency_field='currency_id',
        help='One-time setup cost'
    )
    
    monthly_cost = fields.Monetary(
        string='Monthly Cost',
        currency_field='currency_id',
        help='Monthly subscription cost'
    )
    
    annual_cost = fields.Monetary(
        string='Annual Cost',
        currency_field='currency_id',
        help='Annual subscription cost'
    )
    
    cost_per_dte = fields.Monetary(
        string='Cost per DTE',
        currency_field='currency_id',
        help='Cost per electronic document'
    )
    
    annual_dte_limit = fields.Integer(
        string='Annual DTE Limit',
        help='Number of DTEs included in annual plan'
    )
    
    # Limits and Configuration
    daily_dte_limit = fields.Integer(
        string='Daily DTE Limit',
        help='Maximum number of DTEs allowed per day'
    )
    
    credit_days = fields.Integer(
        string='Credit Days',
        default=8,
        help='Number of credit days allowed before payment is due'
    )
    
    # Supported Document Types
    supported_document_types = fields.Many2many(
        'fel.document.type',
        'fel_cert_provider_doc_type_rel',
        'provider_id',
        'doc_type_id',
        string='Supported Document Types',
        help='List of DTE types supported by this provider'
    )
    
    # Additional Configuration
    additional_config = fields.Text(
        string='Additional Configuration',
        help='JSON-formatted configuration for advanced provider options'
    )
    
    @api.model
    def create(self, vals):
        """Override create to ensure unique codes"""
        if 'code' in vals:
            vals['code'] = vals['code'].lower().strip()
        return super().create(vals)
    
    def write(self, vals):
        """Override write to ensure unique codes"""
        if 'code' in vals:
            vals['code'] = vals['code'].lower().strip()
        return super().write(vals)
    
    @api.constrains('code')
    def _check_unique_code(self):
        """Ensure provider codes are unique"""
        for record in self:
            domain = [('code', '=', record.code), ('id', '!=', record.id)]
            if self.search_count(domain) > 0:
                raise ValidationError(
                    _('Provider code must be unique. Code "%s" already exists.') % record.code
                )
    
    @api.constrains('contact_email', 'support_email')
    def _check_email(self):
        """Validate email format"""
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        for record in self:
            if record.contact_email and not re.match(email_pattern, record.contact_email):
                raise ValidationError(_('Invalid format for contact email: %s') % record.contact_email)
            if record.support_email and not re.match(email_pattern, record.support_email):
                raise ValidationError(_('Invalid format for support email: %s') % record.support_email)
    
    def name_get(self):
        """Custom display name"""
        result = []
        for record in self:
            name = record.name
            if record.code:
                name = f'[{record.code.upper()}] {name}'
            result.append((record.id, name))
        return result
    
    @api.model
    def get_infile_provider(self):
        """Get or create INFILE provider with default configuration"""
        provider = self.search([('code', '=', 'infile')], limit=1)
        
        if not provider:
            provider = self.create({
                'name': 'INFILE, S.A.',
                'code': 'infile',
                'description': 'FEL Provider - INFILE GUATEMALA',
                'website': 'https://www.infile.com.gt',
                'api_base_url': 'https://api.infile.com.gt',
                'test_api_url': 'https://certificador.test.infile.com.gt',
                'production_api_url': 'https://certificador.feel.com.gt',
                'contact_name': 'Zayda Karina Sontay Herrera',
                'contact_email': 'zherrera@infile.com.gt',
                'contact_phone': '2208-2208 Ext 2426',
                'support_hours': 'Lunes a Viernes 8:00 - 17:00',
                'supports_nit_verification': True,
                'supports_xml_generation': True,
                'supports_digital_signature': True,
                'supports_pdf_generation': True,
                'setup_cost': 995.00,
                'monthly_cost': 0.00,
                'annual_cost': 396.00,
                'cost_per_dte': 0.33,
                'annual_dte_limit': 1200,
                'credit_days': 8,
                'active': True,
            })
        
        return provider
    
    @api.model
    def get_active_provider(self):
        """Get the first active provider"""
        return self.search([('active', '=', True)], limit=1)
    
    def test_connection(self):
        """Test connection to the provider"""
        self.ensure_one()
        
        if not self.api_base_url:
            raise ValidationError(_('API Base URL is required to test connection.'))
        
        try:
            # Determine which URL to use based on environment
            if self.environment == 'test' and self.test_api_url:
                test_url = self.test_api_url
            elif self.environment == 'production' and self.production_api_url:
                test_url = self.production_api_url
            else:
                test_url = self.api_base_url
            
            # Make a simple request to test connectivity
            response = requests.get(
                test_url,
                timeout=self.timeout or 30,
                verify=True  # Always verify SSL certificates
            )
            
            if response.status_code in [200, 401, 403]:
                # These status codes indicate the server is reachable
                message = _('Connection successful! Server is reachable.')
                self.message_post(body=message)
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'type': 'success',
                        'message': message,
                        'sticky': False,
                    }
                }
            else:
                raise ValidationError(
                    _('Connection failed. Server returned status code: %s') % response.status_code
                )
                
        except requests.exceptions.Timeout:
            raise ValidationError(_('Connection timeout. Please check the URL and try again.'))
        except requests.exceptions.ConnectionError:
            raise ValidationError(_('Cannot connect to server. Please check the URL and your internet connection.'))
        except Exception as e:
            raise ValidationError(_('Connection test failed: %s') % str(e))
    
    def action_view_configurations(self):
        """View related FEL configurations"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('FEL Configurations'),
            'res_model': 'fel.config',
            'view_mode': 'tree,form',
            'domain': [('provider_id', '=', self.id)],
            'context': {
                'default_provider_id': self.id,
            }
        }