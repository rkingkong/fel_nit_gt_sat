class FelNitVerificationWizard(models.TransientModel):
    _name = 'fel.nit.verification.wizard'
    _description = 'FEL NIT Verification Wizard'
    
    nit = fields.Char(string='NIT', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
    
    # Results
    is_verified = fields.Boolean(string='Verified', readonly=True)
    verification_message = fields.Text(string='Verification Message', readonly=True)
    partner_name = fields.Char(string='Partner Name', readonly=True)
    tax_regime = fields.Char(string='Tax Regime', readonly=True)
    
    def verify_nit(self):
        """Verify NIT with SAT"""
        try:
            # Get FEL configuration
            fel_config = self.env['fel.config'].get_active_config()
            
            # Call verification service
            verification_service = self.env['fel.nit.verification.service']
            result = verification_service.verify_nit(self.nit, fel_config)
            
            # Update wizard with results
            self.write({
                'is_verified': result.get('verified', False),
                'verification_message': result.get('message', ''),
                'partner_name': result.get('name', ''),
                'tax_regime': result.get('regime', ''),
            })
            
            # Update partner if specified
            if self.partner_id and result.get('verified'):
                self.partner_id.write({
                    'nit_gt': self.nit,
                    'is_fel_verified': True,
                    'fel_verification_date': fields.Datetime.now(),
                    'fel_verification_result': result.get('message', ''),
                })
                
                if result.get('regime'):
                    regime_map = {
                        'GENERAL': 'general',
                        'PEQUEÑO': 'pequeno',
                        'ESPECIAL': 'especial',
                    }
                    regime = regime_map.get(result.get('regime', '').upper())
                    if regime:
                        self.partner_id.tax_regime_gt = regime
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'fel.nit.verification.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
            }
            
        except Exception as e:
            raise ValidationError(_('NIT verification failed: %s') % str(e))
