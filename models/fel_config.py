# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import logging

_logger = logging.getLogger(__name__)

class FelConfig(models.Model):
    _name = 'fel.config'
    _description = 'FEL Configuration'
    _rec_name = 'company_id'
    
    # Company and Provider Information
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company for this FEL configuration'
    )
    
    provider_id = fields.Many2one(
        'fel.certification.provider',
        string='FEL Provider',
        required=True,
        help='FEL certification provider (e.g., INFILE, GUATEFACT, etc.)'
    )
    
    # Company Tax Information
    nit = fields.Char(
        string='Company NIT',
        required=True,
        help='Company NIT for FEL documents'
    )
    
    tax_regime = fields.Selection([
        ('general', 'Régimen General'),
        ('pequeno', 'Pequeño Contribuyente'),
        ('especial', 'Régimen Especial'),
    ], string='Tax Regime', 
       required=True,
       default='general',
       help='Company tax regime with SAT')
    
    commercial_name = fields.Char(
        string='Commercial Name',
        help='Commercial name for FEL documents (if different from company name)'
    )
    
    establishment_code = fields.Char(
        string='Establishment Code',
        default='1',
        help='SAT establishment code'
    )
    
    # Environment Configuration
    environment = fields.Selection([
        ('test', 'Test Environment'),
        ('production', 'Production Environment'),
    ], string='Environment',
       required=True,
       default='test',
       help='FEL environment to use')
    
    test_mode = fields.Boolean(
        string='Test Mode',
        default=True,
        help='Enable test mode for debugging'
    )
    
    # API Configuration
    api_url = fields.Char(
        string='API URL',
        help='FEL provider API URL'
    )
    
    api_username = fields.Char(
        string='API Username',
        help='Username for FEL provider API'
    )
    
    api_password = fields.Char(
        string='API Password',
        help='Password for FEL provider API'
    )
    
    api_token = fields.Char(
        string='API Token',
        help='Authentication token for FEL provider API'
    )
    
    api_key = fields.Char(
        string='API Key',
        help='API key for FEL provider'
    )
    
    # Digital Certificate (optional)
    certificate_file = fields.Binary(
        string='Certificate File',
        help='Digital certificate file for signing (optional)'
    )
    
    certificate_filename = fields.Char(
        string='Certificate Filename'
    )
    
    certificate_password = fields.Char(
        string='Certificate Password',
        help='Password for the digital certificate'
    )
    
    # Address Information
    address_line = fields.Char(
        string='Address',
        help='Company address for FEL documents'
    )
    
    postal_code = fields.Char(
        string='Postal Code',
        default='01001',
        help='Postal code for FEL documents'
    )
    
    municipality = fields.Char(
        string='Municipality',
        default='Guatemala',
        help='Municipality for FEL documents'
    )
    
    department = fields.Char(
        string='Department',
        default='Guatemala',
        help='Department for FEL documents'
    )
    
    country_code = fields.Char(
        string='Country Code',
        default='GT',
        help='Country code for FEL documents'
    )
    
    # Usage Limits and Tracking
    annual_dte_limit = fields.Integer(
        string='Annual DTE Limit',
        default=1200,
        help='Maximum DTEs per year (based on provider plan)'
    )
    
    monthly_dte_limit = fields.Integer(
        string='Monthly DTE Limit',
        default=100,
        help='Maximum DTEs per month'
    )
    
    annual_dte_count = fields.Integer(
        string='Annual DTE Count',
        default=0,
        readonly=True,
        help='DTEs used this year'
    )
    
    monthly_dte_count = fields.Integer(
        string='Monthly DTE Count',
        default=0,
        readonly=True,
        help='DTEs used this month'
    )
    
    dte_usage_percentage = fields.Float(
        string='DTE Usage Percentage',
        compute='_compute_dte_usage_percentage',
        help='Percentage of annual DTEs used'
    )
    
    # Auto-send Configuration
    auto_send_invoices = fields.Boolean(
        string='Auto-send Invoices',
        default=False,
        help='Automatically send invoices to FEL when posted'
    )
    
    auto_send_credit_notes = fields.Boolean(
        string='Auto-send Credit Notes',
        default=False,
        help='Automatically send credit notes to FEL when posted'
    )
    
    auto_send_pos_orders = fields.Boolean(
        string='Auto-send POS Orders',
        default=False,
        help='Automatically send POS orders to FEL when completed'
    )
    
    # Status and Control
    is_active = fields.Boolean(
        string='Active',
        default=False,
        help='Whether this configuration is currently active'
    )
    
    last_sync = fields.Datetime(
        string='Last Sync',
        readonly=True,
        help='Last time this configuration was synchronized with the provider'
    )
    
    # Computed fields
    @api.depends('annual_dte_count', 'annual_dte_limit')
    def _compute_dte_usage_percentage(self):
        """Compute percentage of DTEs used"""
        for config in self:
            if config.annual_dte_limit > 0:
                config.dte_usage_percentage = (config.annual_dte_count / config.annual_dte_limit) * 100
            else:
                config.dte_usage_percentage = 0
    
    @api.model
    def get_active_config(self, company_id=None):
        """Get the active FEL configuration for a company"""
        if not company_id:
            company_id = self.env.company.id
        
        config = self.search([
            ('company_id', '=', company_id),
            ('is_active', '=', True)
        ], limit=1)
        
        if not config:
            raise ValidationError(_('No active FEL configuration found for company. Please configure FEL first.'))
        
        return config
    
    def test_connection(self):
        """Test connection to FEL provider"""
        self.ensure_one()
        
        if not self.api_url:
            raise ValidationError(_('API URL is required to test connection.'))
        
        try:
            # Test basic connectivity
            response = requests.get(self.api_url, timeout=10)
            
            if response.status_code == 200:
                self.last_sync = fields.Datetime.now()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Successfully connected to FEL provider.'),
                        'type': 'success',
                    }
                }
            else:
                raise ValidationError(_('Connection failed with status code: %s') % response.status_code)
                
        except requests.exceptions.Timeout:
            raise ValidationError(_('Connection timeout. Please check the API URL and your internet connection.'))
        except requests.exceptions.ConnectionError:
            raise ValidationError(_('Connection error. Please check the API URL and try again.'))
        except Exception as e:
            raise ValidationError(_('Connection test failed: %s') % str(e))
    
    def increment_dte_count(self):
        """Increment DTE counters"""
        self.ensure_one()
        
        # Reset monthly count if it's a new month
        current_month = fields.Date.today().month
        if hasattr(self, '_last_month') and self._last_month != current_month:
            self.monthly_dte_count = 0
        
        self.annual_dte_count += 1
        self.monthly_dte_count += 1
        self._last_month = current_month
    
    def reset_annual_counters(self):
        """Reset annual counters (to be called yearly)"""
        self.ensure_one()
        self.annual_dte_count = 0
    
    def reset_monthly_counters(self):
        """Reset monthly counters (to be called monthly)"""
        self.ensure_one()
        self.monthly_dte_count = 0
    
    @api.constrains('is_active')
    def _check_unique_active_config(self):
        """Ensure only one active configuration per company"""
        for config in self:
            if config.is_active:
                other_active = self.search([
                    ('company_id', '=', config.company_id.id),
                    ('is_active', '=', True),
                    ('id', '!=', config.id)
                ])
                if other_active:
                    raise ValidationError(_('Only one FEL configuration can be active per company.'))
    
    @api.constrains('nit')
    def _check_nit_format(self):
        """Validate NIT format"""
        for config in self:
            if config.nit:
                # Remove non-digits
                import re
                clean_nit = re.sub(r'\D', '', config.nit)
                if len(clean_nit) < 8 or len(clean_nit) > 9:
                    raise ValidationError(_('Company NIT must have 8 or 9 digits.'))
    
    def action_view_documents(self):
        """View FEL documents for this configuration"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('FEL Documents'),
            'res_model': 'fel.document',
            'view_mode': 'tree,form',
            'domain': [('company_id', '=', self.company_id.id)],
            'context': {'default_company_id': self.company_id.id},
        }
    
    def action_view_monthly_stats(self):
        """View monthly statistics"""
        self.ensure_one()
        # This would show monthly usage statistics
        # For now, just show a notification with current stats
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Monthly Statistics'),
                'message': _('Monthly DTEs used: %s / %s (%.1f%%)') % (
                    self.monthly_dte_count, 
                    self.monthly_dte_limit,
                    (self.monthly_dte_count / self.monthly_dte_limit * 100) if self.monthly_dte_limit > 0 else 0
                ),
                'type': 'info',
            }
        }
