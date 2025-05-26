# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
import logging

_logger = logging.getLogger(__name__)

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Guatemala specific identification fields
    nit_gt = fields.Char(
        string='NIT Guatemala',
        help='Número de Identificación Tributaria (NIT) de Guatemala'
    )
    
    dpi_gt = fields.Char(
        string='DPI Guatemala',
        help='Documento Personal de Identificación (DPI) de Guatemala'
    )
    
    # FEL Integration fields
    is_fel_verified = fields.Boolean(
        string='FEL Verified',
        readonly=True,
        help='Indicates if the NIT has been verified with SAT'
    )
    
    fel_verification_date = fields.Datetime(
        string='FEL Verification Date',
        readonly=True,
        help='Date when the NIT was last verified with SAT'
    )
    
    fel_verification_result = fields.Text(
        string='FEL Verification Result',
        readonly=True,
        help='Result message from the last NIT verification'
    )
    
    fel_verification_status = fields.Selection([
        ('not_verified', 'Not Verified'),
        ('valid', 'Valid'),
        ('invalid', 'Invalid'),
        ('error', 'Verification Error'),
    ], string='FEL Verification Status', 
       default='not_verified', 
       readonly=True,
       help='Current status of NIT verification with SAT')
    
    # Tax regime information (important for document type selection)
    tax_regime_gt = fields.Selection([
        ('general', 'Régimen General'),
        ('pequeno', 'Pequeño Contribuyente'),
        ('especial', 'Régimen Especial'),
    ], string='Guatemala Tax Regime',
       help='Tax regime of the partner as registered with SAT')
    
    # SAT registration information
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
    
    sat_status = fields.Char(
        string='SAT Status',
        readonly=True,
        help='Registration status with SAT'
    )
    
    # FEL document preferences
    default_fel_document_type_id = fields.Many2one(
        'fel.document.type',
        string='Default FEL Document Type',
        help='Default document type to use for this partner'
    )
    
    require_fel = fields.Boolean(
        string='Require FEL',
        default=False,
        help='Always require FEL documents for this partner'
    )
    
    # Email for FEL documents
    fel_email = fields.Char(
        string='FEL Email',
        help='Email address for sending FEL documents (if different from main email)'
    )
    
    # Computed fields
    display_nit = fields.Char(
        string='Display NIT',
        compute='_compute_display_nit',
        help='Formatted NIT for display'
    )
    
    can_verify_nit = fields.Boolean(
        string='Can Verify NIT',
        compute='_compute_can_verify_nit',
        help='Whether NIT verification is possible'
    )
    
    @api.depends('nit_gt')
    def _compute_display_nit(self):
        """Format NIT for display"""
        for partner in self:
            if partner.nit_gt:
                # Format NIT as XXXXXXXX-X
                nit = re.sub(r'\D', '', partner.nit_gt)  # Remove non-digits
                if len(nit) >= 8:
                    partner.display_nit = f"{nit[:-1]}-{nit[-1]}"
                else:
                    partner.display_nit = partner.nit_gt
            else:
                partner.display_nit = False
    
    @api.depends('nit_gt', 'is_company')
    def _compute_can_verify_nit(self):
        """Check if NIT verification is possible"""
        for partner in self:
            partner.can_verify_nit = bool(
                partner.nit_gt and 
                partner.nit_gt != 'CF' and 
                len(re.sub(r'\D', '', partner.nit_gt)) >= 8
            )
    
    @api.onchange('nit_gt')
    def _onchange_nit_gt(self):
        """Reset verification when NIT changes"""
        if self.nit_gt:
            # Clean and format NIT
            self.nit_gt = self._clean_nit(self.nit_gt)
            
            # Reset verification status if NIT changed
            if self._origin.nit_gt != self.nit_gt:
                self.is_fel_verified = False
                self.fel_verification_status = 'not_verified'
                self.fel_verification_date = False
                self.fel_verification_result = ''
    
    @api.onchange('tax_regime_gt')
    def _onchange_tax_regime_gt(self):
        """Update default document type when tax regime changes"""
        if self.tax_regime_gt:
            doc_type_model = self.env['fel.document.type']
            if self.tax_regime_gt == 'pequeno':
                default_type = doc_type_model.get_document_type_by_code('FPEQ')
            elif self.tax_regime_gt == 'especial':
                default_type = doc_type_model.get_document_type_by_code('FESP')
            else:
                default_type = doc_type_model.get_document_type_by_code('FACT')
            
            if default_type:
                self.default_fel_document_type_id = default_type.id
    
    def _clean_nit(self, nit):
        """Clean and format NIT"""
        if not nit:
            return nit
        
        # Remove all non-alphanumeric characters except 'CF'
        if nit.upper() == 'CF':
            return 'CF'
        
        # Remove all non-digits
        clean_nit = re.sub(r'\D', '', nit)
        
        # Validate length (should be 8-9 digits for Guatemala)
        if len(clean_nit) < 8:
            return nit  # Return original if too short
        
        return clean_nit
    
    def verify_nit_with_sat(self):
        """Verify NIT with SAT through FEL provider"""
        self.ensure_one()
        
        if not self.nit_gt:
            raise ValidationError(_('NIT is required for verification.'))
        
        if self.nit_gt == 'CF':
            raise ValidationError(_('Cannot verify NIT for "Consumidor Final" (CF).'))
        
        try:
            # Get active FEL configuration
            fel_config = self.env['fel.config'].get_active_config()
            
            # Call NIT verification service
            verification_service = self.env['fel.nit.verification.service']
            result = verification_service.verify_nit(self.nit_gt, fel_config)
            
            # Update partner with verification results
            verification_data = {
                'fel_verification_date': fields.Datetime.now(),
                'fel_verification_result': result.get('message', ''),
            }
            
            if result.get('verified'):
                verification_data.update({
                    'is_fel_verified': True,
                    'fel_verification_status': 'valid',
                    'sat_name': result.get('name', ''),
                    'sat_status': result.get('status', ''),
                    'sat_address': result.get('address', ''),
                })
                
                # Update tax regime if provided
                if result.get('regime'):
                    regime_mapping = {
                        'GENERAL': 'general',
                        'PEQUEÑO': 'pequeno',
                        'PEQUEÑO CONTRIBUYENTE': 'pequeno',
                        'ESPECIAL': 'especial',
                    }
                    regime = regime_mapping.get(result.get('regime', '').upper())
                    if regime:
                        verification_data['tax_regime_gt'] = regime
                
                # Update name if not set and SAT provides it
                if result.get('name') and not self.name:
                    verification_data['name'] = result.get('name')
                    
            else:
                verification_data.update({
                    'is_fel_verified': False,
                    'fel_verification_status': 'invalid',
                })
            
            self.write(verification_data)
            
            # Return notification
            if result.get('verified'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('NIT Verification Successful'),
                        'message': _('NIT %s verified successfully with SAT.') % self.nit_gt,
                        'type': 'success',
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('NIT Verification Failed'),
                        'message': _('NIT %s could not be verified: %s') % (self.nit_gt, result.get('message', '')),
                        'type': 'warning',
                    }
                }
                
        except Exception as e:
            self.write({
                'fel_verification_status': 'error',
                'fel_verification_date': fields.Datetime.now(),
                'fel_verification_result': str(e),
            })
            _logger.error(f"NIT verification failed for {self.nit_gt}: {str(e)}")
            raise ValidationError(_('NIT verification failed: %s') % str(e))
    
    def action_verify_nit(self):
        """Action to verify NIT - can be called from buttons"""
        return self.verify_nit_with_sat()
    
    def get_fel_email(self):
        """Get the email address to use for FEL documents"""
        self.ensure_one()
        return self.fel_email or self.email
    
    def get_fel_document_type(self):
        """Get the appropriate FEL document type for this partner"""
        self.ensure_one()
        
        # Use partner's default if set
        if self.default_fel_document_type_id:
            return self.default_fel_document_type_id
        
        # Otherwise, determine based on tax regime
        doc_type_model = self.env['fel.document.type']
        if self.tax_regime_gt == 'pequeno':
            return doc_type_model.get_document_type_by_code('FPEQ')
        elif self.tax_regime_gt == 'especial':
            return doc_type_model.get_document_type_by_code('FESP')
        else:
            return doc_type_model.get_document_type_by_code('FACT')
    
    def is_consumidor_final(self):
        """Check if this partner is 'Consumidor Final'"""
        self.ensure_one()
        return self.nit_gt == 'CF' or not self.nit_gt
    
    @api.constrains('nit_gt')
    def _check_nit_format(self):
        """Validate NIT format"""
        for partner in self:
            if partner.nit_gt and partner.nit_gt != 'CF':
                # Remove all non-digits
                clean_nit = re.sub(r'\D', '', partner.nit_gt)
                
                # Check if it's a valid length (8-9 digits for Guatemala)
                if len(clean_nit) < 8 or len(clean_nit) > 9:
                    raise ValidationError(_('NIT must have 8 or 9 digits. Current NIT: %s') % partner.nit_gt)
    
    @api.constrains('dpi_gt')
    def _check_dpi_format(self):
        """Validate DPI format"""
        for partner in self:
            if partner.dpi_gt:
                # Remove all non-digits
                clean_dpi = re.sub(r'\D', '', partner.dpi_gt)
                
                # DPI should have 13 digits
                if len(clean_dpi) != 13:
                    raise ValidationError(_('DPI must have exactly 13 digits. Current DPI: %s') % partner.dpi_gt)
    
    def name_get(self):
        """Override name_get to include NIT in display"""
        result = []
        for partner in self:
            name = partner.name or ''
            if partner.nit_gt and partner.nit_gt != 'CF':
                name = f"{name} ({partner.display_nit})"
            result.append((partner.id, name))
        return result
    
    @api.model
    def search_by_nit(self, nit):
        """Search partner by NIT"""
        if not nit:
            return self.browse()
        
        # Clean the search NIT
        clean_nit = self._clean_nit(nit)
        
        # Search for exact match first
        partner = self.search([('nit_gt', '=', clean_nit)], limit=1)
        
        if not partner and clean_nit != 'CF':
            # Try searching without formatting
            partner = self.search([('nit_gt', 'ilike', clean_nit)], limit=1)
        
        return partner
    
    def action_open_fel_documents(self):
        """Open FEL documents for this partner"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('FEL Documents - %s') % self.name,
            'res_model': 'fel.document',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
