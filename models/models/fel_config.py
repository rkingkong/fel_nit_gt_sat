from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import logging

_logger = logging.getLogger(__name__)

class FelConfiguration(models.Model):
    _name = 'fel.config'
    _description = 'FEL Configuration'
    _rec_name = 'company_id'

    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        required=True,
        default=lambda self: self.env.company
    )
    
    # Provider Configuration
    provider_id = fields.Many2one(
        'fel.certification.provider',
        string='Certification Provider',
        required=True
    )
    
    # NIT and Tax Information
    nit = fields.Char(
        string='NIT',
        required=True,
        help='Número de Identificación Tributaria'
    )
    
    tax_regime = fields.Selection([
        ('general', 'Régimen General'),
        ('pequeno', 'Pequeño Contribuyente'),
        ('especial', 'Régimen Especial'),
    ], string='Tax Regime', required=True, default='general')
    
    # Environment Configuration
    environment = fields.Selection([
        ('test', 'Test Environment'),
        ('production', 'Production'),
    ], string='Environment', required=True, default='test')
    
    # API Configuration
    api_url = fields.Char(string='API URL', required=True)
    api_username = fields.Char(string='API Username')
    api_password = fields.Char(string='API Password')
    api_token = fields.Char(string='API Token')
    
    # Certificate Configuration
    certificate_file = fields.Binary(string='Certificate File')
    certificate_password = fields.Char(string='Certificate Password')
    
    # Status
    is_active = fields.Boolean(string='Active', default=True)
    last_sync = fields.Datetime(string='Last Synchronization')
    
    # Monthly Statistics
    monthly_dte_count = fields.Integer(string='Monthly DTE Count', readonly=True)
    monthly_dte_limit = fields.Integer(string='Monthly DTE Limit', default=1200)
    
    @api.model
    def get_active_config(self, company_id=None):
        """Get active FEL configuration for company"""
        domain = [('is_active', '=', True)]
        if company_id:
            domain.append(('company_id', '=', company_id))
        else:
            domain.append(('company_id', '=', self.env.company.id))
            
        config = self.search(domain, limit=1)
        if not config:
            raise ValidationError(_('No active FEL configuration found for this company.'))
        return config
    
    def test_connection(self):
        """Test connection to FEL provider"""
        try:
            # Implementation depends on provider
            if self.provider_id.code == 'infile':
                return self._test_infile_connection()
            else:
                return self._test_generic_connection()
        except Exception as e:
            raise ValidationError(_('Connection test failed: %s') % str(e))
    
    def _test_infile_connection(self):
        """Test INFILE connection"""
        # Implement INFILE specific connection test
        pass
    
    def _test_generic_connection(self):
        """Test generic provider connection"""
        pass
