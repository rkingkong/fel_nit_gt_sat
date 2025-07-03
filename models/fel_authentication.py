# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import requests
import json
import logging
import time
from datetime import datetime, timedelta
import uuid
import hashlib

_logger = logging.getLogger(__name__)

class FelAuthenticationService(models.AbstractModel):
    """Service class for FEL authentication and communication"""
    _name = 'fel.authentication.service'
    _description = 'FEL Authentication Service'
    
    # Transaction tracking for retry logic
    _transaction_cache = {}
    
    @api.model
    def generate_unique_identifier(self, prefix=None):
        """Generate unique identifier for FEL transactions"""
        if not prefix:
            prefix = self.env.company.id
        
        # Format: PREFIX_TIMESTAMP_RANDOM
        timestamp = int(datetime.now().timestamp() * 1000)
        random_part = uuid.uuid4().hex[:8]
        
        identifier = f"{prefix}_{timestamp}_{random_part}"
        
        # Store in cache for retry logic
        self._transaction_cache[identifier] = {
            'created': datetime.now(),
            'attempts': 0,
            'last_attempt': None,
        }
        
        # Clean old entries (older than 24 hours)
        self._clean_transaction_cache()
        
        return identifier
    
    def _clean_transaction_cache(self):
        """Clean old transaction identifiers from cache"""
        cutoff = datetime.now() - timedelta(hours=24)
        to_remove = []
        
        for identifier, data in self._transaction_cache.items():
            if data['created'] < cutoff:
                to_remove.append(identifier)
        
        for identifier in to_remove:
            del self._transaction_cache[identifier]
    
    @api.model
    def get_transaction_identifier(self, document_id, document_type='invoice'):
        """Get or create transaction identifier for a specific document"""
        # Create a deterministic identifier based on document
        hash_input = f"{self.env.company.id}_{document_type}_{document_id}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()[:12]
        
        identifier = f"{self.env.company.id}_{hash_value}"
        
        # Check if exists in cache
        if identifier not in self._transaction_cache:
            self._transaction_cache[identifier] = {
                'created': datetime.now(),
                'attempts': 0,
                'last_attempt': None,
                'document_id': document_id,
                'document_type': document_type,
            }
        
        return identifier
    
    @api.model
    def prepare_infile_headers(self, fel_config, identifier=None):
        """Prepare headers for INFILE API requests"""
        if not identifier:
            identifier = self.generate_unique_identifier()
        
        # Validate credentials
        required_fields = ['usuario_firma', 'llave_firma', 'usuario_api', 'llave_api']
        missing_fields = [f for f in required_fields if not getattr(fel_config, f, None)]
        
        if missing_fields:
            raise ValidationError(
                _('Missing INFILE credentials: %s. Please complete the FEL configuration.') 
                % ', '.join(missing_fields)
            )
        
        # Check signature key expiry
        if fel_config.llave_firma_expiry and fel_config.llave_firma_expiry < fields.Date.today():
            raise ValidationError(_('FEL signature key has expired. Please update your credentials.'))
        
        headers = {
            'UsuarioFirma': fel_config.usuario_firma,
            'LlaveFirma': fel_config.llave_firma,
            'UsuarioApi': fel_config.usuario_api,
            'LlaveApi': fel_config.llave_api,
            'identificador': identifier,
        }
        
        return headers, identifier
    
    @api.model
    def send_to_infile(self, fel_config, xml_content, identifier=None, retry_count=0):
        """Send XML to INFILE with retry logic"""
        # Check if we can send
        fel_config.can_send_transaction()
        
        # Prepare headers
        headers, used_identifier = self.prepare_infile_headers(fel_config, identifier)
        
        # Update transaction cache
        if used_identifier in self._transaction_cache:
            self._transaction_cache[used_identifier]['attempts'] += 1
            self._transaction_cache[used_identifier]['last_attempt'] = datetime.now()
        
        # Prepare request
        headers['Content-Type'] = 'text/xml; charset=utf-8'
        headers['Accept'] = 'application/json'
        
        url = fel_config.certification_url
        
        try:
            _logger.info(f"Sending to INFILE with identifier: {used_identifier}")
            
            # Make request
            response = requests.post(
                url,
                data=xml_content.encode('utf-8'),
                headers=headers,
                timeout=60
            )
            
            # Log response for debugging
            _logger.debug(f"INFILE Response Status: {response.status_code}")
            _logger.debug(f"INFILE Response Headers: {response.headers}")
            
            # Check status code
            if response.status_code != 200:
                error_msg = f"INFILE returned status {response.status_code}"
                if response.text:
                    error_msg += f": {response.text}"
                
                # Determine if retry is appropriate
                if self._should_retry_error(response.status_code, error_msg):
                    return self._handle_retry(
                        fel_config, xml_content, used_identifier, 
                        retry_count, error_msg
                    )
                else:
                    fel_config.increment_counter(is_error=True)
                    raise ValidationError(error_msg)
            
            # Parse response
            try:
                result = response.json()
            except json.JSONDecodeError:
                _logger.error(f"Failed to parse INFILE response: {response.text}")
                raise ValidationError(_('Invalid response from INFILE. Response was not valid JSON.'))
            
            # Check for success
            if result.get('resultado'):
                # Success - update counters
                fel_config.increment_counter(is_error=False)
                
                # Extract UUID, series, and number
                uuid = result.get('uuid')
                xml_certificado = result.get('xml_certificado', '')
                
                # Extract series and number from UUID
                if uuid:
                    series = uuid[:8]  # First 8 characters
                    # Convert hex to decimal for number
                    number_hex = uuid[9:13] + uuid[14:18]  # Skip hyphens
                    number = str(int(number_hex, 16))
                else:
                    series = result.get('serie', '')
                    number = result.get('numero', '')
                
                return {
                    'success': True,
                    'uuid': uuid,
                    'series': series,
                    'number': number,
                    'xml_certified': xml_certificado,
                    'full_response': result,
                    'identifier': used_identifier,
                }
            
            else:
                # Error from INFILE
                error_msg = self._parse_infile_error(result)
                
                # Check if we should retry
                if self._should_retry_infile_error(result):
                    return self._handle_retry(
                        fel_config, xml_content, used_identifier, 
                        retry_count, error_msg
                    )
                
                # Update error counters
                fel_config.increment_counter(is_error=True)
                fel_config.write({
                    'last_error_message': error_msg,
                })
                
                return {
                    'success': False,
                    'error': error_msg,
                    'full_response': result,
                    'identifier': used_identifier,
                }
                
        except requests.exceptions.Timeout:
            error_msg = "Request timeout after 60 seconds"
            if fel_config.retry_on_timeout and retry_count < fel_config.max_retry_attempts:
                return self._handle_retry(
                    fel_config, xml_content, used_identifier, 
                    retry_count, error_msg
                )
            else:
                fel_config.increment_counter(is_error=True)
                raise ValidationError(_('INFILE request timeout. Please try again.'))
                
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            if fel_config.retry_on_connection_error and retry_count < fel_config.max_retry_attempts:
                return self._handle_retry(
                    fel_config, xml_content, used_identifier, 
                    retry_count, error_msg
                )
            else:
                fel_config.increment_counter(is_error=True)
                raise ValidationError(_('Connection error to INFILE. Please check your internet connection.'))
                
        except Exception as e:
            fel_config.increment_counter(is_error=True)
            _logger.exception(f"Unexpected error sending to INFILE: {str(e)}")
            raise ValidationError(_('Unexpected error: %s') % str(e))
    
    def _handle_retry(self, fel_config, xml_content, identifier, retry_count, error_msg):
        """Handle retry logic"""
        retry_count += 1
        
        if retry_count > fel_config.max_retry_attempts:
            fel_config.increment_counter(is_error=True)
            raise ValidationError(
                _('Failed after %d attempts. Last error: %s') 
                % (retry_count, error_msg)
            )
        
        # Wait before retry
        wait_time = fel_config.retry_delay_seconds * retry_count
        _logger.info(f"Retrying in {wait_time} seconds (attempt {retry_count}/{fel_config.max_retry_attempts})")
        time.sleep(wait_time)
        
        # Retry with same identifier
        return self.send_to_infile(fel_config, xml_content, identifier, retry_count)
    
    def _parse_infile_error(self, response):
        """Parse error message from INFILE response"""
        # Check different possible error fields
        if 'descripcion_errores' in response and response['descripcion_errores']:
            errors = response['descripcion_errores']
            if isinstance(errors, list):
                # Format error list
                error_msgs = []
                for error in errors:
                    if isinstance(error, dict):
                        # Extract meaningful fields
                        msg_parts = []
                        if 'fuente' in error:
                            msg_parts.append(f"[{error['fuente']}]")
                        if 'categoria' in error:
                            msg_parts.append(error['categoria'])
                        if 'numeral' in error:
                            msg_parts.append(f"#{error['numeral']}")
                        if 'validacion' in error:
                            msg_parts.append(f"V{error['validacion']}")
                        if 'mensaje_error' in error:
                            msg_parts.append(error['mensaje_error'])
                        
                        error_msgs.append(' '.join(msg_parts))
                    else:
                        error_msgs.append(str(error))
                
                return '\n'.join(error_msgs)
            else:
                return str(errors)
        
        elif 'mensaje' in response:
            return response['mensaje']
        
        elif 'descripcion' in response:
            return response['descripcion']
        
        else:
            return json.dumps(response)
    
    def _should_retry_error(self, status_code, error_msg):
        """Determine if error should trigger retry"""
        # Retry on server errors
        if status_code >= 500:
            return True
        
        # Retry on specific client errors
        retry_messages = [
            'timeout',
            'connection',
            'temporar',
            'try again',
            'rate limit',
        ]
        
        error_lower = error_msg.lower()
        return any(msg in error_lower for msg in retry_messages)
    
    def _should_retry_infile_error(self, response):
        """Check if INFILE error response warrants retry"""
        # Check for specific error codes that indicate temporary issues
        if 'codigo_error' in response:
            retry_codes = ['TEMP001', 'LIMIT001', 'CONN001']  # Example codes
            if response['codigo_error'] in retry_codes:
                return True
        
        # Check error messages
        error_msg = self._parse_infile_error(response).lower()
        
        temporary_indicators = [
            'temporal',
            'momento',
            'intente',
            'sobrecarga',
            'timeout',
            'límite diario',
        ]
        
        return any(indicator in error_msg for indicator in temporary_indicators)
    
    @api.model
    def verify_nit_infile(self, nit, fel_config):
        """Verify NIT using INFILE service"""
        try:
            url = fel_config.nit_verification_url
            
            # Prepare request data
            data = {
                'emisor_codigo': fel_config.usuario_api,
                'emisor_clave': fel_config.llave_api,
                'nit_consulta': nit.upper().strip()
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }
            
            _logger.info(f"Verifying NIT {nit} with INFILE")
            
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                # Parse response
                if result.get('nit'):
                    return {
                        'success': True,
                        'nit': result.get('nit'),
                        'name': result.get('nombre', ''),
                        'message': result.get('mensaje', ''),
                    }
                else:
                    return {
                        'success': False,
                        'error': result.get('mensaje', 'NIT verification failed'),
                    }
            else:
                return {
                    'success': False,
                    'error': f'Service returned status {response.status_code}',
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'NIT verification timeout',
            }
        except Exception as e:
            _logger.exception(f"Error verifying NIT: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    @api.model
    def get_cui_auth_token(self, fel_config):
        """Get JWT token for CUI verification"""
        try:
            url = fel_config.cui_login_url
            
            data = {
                'prefijo': fel_config.usuario_api,
                'llave': fel_config.llave_api,
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            response = requests.post(url, data=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                return {
                    'success': True,
                    'token': result.get('token'),
                    'expires': result.get('fecha_de_vencimiento'),
                }
            else:
                return {
                    'success': False,
                    'error': f'Authentication failed with status {response.status_code}',
                }
                
        except Exception as e:
            _logger.exception(f"Error getting CUI token: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    @api.model
    def verify_cui_infile(self, cui, fel_config, token=None):
        """Verify CUI using INFILE service"""
        try:
            # Get token if not provided
            if not token:
                token_result = self.get_cui_auth_token(fel_config)
                if not token_result['success']:
                    return token_result
                token = token_result['token']
            
            url = fel_config.cui_verification_url
            
            data = {
                'cui': cui.strip()
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Bearer {token}',
            }
            
            response = requests.post(url, data=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                
                if 'cui' in result:
                    return {
                        'success': True,
                        'cui': result.get('cui'),
                        'name': result.get('nombre', ''),
                        'nombres': result.get('nombres', ''),
                        'apellidos': result.get('apellidos', ''),
                        'fallecido': result.get('fallecido', 'NO') == 'SI',
                    }
                else:
                    return {
                        'success': False,
                        'error': result.get('mensaje', 'CUI verification failed'),
                    }
            else:
                return {
                    'success': False,
                    'error': f'Service returned status {response.status_code}',
                }
                
        except Exception as e:
            _logger.exception(f"Error verifying CUI: {str(e)}")
            return {
                'success': False,
                'error': str(e),
            }
    
    @api.model
    def cancel_document_infile(self, uuid, reason, fel_config):
        """Cancel a certified document with INFILE"""
        # This would implement the cancellation logic
        # The actual endpoint and format would depend on INFILE's API
        raise NotImplementedError("Document cancellation not yet implemented")