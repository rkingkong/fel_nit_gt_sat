# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import logging
from datetime import datetime, timedelta
import json

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
    
    # INFILE Specific Authentication Fields
    usuario_firma = fields.Char(
        string='Usuario Firma',
        help='INFILE user for digital signature (prefix)'
    )
    
    llave_firma = fields.Char(
        string='Llave Firma',
        help='INFILE signature key (token signer)'
    )
    
    usuario_api = fields.Char(
        string='Usuario API',
        help='INFILE API user (usually same as Usuario Firma)'
    )
    
    llave_api = fields.Char(
        string='Llave API',
        help='INFILE API key'
    )
    
    llave_firma_expiry = fields.Date(
        string='Llave Firma Expiry Date',
        help='Expiration date for the signature key (approx 2 years from SAT download)'
    )
    
    # Establishment Information
    establishment_name = fields.Char(
        string='Establishment Name',
        help='Name of the establishment (e.g., FUSIÓN GATRONÓMICA)'
    )
    
    establishment_code = fields.Char(
        string='Establishment Code',
        default='1',
        required=True,
        help='SAT establishment code'
    )
    
    establishment_classification = fields.Char(
        string='Establishment Classification',
        help='SAT classification code (e.g., 885 for restaurants)'
    )
    
    establishment_type = fields.Char(
        string='Establishment Type',
        help='SAT establishment type (e.g., 888)'
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
    
    # API Configuration (Base URLs)
    api_url = fields.Char(
        string='API URL',
        compute='_compute_api_urls',
        help='FEL provider API URL'
    )
    
    certification_url = fields.Char(
        string='Certification URL',
        default='https://certificador.feel.com.gt/fel/procesounificado/transaccion/v2/xml',
        help='INFILE certification endpoint'
    )
    
    nit_verification_url = fields.Char(
        string='NIT Verification URL',
        default='https://consultareceptores.feel.com.gt/rest/action',
        help='INFILE NIT verification endpoint'
    )
    
    cui_verification_url = fields.Char(
        string='CUI Verification URL',
        default='https://certificador.feel.com.gt/api/v2/servicios/externos/cui',
        help='INFILE CUI verification endpoint'
    )
    
    cui_login_url = fields.Char(
        string='CUI Login URL',
        default='https://certificador.feel.com.gt/api/v2/servicios/externos/login',
        help='INFILE CUI authentication endpoint'
    )
    
    # Document Numbering
    use_provider_numbering = fields.Boolean(
        string='Use Provider Numbering',
        default=True,
        help='Use automatic numbering from INFILE (recommended)'
    )
    
    last_internal_number = fields.Integer(
        string='Last Internal Number',
        default=0,
        help='Last number used for internal numbering (if not using provider numbering)'
    )
    
    # Daily Limit Control
    daily_limit = fields.Integer(
        string='Daily API Limit',
        default=2000,
        help='Maximum API calls per day (2000 in implementation mode)'
    )
    
    daily_counter = fields.Integer(
        string='Daily Counter',
        default=0,
        readonly=True,
        help='Number of API calls made today'
    )
    
    last_counter_reset = fields.Date(
        string='Last Counter Reset',
        default=fields.Date.today,
        readonly=True,
        help='Date when the daily counter was last reset'
    )
    
    daily_errors = fields.Integer(
        string='Daily Errors',
        default=0,
        readonly=True,
        help='Number of errors today'
    )
    
    # Retry Configuration
    max_retry_attempts = fields.Integer(
        string='Max Retry Attempts',
        default=3,
        help='Maximum number of retry attempts for failed transactions'
    )
    
    retry_delay_seconds = fields.Integer(
        string='Retry Delay (seconds)',
        default=30,
        help='Seconds to wait between retry attempts'
    )
    
    retry_on_timeout = fields.Boolean(
        string='Retry on Timeout',
        default=True,
        help='Automatically retry when request times out'
    )
    
    retry_on_connection_error = fields.Boolean(
        string='Retry on Connection Error',
        default=True,
        help='Automatically retry on connection errors'
    )
    
    # Error Tracking
    last_error_date = fields.Datetime(
        string='Last Error Date',
        readonly=True,
        help='Date of the last error'
    )
    
    last_error_message = fields.Text(
        string='Last Error Message',
        readonly=True,
        help='Last error message received'
    )
    
    consecutive_errors = fields.Integer(
        string='Consecutive Errors',
        default=0,
        readonly=True,
        help='Number of consecutive errors (reset on success)'
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
        default=True,
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
    
    last_successful_transaction = fields.Datetime(
        string='Last Successful Transaction',
        readonly=True,
        help='Date of the last successful FEL transaction'
    )
    
    # Monitoring
    health_status = fields.Selection([
        ('healthy', 'Healthy'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('critical', 'Critical'),
    ], string='Health Status',
       compute='_compute_health_status',
       help='Overall health status of FEL integration')
    
    health_message = fields.Text(
        string='Health Message',
        compute='_compute_health_status',
        help='Detailed health status message'
    )
    
    @api.depends('provider_id')
    def _compute_api_urls(self):
        """Compute API URLs based on provider"""
        for config in self:
            if config.provider_id and config.provider_id.code == 'infile':
                config.api_url = 'https://certificador.feel.com.gt'
            else:
                config.api_url = config.provider_id.api_base_url if config.provider_id else ''
    
    @api.depends('annual_dte_count', 'annual_dte_limit')
    def _compute_dte_usage_percentage(self):
        """Compute percentage of DTEs used"""
        for config in self:
            if config.annual_dte_limit > 0:
                config.dte_usage_percentage = (config.annual_dte_count / config.annual_dte_limit) * 100
            else:
                config.dte_usage_percentage = 0
    
    @api.depends('consecutive_errors', 'daily_errors', 'dte_usage_percentage', 'llave_firma_expiry')
    def _compute_health_status(self):
        """Compute overall health status"""
        for config in self:
            health_issues = []
            
            # Check consecutive errors
            if config.consecutive_errors >= 10:
                config.health_status = 'critical'
                health_issues.append(_('Critical: %d consecutive errors') % config.consecutive_errors)
            elif config.consecutive_errors >= 5:
                config.health_status = 'error'
                health_issues.append(_('Error: %d consecutive errors') % config.consecutive_errors)
            elif config.consecutive_errors >= 3:
                config.health_status = 'warning'
                health_issues.append(_('Warning: %d consecutive errors') % config.consecutive_errors)
            else:
                config.health_status = 'healthy'
            
            # Check daily errors
            if config.daily_errors >= 50:
                if config.health_status != 'critical':
                    config.health_status = 'error'
                health_issues.append(_('%d errors today') % config.daily_errors)
            
            # Check DTE usage
            if config.dte_usage_percentage >= 90:
                if config.health_status == 'healthy':
                    config.health_status = 'warning'
                health_issues.append(_('DTE usage at %.1f%%') % config.dte_usage_percentage)
            
            # Check signature expiry
            if config.llave_firma_expiry:
                days_until_expiry = (config.llave_firma_expiry - fields.Date.today()).days
                if days_until_expiry <= 0:
                    config.health_status = 'critical'
                    health_issues.append(_('Signature key expired!'))
                elif days_until_expiry <= 30:
                    if config.health_status == 'healthy':
                        config.health_status = 'warning'
                    health_issues.append(_('Signature key expires in %d days') % days_until_expiry)
            
            # Set health message
            if health_issues:
                config.health_message = '\n'.join(health_issues)
            else:
                config.health_message = _('All systems operational')
    
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
        
        # Check and reset daily counter if needed
        config._check_daily_counter_reset()
        
        return config
    
    def _check_daily_counter_reset(self):
        """Check if daily counter needs reset"""
        self.ensure_one()
        today = fields.Date.today()
        
        if self.last_counter_reset != today:
            self.write({
                'daily_counter': 0,
                'daily_errors': 0,
                'last_counter_reset': today,
            })
            _logger.info(f"Reset daily counters for FEL config {self.id}")
    
    def increment_counter(self, is_error=False):
        """Increment transaction counter"""
        self.ensure_one()
        self._check_daily_counter_reset()
        
        vals = {
            'daily_counter': self.daily_counter + 1,
        }
        
        if is_error:
            vals.update({
                'daily_errors': self.daily_errors + 1,
                'consecutive_errors': self.consecutive_errors + 1,
                'last_error_date': fields.Datetime.now(),
            })
        else:
            vals.update({
                'consecutive_errors': 0,
                'last_successful_transaction': fields.Datetime.now(),
            })
        
        self.write(vals)
        
        # Check if approaching daily limit
        if self.daily_counter >= (self.daily_limit * 0.9):  # 90% of limit
            _logger.warning(f"FEL daily limit warning: {self.daily_counter}/{self.daily_limit} transactions")
    
    def can_send_transaction(self):
        """Check if we can send another transaction"""
        self.ensure_one()
        self._check_daily_counter_reset()
        
        if self.daily_counter >= self.daily_limit:
            raise ValidationError(_('Daily FEL transaction limit reached (%d/%d). Please try again tomorrow.') % 
                                (self.daily_counter, self.daily_limit))
        
        # Check signature expiry
        if self.llave_firma_expiry and self.llave_firma_expiry < fields.Date.today():
            raise ValidationError(_('FEL signature key has expired. Please update your credentials.'))
        
        return True
    
    def get_infile_headers(self, identifier=None):
        """Get headers for INFILE API requests"""
        self.ensure_one()
        
        if not all([self.usuario_firma, self.llave_firma, self.usuario_api, self.llave_api]):
            raise ValidationError(_('INFILE credentials are not complete. Please check your configuration.'))
        
        # Generate unique identifier if not provided
        if not identifier:
            identifier = f"{self.company_id.id}_{int(datetime.now().timestamp() * 1000)}"
        
        return {
            'UsuarioFirma': self.usuario_firma,
            'LlaveFirma': self.llave_firma,
            'UsuarioApi': self.usuario_api,
            'LlaveApi': self.llave_api,
            'identificador': identifier,
            'Content-Type': 'text/xml; charset=utf-8',
            'Accept': 'application/json',
        }
    
    def test_connection(self):
        """Test connection to FEL provider"""
        self.ensure_one()
        
        try:
            # For INFILE, test NIT verification endpoint
            if self.provider_id.code == 'infile':
                headers = self.get_infile_headers()
                
                # Test with a known valid NIT (CF)
                test_data = {
                    'emisor_codigo': self.usuario_api,
                    'emisor_clave': self.llave_api,
                    'nit_consulta': 'CF'
                }
                
                response = requests.post(
                    self.nit_verification_url,
                    json=test_data,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('nit') == 'CF':
                        self.last_sync = fields.Datetime.now()
                        return {
                            'type': 'ir.actions.client',
                            'tag': 'display_notification',
                            'params': {
                                'title': _('Connection Successful'),
                                'message': _('Successfully connected to INFILE. NIT verification working correctly.'),
                                'type': 'success',
                            }
                        }
                    else:
                        raise ValidationError(_('INFILE connection test failed: Invalid response'))
                else:
                    raise ValidationError(_('Connection failed with status code: %s') % response.status_code)
            else:
                # Generic test for other providers
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
                    
        except requests.exceptions.Timeout:
            raise ValidationError(_('Connection timeout. Please check the API URL and your internet connection.'))
        except requests.exceptions.ConnectionError:
            raise ValidationError(_('Connection error. Please check the API URL and try again.'))
        except Exception as e:
            raise ValidationError(_('Connection test failed: %s') % str(e))
    
    def action_check_signature_expiry(self):
        """Check and update signature expiry date"""
        self.ensure_one()
        
        if not self.llave_firma_expiry:
            # Set default 2 years from today
            self.llave_firma_expiry = fields.Date.today() + timedelta(days=730)
            
        days_remaining = (self.llave_firma_expiry - fields.Date.today()).days
        
        message_type = 'success'
        if days_remaining <= 0:
            message = _('Signature key has expired! Please update immediately.')
            message_type = 'danger'
        elif days_remaining <= 30:
            message = _('Signature key expires in %d days. Please plan for renewal.') % days_remaining
            message_type = 'warning'
        else:
            message = _('Signature key is valid for %d more days.') % days_remaining
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Signature Key Status'),
                'message': message,
                'type': message_type,
            }
        }
    
    def action_view_health_dashboard(self):
        """Open health monitoring dashboard"""
        self.ensure_one()
        # This will be implemented in a separate view
        return {
            'type': 'ir.actions.act_window',
            'name': _('FEL Health Dashboard'),
            'res_model': 'fel.config',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'context': {'show_health_dashboard': True},
        }
    # Add these methods to the FelConfig class in models/fel_config.py

    def action_view_documents(self):
        """View all FEL documents for this configuration"""
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
        """View monthly statistics for FEL documents"""
        self.ensure_one()
        
        # Calculate date range for current month
        today = fields.Date.today()
        month_start = today.replace(day=1)
        
        # Get next month's first day
        if today.month == 12:
            month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Monthly FEL Documents'),
            'res_model': 'fel.document',
            'view_mode': 'tree,form,pivot,graph',
            'domain': [
                ('company_id', '=', self.company_id.id),
                ('generation_date', '>=', month_start),
                ('generation_date', '<=', month_end),
            ],
            'context': {
                'default_company_id': self.company_id.id,
                'search_default_group_by_state': 1,
                'search_default_group_by_document_type': 1,
            },
        }
    
    
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
                if len(clean_nit) < 6 or len(clean_nit) > 14:
                    raise ValidationError(_('Company NIT must have between 6 and 14 digits.'))
    
    @api.onchange('provider_id')
    def _onchange_provider_id(self):
        """Update URLs when provider changes"""
        if self.provider_id and self.provider_id.code == 'infile':
            self.certification_url = 'https://certificador.feel.com.gt/fel/procesounificado/transaccion/v2/xml'
            self.nit_verification_url = 'https://consultareceptores.feel.com.gt/rest/action'
            self.cui_verification_url = 'https://certificador.feel.com.gt/api/v2/servicios/externos/cui'
            self.cui_login_url = 'https://certificador.feel.com.gt/api/v2/servicios/externos/login'