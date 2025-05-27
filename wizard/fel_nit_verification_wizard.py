# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
import logging

_logger = logging.getLogger(__name__)

class FelNitVerificationWizard(models.TransientModel):
    _name = 'fel.nit.verification.wizard'
    _description = 'FEL NIT Verification Wizard'
    
    # Input fields
    nit = fields.Char(
        string='NIT to Verify', 
        required=True,
        help='Enter the NIT to verify with SAT (e.g. 12345678-9 or CF)'
    )
    
    partner_id = fields.Many2one(
        'res.partner', 
        string='Partner',
        help='Partner to update with verification results'
    )
    
    # Result fields
    verification_state = fields.Selection([
        ('draft', 'Ready to Verify'),
        ('verifying', 'Verifying...'),
        ('verified', 'Verified'),
        ('error', 'Error'),
    ], string='Status', default='draft', readonly=True)
    
    is_verified = fields.Boolean(
        string='Verified with SAT', 
        readonly=True,
        help='Whether the NIT was successfully verified'
    )
    
    verification_message = fields.Text(
        string='Verification Message', 
        readonly=True,
        help='Message from the verification service'
    )
    
    # SAT Information (filled after verification)
    sat_name = fields.Char(
        string='SAT Registered Name', 
        readonly=True,
        help='Official name as registered with SAT'
    )
    
    sat_address = fields.Text(
        string='SAT Registered Address', 
        readonly=True,
        help='Official address as registered with SAT'
    )
    
    tax_regime = fields.Selection([
        ('general', 'Régimen General'),
        ('pequeno', 'Pequeño Contribuyente'),
        ('especial', 'Régimen Especial'),
    ], string='Tax Regime', readonly=True,
       help='Tax regime as registered with SAT')
    
    sat_status = fields.Char(
        string='SAT Status', 
        readonly=True,
        help='Registration status with SAT'
    )
    
    # Options
    update_partner = fields.Boolean(
        string='Update Partner Information',
        default=True,
        help='Update partner with verification results'
    )
    
    create_partner = fields.Boolean(
        string='Create Partner if Not Exists',
        default=False,
        help='Create new partner if NIT is valid but partner does not exist'
    )
    
    partner_name = fields.Char(
        string='Partner Name',
        help='Name for the partner (required if creating new partner)'
    )
    
    # Computed fields
    clean_nit = fields.Char(
        string='Cleaned NIT',
        compute='_compute_clean_nit',
        help='NIT formatted for verification'
    )
    
    can_verify = fields.Boolean(
        string='Can Verify',
        compute='_compute_can_verify',
        help='Whether the NIT can be verified'
    )
    
    show_partner_creation = fields.Boolean(
        string='Show Partner Creation',
        compute='_compute_show_partner_creation',
        help='Whether to show partner creation options'
    )
    
    @api.depends('nit')
    def _compute_clean_nit(self):
        """Clean and format NIT"""
        for wizard in self:
            if wizard.nit:
                # Clean NIT (remove non-alphanumeric except CF)
                if wizard.nit.upper() == 'CF':
                    wizard.clean_nit = 'CF'
                else:
                    wizard.clean_nit = re.sub(r'\D', '', wizard.nit)
            else:
                wizard.clean_nit = ''
    
    @api.depends('clean_nit')
    def _compute_can_verify(self):
        """Check if NIT can be verified"""
        for wizard in self:
            if wizard.clean_nit == 'CF':
                wizard.can_verify = False
            elif wizard.clean_nit and len(wizard.clean_nit) >= 8:
                wizard.can_verify = True
            else:
                wizard.can_verify = False
    
    @api.depends('is_verified', 'partner_id', 'create_partner')
    def _compute_show_partner_creation(self):
        """Show partner creation options when appropriate"""
        for wizard in self:
            wizard.show_partner_creation = (
                wizard.is_verified and 
                not wizard.partner_id and 
                wizard.create_partner
            )
    
    @api.onchange('nit')
    def _onchange_nit(self):
        """Reset verification when NIT changes"""
        if self.nit:
            # Reset verification results
            self.verification_state = 'draft'
            self.is_verified = False
            self.verification_message = ''
            self.sat_name = ''
            self.sat_address = ''
            self.tax_regime = False
            self.sat_status = ''
            
            # Try to find existing partner
            if self.clean_nit and self.clean_nit != 'CF':
                partner = self.env['res.partner'].search([
                    ('nit_gt', '=', self.clean_nit)
                ], limit=1)
                if partner:
                    self.partner_id = partner.id
                    self.partner_name = partner.name
                else:
                    self.partner_id = False
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Update NIT when partner changes"""
        if self.partner_id and self.partner_id.nit_gt:
            self.nit = self.partner_id.nit_gt
            self.partner_name = self.partner_id.name
    
    def action_verify_nit(self):
        """Verify NIT with SAT"""
        self.ensure_one()
        
        if not self.can_verify:
            raise ValidationError(_('Invalid NIT format. Please enter a valid Guatemala NIT.'))
        
        try:
            self.verification_state = 'verifying'
            
            # Get FEL configuration
            try:
                fel_config = self.env['fel.config'].get_active_config()
            except ValidationError:
                raise ValidationError(_('No active FEL configuration found. Please configure FEL first.'))
            
            # Call verification service
            verification_service = self.env['fel.nit.verification.service']
            result = verification_service.verify_nit(self.clean_nit, fel_config)
            
            # Update wizard with results
            self.write({
                'verification_state': 'verified' if result.get('verified') else 'error',
                'is_verified': result.get('verified', False),
                'verification_message': result.get('message', ''),
                'sat_name': result.get('name', ''),
                'sat_address': result.get('address', ''),
                'sat_status': result.get('status', ''),
            })
            
            # Map tax regime
            if result.get('regime'):
                regime_mapping = {
                    'GENERAL': 'general',
                    'RÉGIMEN GENERAL': 'general',
                    'PEQUEÑO': 'pequeno',
                    'PEQUEÑO CONTRIBUYENTE': 'pequeno',
                    'ESPECIAL': 'especial',
                    'RÉGIMEN ESPECIAL': 'especial',
                }
                regime = regime_mapping.get(result.get('regime', '').upper())
                if regime:
                    self.tax_regime = regime
            
            # Auto-fill partner name if verified and not set
            if self.is_verified and not self.partner_name and self.sat_name:
                self.partner_name = self.sat_name
            
            _logger.info(f"NIT verification completed for {self.clean_nit}: {result.get('verified')}")
            
        except Exception as e:
            self.write({
                'verification_state': 'error',
                'is_verified': False,
                'verification_message': str(e),
            })
            _logger.error(f"NIT verification failed for {self.clean_nit}: {str(e)}")
            raise ValidationError(_('NIT verification failed: %s') % str(e))
        
        # Return action to stay in wizard
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fel.nit.verification.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
    
    def action_update_partner(self):
        """Update partner with verification results"""
        self.ensure_one()
        
        if not self.is_verified:
            raise ValidationError(_('Can only update partner with verified NIT information.'))
        
        partner = self.partner_id
        
        # Create partner if requested and doesn't exist
        if not partner and self.create_partner:
            if not self.partner_name:
                raise ValidationError(_('Partner name is required to create a new partner.'))
            
            partner = self.env['res.partner'].create({
                'name': self.partner_name,
                'nit_gt': self.clean_nit,
                'is_company': True,
                'customer_rank': 1,
                'country_id': self.env.ref('base.gt').id,
            })
            self.partner_id = partner.id
        
        if not partner:
            raise ValidationError(_('No partner selected to update.'))
        
        # Update partner with verification data
        update_data = {
            'nit_gt': self.clean_nit,
            'is_fel_verified': True,
            'fel_verification_date': fields.Datetime.now(),
            'fel_verification_result': self.verification_message,
            'fel_verification_status': 'valid',
            'sat_name': self.sat_name,
            'sat_status': self.sat_status,
            'sat_address': self.sat_address,
        }
        
        # Update tax regime if available
        if self.tax_regime:
            update_data['tax_regime_gt'] = self.tax_regime
        
        # Update name if empty and SAT provides one
        if not partner.name and self.sat_name:
            update_data['name'] = self.sat_name
        
        partner.write(update_data)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Partner Updated'),
                'message': _('Partner "%s" updated successfully with verified NIT information.') % partner.name,
                'type': 'success',
            }
        }
    
    def action_view_partner(self):
        """View the updated partner"""
        self.ensure_one()
        
        if not self.partner_id:
            raise ValidationError(_('No partner to view.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Partner'),
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_verify_another(self):
        """Start verification of another NIT"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Verify NIT'),
            'res_model': 'fel.nit.verification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_create_partner': self.create_partner},
        }
    
    @api.model
    def action_batch_verify(self, partner_ids):
        """Batch verify multiple partners"""
        partners = self.env['res.partner'].browse(partner_ids)
        verified_count = 0
        error_count = 0
        
        for partner in partners.filtered(lambda p: p.nit_gt and p.nit_gt != 'CF' and not p.is_fel_verified):
            try:
                # Create wizard for each partner
                wizard = self.create({
                    'nit': partner.nit_gt,
                    'partner_id': partner.id,
                    'update_partner': True,
                })
                
                # Verify and update
                wizard.action_verify_nit()
                if wizard.is_verified:
                    wizard.action_update_partner()
                    verified_count += 1
                else:
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                _logger.error(f"Batch verification failed for partner {partner.id}: {str(e)}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Verification Complete'),
                'message': _('Verified %d NITs successfully, %d errors.') % (verified_count, error_count),
                'type': 'success' if verified_count > 0 else 'warning',
            }
        }
