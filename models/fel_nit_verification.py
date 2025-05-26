# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import requests
import json
import re
import logging

_logger = logging.getLogger(__name__)

class FelNitVerificationService(models.AbstractModel):
    _name = 'fel.nit.verification.service'
    _description = 'FEL NIT Verification Service'
    
    def verify_nit(self, nit, fel_config):
        """
        Verify NIT with SAT through FEL provider
        
        Args:
            nit (str): NIT to verify
            fel_config (fel.config): FEL configuration record
            
        Returns:
            dict: Verification result with keys:
                - verified (bool): Whether NIT is valid
                - name (str): Company/person name from SAT
                - regime (str): Tax regime
                - status (str): Registration status
                - address (str): Registered address
                - message (str): Status message
        """
        if not nit or nit == 'CF':
            return {
                'verified': False,
                'message': _('Cannot verify "Consumidor Final" (CF)')
            }
        
        # Clean NIT
        clean_nit = self._clean_nit_for_verification(nit)
        
        if not self._validate_nit_format(clean_nit):
            return {
                'verified': False,
                'message': _('Invalid NIT format')
            }
        
        # Route to appropriate provider
        if fel_config.provider_id.code == 'infile':
            return self._verify_nit_infile(clean_nit, fel_config)
        elif fel_config.provider_id.code == 'sat_direct':
            return self._verify_nit_sat_direct(clean_nit, fel_config)
        else:
            return self._verify_nit_generic(clean_nit, fel_config)
    
    def _clean_nit_for_verification(self, nit):
        """Clean NIT for verification API calls"""
        if not nit:
            return ''
        
        # Remove all non-digits except for CF
        if nit.upper() == 'CF':
            return 'CF'
        
        return re.sub(r'\D', '', nit)
    
    def _validate_nit_format(self, nit):
        """Validate NIT format for Guatemala"""
        if not nit or nit == 'CF':
            return nit == 'CF'
        
        # NIT should be 8-9 digits
        return len(nit) >= 8 and len(nit) <= 9 and nit.isdigit()
    
    def _verify_nit_infile(self, nit, fel_config):
        """Verify NIT using INFILE service"""
        try:
            # INFILE NIT verification endpoint
            url = f"{fel_config.api_url}/api/v1/nit/verify"
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }
            
            # Add authentication
            if fel_config.api_token:
                headers['Authorization'] = f'Bearer {fel_config.api_token}'
            elif fel_config.api_username and fel_config.api_password:
                # Use basic auth if token not available
                import base64
                credentials = base64.b64encode(
                    f"{fel_config.api_username}:{fel_config.api_password}".encode()
                ).decode()
                headers['Authorization'] = f'Basic {credentials}'
            
            data = {
                'nit': nit,
                'environment': fel_config.environment or 'test',
            }
            
            _logger.info(f"Verifying NIT {nit} with INFILE")
            
            response = requests.post(
                url, 
                json=data, 
                headers=headers, 
                timeout=30,
                verify=True  # Verify SSL certificates
            )
            
            _logger.info(f"INFILE response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                _logger.info(f"INFILE response: {result}")
                
                # Parse INFILE response format
                success = result.get('success', False) or result.get('valid', False)
                
                if success:
                    # Extract data from successful response
                    data = result.get('data', result)
                    
                    return {
                        'verified': True,
                        'name': data.get('nombre', data.get('name', '')),
                        'regime': data.get('regimen', data.get('regime', '')),
                        'status': data.get('estado', data.get('status', 'ACTIVO')),
                        'address': data.get('direccion', data.get('address', '')),
                        'message': result.get('mensaje', result.get('message', 'NIT verificado exitosamente')),
                    }
                else:
                    return {
                        'verified': False,
                        'message': result.get('mensaje', result.get('message', 'NIT no válido')),
                    }
            
            elif response.status_code == 401:
                return {
                    'verified': False,
                    'message': _('Authentication failed. Please check API credentials.')
                }
            
            elif response.status_code == 404:
                return {
                    'verified': False,
                    'message': _('NIT not found in SAT registry.')
                }
            
            else:
                return {
                    'verified': False,
                    'message': _('Verification service error: HTTP %s') % response.status_code
                }
                
        except requests.exceptions.Timeout:
            _logger.error("INFILE NIT verification timeout")
            return {
                'verified': False,
                'message': _('Verification service timeout. Please try again.')
            }
            
        except requests.exceptions.ConnectionError:
            _logger.error("INFILE NIT verification connection error")
            return {
                'verified': False,
                'message': _('Cannot connect to verification service. Please check your internet connection.')
            }
            
        except requests.exceptions.RequestException as e:
            _logger.error(f"INFILE NIT verification request error: {str(e)}")
            return {
                'verified': False,
                'message': _('Verification service error: %s') % str(e)
            }
            
        except json.JSONDecodeError as e:
            _logger.error(f"INFILE NIT verification JSON error: {str(e)}")
            return {
                'verified': False,
                'message': _('Invalid response from verification service.')
            }
            
        except Exception as e:
            _logger.error(f"INFILE NIT verification unexpected error: {str(e)}")
            return {
                'verified': False,
                'message': _('Unexpected error during verification: %s') % str(e)
            }
    
    def _verify_nit_sat_direct(self, nit, fel_config):
        """Verify NIT directly with SAT (if direct API available)"""
        try:
            # This would be the direct SAT API if available
            # For now, return not implemented
            return {
                'verified': False,
                'message': _('Direct SAT verification not yet implemented.')
            }
            
        except Exception as e:
            _logger.error(f"SAT direct NIT verification error: {str(e)}")
            return {
                'verified': False,
                'message': f'SAT verification failed: {str(e)}'
            }
    
    def _verify_nit_generic(self, nit, fel_config):
        """Generic NIT verification for unknown providers"""
        _logger.warning(f"Generic NIT verification requested for provider: {fel_config.provider_id.name}")
        return {
            'verified': False,
            'message': _('NIT verification not implemented for provider: %s') % fel_config.provider_id.name
        }
    
    def batch_verify_nits(self, nits, fel_config):
        """
        Verify multiple NITs in batch
        
        Args:
            nits (list): List of NITs to verify
            fel_config (fel.config): FEL configuration record
            
        Returns:
            dict: Results keyed by NIT
        """
        results = {}
        
        for nit in nits:
            try:
                results[nit] = self.verify_nit(nit, fel_config)
            except Exception as e:
                results[nit] = {
                    'verified': False,
                    'message': f'Error: {str(e)}'
                }
        
        return results
    
    def verify_and_update_partner(self, partner):
        """
        Verify NIT and update partner record
        
        Args:
            partner (res.partner): Partner record to verify and update
            
        Returns:
            dict: Verification result
        """
        if not partner.nit_gt:
            raise ValidationError(_('Partner must have a NIT to verify.'))
        
        try:
            # Get FEL configuration
            fel_config = self.env['fel.config'].get_active_config()
            
            # Verify NIT
            result = self.verify_nit(partner.nit_gt, fel_config)
            
            # Update partner based on results
            update_data = {
                'fel_verification_date': fields.Datetime.now(),
                'fel_verification_result': result.get('message', ''),
            }
            
            if result.get('verified'):
                update_data.update({
                    'is_fel_verified': True,
                    'fel_verification_status': 'valid',
                    'sat_name': result.get('name', ''),
                    'sat_status': result.get('status', ''),
                    'sat_address': result.get('address', ''),
                })
                
                # Map tax regime
                regime_mapping = {
                    'GENERAL': 'general',
                    'RÉGIMEN GENERAL': 'general',
                    'PEQUEÑO': 'pequeno',
                    'PEQUEÑO CONTRIBUYENTE': 'pequeno',
                    'ESPECIAL': 'especial',
                    'RÉGIMEN ESPECIAL': 'especial',
                }
                
                regime = result.get('regime', '').upper()
                mapped_regime = regime_mapping.get(regime)
                if mapped_regime:
                    update_data['tax_regime_gt'] = mapped_regime
                
                # Update name if empty and SAT provides one
                if not partner.name and result.get('name'):
                    update_data['name'] = result.get('name')
            else:
                update_data.update({
                    'is_fel_verified': False,
                    'fel_verification_status': 'invalid',
                })
            
            partner.write(update_data)
            return result
            
        except Exception as e:
            partner.write({
                'fel_verification_status': 'error',
                'fel_verification_date': fields.Datetime.now(),
                'fel_verification_result': str(e),
            })
            raise
