class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Guatemala specific fields
    nit_gt = fields.Char(string='NIT Guatemala')
    dpi_gt = fields.Char(string='DPI Guatemala')
    
    # FEL Integration
    is_fel_verified = fields.Boolean(string='FEL Verified', readonly=True)
    fel_verification_date = fields.Datetime(string='FEL Verification Date', readonly=True)
    fel_verification_result = fields.Text(string='FEL Verification Result', readonly=True)
    
    # Tax Information
    tax_regime_gt = fields.Selection([
        ('general', 'Régimen General'),
        ('pequeno', 'Pequeño Contribuyente'),
        ('especial', 'Régimen Especial'),
    ], string='Guatemala Tax Regime')
    
    def verify_nit_with_sat(self):
        """Verify NIT with SAT"""
        if not self.nit_gt:
            raise ValidationError(_('NIT is required for verification.'))
        
        try:
            # Get FEL configuration
            fel_config = self.env['fel.config'].get_active_config()
            
            # Call NIT verification service
            verification_service = self.env['fel.nit.verification.service']
            result = verification_service.verify_nit(self.nit_gt, fel_config)
            
            # Update partner with verification result
            self.write({
                'is_fel_verified': result.get('verified', False),
                'fel_verification_date': fields.Datetime.now(),
                'fel_verification_result': result.get('message', ''),
            })
            
            return result
            
        except Exception as e:
            _logger.error(f"NIT verification failed for {self.nit_gt}: {str(e)}")
            raise ValidationError(_('NIT verification failed: %s') % str(e))
