# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
import xml.etree.ElementTree as ET
from datetime import datetime
import requests
import logging

_logger = logging.getLogger(__name__)

class FelDocument(models.Model):
    _name = 'fel.document'
    _description = 'FEL Document'
    _order = 'create_date desc'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(
        string='Name', 
        compute='_compute_name', 
        store=True,
        help='Document name for display'
    )
    
    # Document Information
    document_type_id = fields.Many2one(
        'fel.document.type',
        string='Document Type',
        required=True,
        help='Type of FEL document (FACT, FPEQ, NCRE, etc.)'
    )
    
    # Related Records
    invoice_id = fields.Many2one(
        'account.move', 
        string='Invoice',
        help='Related invoice if this is an invoice document'
    )
    
    pos_order_id = fields.Many2one(
        'pos.order',
        string='POS Order',
        help='Related POS order if this is a POS document'
    )
    
    partner_id = fields.Many2one(
        'res.partner', 
        string='Customer', 
        required=True,
        help='Customer for this document'
    )
    
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        required=True,
        default=lambda self: self.env.company,
        help='Company issuing this document'
    )
    
    # FEL Specific Fields (assigned by SAT)
    uuid = fields.Char(
        string='UUID', 
        readonly=True,
        help='Unique identifier assigned by SAT',
        tracking=True
    )
    
    series = fields.Char(
        string='Series', 
        readonly=True,
        help='Document series assigned by SAT'
    )
    
    number = fields.Char(
        string='Number', 
        readonly=True,
        help='Document number assigned by SAT'
    )
    
    # XML and PDF Files
    xml_content = fields.Text(
        string='XML Content',
        help='Generated XML content for the document'
    )
    
    xml_file = fields.Binary(
        string='XML File',
        help='XML file for download'
    )
    
    xml_filename = fields.Char(
        string='XML Filename',
        help='Name of the XML file'
    )
    
    pdf_file = fields.Binary(
        string='PDF File',
        help='PDF file for download'
    )
    
    pdf_filename = fields.Char(
        string='PDF Filename',
        help='Name of the PDF file'
    )
    
    # Status and Tracking
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generating', 'Generating XML'),
        ('generated', 'XML Generated'),
        ('sending', 'Sending to SAT'),
        ('sent', 'Sent to SAT'),
        ('certified', 'Certified by SAT'),
        ('error', 'Error'),
        ('cancelled', 'Cancelled'),
    ], string='State', default='draft', readonly=True,
       help='Current processing state of the document',
       tracking=True)
    
    error_message = fields.Text(
        string='Error Message', 
        readonly=True,
        help='Error message if processing failed'
    )
    
    # Provider Responses
    provider_response = fields.Text(
        string='Provider Response', 
        readonly=True,
        help='Full response from the FEL provider'
    )
    
    sat_response = fields.Text(
        string='SAT Response', 
        readonly=True,
        help='Response from SAT through the provider'
    )
    
    # Dates
    generation_date = fields.Datetime(
        string='Generation Date', 
        readonly=True,
        help='Date when XML was generated'
    )
    
    certification_date = fields.Datetime(
        string='Certification Date', 
        readonly=True,
        help='Date when document was certified by SAT',
        tracking=True
    )
    
    # Document amounts for validation
    amount_untaxed = fields.Float(
        string='Untaxed Amount',
        help='Amount without taxes'
    )
    
    amount_tax = fields.Float(
        string='Tax Amount', 
        help='Total tax amount'
    )
    
    amount_total = fields.Float(
        string='Total Amount',
        help='Total amount including taxes'
    )
    
    @api.depends('document_type_id', 'partner_id', 'invoice_id', 'pos_order_id')
    def _compute_name(self):
        """Compute document name for display"""
        for record in self:
            if record.invoice_id:
                record.name = f"{record.document_type_id.code} - {record.invoice_id.name}"
            elif record.pos_order_id:
                record.name = f"{record.document_type_id.code} - {record.pos_order_id.name}"
            else:
                record.name = f"{record.document_type_id.code} - {record.partner_id.name}"
    
    def generate_xml(self):
        """Generate XML content for FEL document"""
        self.ensure_one()
        
        try:
            self.state = 'generating'
            
            # Get FEL configuration
            fel_config = self.env['fel.config'].get_active_config(self.company_id.id)
            
            # Generate XML based on document type
            if self.document_type_id.code in ['FACT', 'FCAM', 'FPEQ', 'FCAP', 'FESP']:
                xml_content = self._generate_invoice_xml(fel_config)
            elif self.document_type_id.code == 'NCRE':
                xml_content = self._generate_credit_note_xml(fel_config)
            elif self.document_type_id.code == 'NDEB':
                xml_content = self._generate_debit_note_xml(fel_config)
            else:
                raise ValidationError(_('Document type %s not supported yet.') % self.document_type_id.name)
            
            # Save XML content
            self.xml_content = xml_content
            self.xml_filename = f"{self.document_type_id.code}_{self.partner_id.nit_gt or 'CF'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
            self.xml_file = base64.b64encode(xml_content.encode('utf-8'))
            self.generation_date = fields.Datetime.now()
            self.state = 'generated'
            
            _logger.info(f"XML generated successfully for FEL document {self.id}")
            
        except Exception as e:
            self.state = 'error'
            self.error_message = str(e)
            _logger.error(f"XML generation failed for FEL document {self.id}: {str(e)}")
            raise
    
    def _generate_invoice_xml(self, fel_config):
        """Generate XML for invoice documents (FACT, FPEQ, etc.)"""
        source_doc = self.invoice_id or self.pos_order_id
        if not source_doc:
            raise ValidationError(_('Invoice or POS order is required for this document type.'))
        
        # Create XML structure according to Guatemala FEL specification
        root = ET.Element('dte:GTDocumento')
        root.set('xmlns:dte', 'http://www.sat.gob.gt/dte/fel/0.2.0')
        root.set('xmlns:xsi', 'http://www.w3.org/2001/XMLSchema-instance')
        root.set('Version', '0.1')
        
        # SAT element
        sat = ET.SubElement(root, 'dte:SAT')
        sat.set('ClaseDocumento', 'dte')
        
        # DTE element
        dte = ET.SubElement(sat, 'dte:DTE')
        dte.set('ID', 'DatosCertificados')
        
        # DatosEmision
        datos_emision = ET.SubElement(dte, 'dte:DatosEmision')
        datos_emision.set('ID', 'DatosEmision')
        
        # DatosGenerales
        datos_generales = ET.SubElement(datos_emision, 'dte:DatosGenerales')
        datos_generales.set('Tipo', self.document_type_id.code)
        
        # Format date according to FEL requirements
        if self.invoice_id:
            doc_date = self.invoice_id.invoice_date
            currency = self.invoice_id.currency_id.name
        else:  # POS order
            doc_date = self.pos_order_id.date_order.date()
            currency = self.pos_order_id.currency_id.name
            
        invoice_datetime = datetime.combine(doc_date, datetime.min.time())
        fecha_emision = invoice_datetime.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + '-06:00'
        datos_generales.set('FechaHoraEmision', fecha_emision)
        datos_generales.set('CodigoMoneda', currency)
        
        # Emisor (Company/Issuer)
        emisor = ET.SubElement(datos_emision, 'dte:Emisor')
        emisor.set('NITEmisor', fel_config.nit)
        emisor.set('NombreEmisor', fel_config.commercial_name or self.company_id.name)
        emisor.set('CodigoEstablecimiento', fel_config.establishment_code or '1')
        emisor.set('NombreComercial', fel_config.commercial_name or self.company_id.name)
        
        # DireccionEmisor
        direccion_emisor = ET.SubElement(emisor, 'dte:DireccionEmisor')
        ET.SubElement(direccion_emisor, 'dte:Direccion').text = fel_config.address_line or self.company_id.street or ''
        ET.SubElement(direccion_emisor, 'dte:CodigoPostal').text = fel_config.postal_code or '01001'
        ET.SubElement(direccion_emisor, 'dte:Municipio').text = fel_config.municipality or 'Guatemala'
        ET.SubElement(direccion_emisor, 'dte:Departamento').text = fel_config.department or 'Guatemala'
        ET.SubElement(direccion_emisor, 'dte:Pais').text = fel_config.country_code or 'GT'
        
        # Receptor (Customer)
        receptor = ET.SubElement(datos_emision, 'dte:Receptor')
        receptor.set('IDReceptor', self.partner_id.nit_gt or 'CF')
        receptor.set('NombreReceptor', self.partner_id.name)
        
        # Add address only if not Consumidor Final
        if self.partner_id.nit_gt and self.partner_id.nit_gt != 'CF':
            direccion_receptor = ET.SubElement(receptor, 'dte:DireccionReceptor')
            ET.SubElement(direccion_receptor, 'dte:Direccion').text = self.partner_id.street or ''
            ET.SubElement(direccion_receptor, 'dte:CodigoPostal').text = self.partner_id.zip or '01001'
            ET.SubElement(direccion_receptor, 'dte:Municipio').text = self.partner_id.city or 'Guatemala'
            ET.SubElement(direccion_receptor, 'dte:Departamento').text = (self.partner_id.state_id.name if self.partner_id.state_id else 'Guatemala')
            ET.SubElement(direccion_receptor, 'dte:Pais').text = 'GT'
        
        # Items
        items = ET.SubElement(datos_emision, 'dte:Items')
        if self.invoice_id:
            self._add_invoice_items_to_xml(items)
        else:
            self._add_pos_items_to_xml(items)
        
        # Totales
        totales = ET.SubElement(datos_emision, 'dte:Totales')
        self._add_totals_to_xml(totales)
        
        return ET.tostring(root, encoding='unicode', method='xml')
    
    def _add_invoice_items_to_xml(self, items_element):
        """Add invoice line items to XML"""
        line_number = 1
        
        for line in self.invoice_id.invoice_line_ids.filtered(lambda l: not l.display_type):
            item = ET.SubElement(items_element, 'dte:Item')
            item.set('NumeroLinea', str(line_number))
            item.set('BienOServicio', 'S' if line.product_id.type == 'service' else 'B')
            
            ET.SubElement(item, 'dte:Cantidad').text = str(line.quantity)
            ET.SubElement(item, 'dte:UnidadMedida').text = 'UNI'
            ET.SubElement(item, 'dte:Descripcion').text = line.name or (line.product_id.name if line.product_id else '')
            ET.SubElement(item, 'dte:PrecioUnitario').text = f"{line.price_unit:.6f}"
            ET.SubElement(item, 'dte:Precio').text = f"{line.price_subtotal:.2f}"
            ET.SubElement(item, 'dte:Descuento').text = f"{line.discount:.2f}"
            
            # Impuestos (Taxes)
            impuestos = ET.SubElement(item, 'dte:Impuestos')
            
            # Add IVA if applicable
            for tax in line.tax_ids:
                if tax.amount > 0:  # IVA
                    impuesto = ET.SubElement(impuestos, 'dte:Impuesto')
                    ET.SubElement(impuesto, 'dte:NombreCorto').text = 'IVA'
                    ET.SubElement(impuesto, 'dte:CodigoUnidadGravable').text = '1'
                    ET.SubElement(impuesto, 'dte:MontoGravable').text = f"{line.price_subtotal:.2f}"
                    ET.SubElement(impuesto, 'dte:MontoImpuesto').text = f"{line.price_total - line.price_subtotal:.2f}"
            
            ET.SubElement(item, 'dte:Total').text = f"{line.price_total:.2f}"
            line_number += 1
    
    def _add_pos_items_to_xml(self, items_element):
        """Add POS order line items to XML"""
        line_number = 1
        
        for line in self.pos_order_id.lines:
            item = ET.SubElement(items_element, 'dte:Item')
            item.set('NumeroLinea', str(line_number))
            item.set('BienOServicio', 'S' if line.product_id.type == 'service' else 'B')
            
            ET.SubElement(item, 'dte:Cantidad').text = str(line.qty)
            ET.SubElement(item, 'dte:UnidadMedida').text = 'UNI'
            ET.SubElement(item, 'dte:Descripcion').text = line.product_id.name
            ET.SubElement(item, 'dte:PrecioUnitario').text = f"{line.price_unit:.6f}"
            ET.SubElement(item, 'dte:Precio').text = f"{line.price_subtotal:.2f}"
            ET.SubElement(item, 'dte:Descuento').text = f"{line.discount:.2f}"
            
            # Impuestos (Taxes) for POS
            impuestos = ET.SubElement(item, 'dte:Impuestos')
            
            # Calculate tax for POS line
            tax_amount = line.price_subtotal_incl - line.price_subtotal
            if tax_amount > 0:
                impuesto = ET.SubElement(impuestos, 'dte:Impuesto')
                ET.SubElement(impuesto, 'dte:NombreCorto').text = 'IVA'
                ET.SubElement(impuesto, 'dte:CodigoUnidadGravable').text = '1'
                ET.SubElement(impuesto, 'dte:MontoGravable').text = f"{line.price_subtotal:.2f}"
                ET.SubElement(impuesto, 'dte:MontoImpuesto').text = f"{tax_amount:.2f}"
            
            ET.SubElement(item, 'dte:Total').text = f"{line.price_subtotal_incl:.2f}"
            line_number += 1
    
    def _add_totals_to_xml(self, totales_element):
        """Add totals section to XML"""
        # TotalImpuestos
        total_impuestos = ET.SubElement(totales_element, 'dte:TotalImpuestos')
        
        # Calculate total IVA
        if self.invoice_id:
            total_iva = sum(line.price_total - line.price_subtotal 
                           for line in self.invoice_id.invoice_line_ids.filtered(lambda l: not l.display_type))
            grand_total = self.invoice_id.amount_total
        else:  # POS order
            total_iva = sum(line.price_subtotal_incl - line.price_subtotal for line in self.pos_order_id.lines)
            grand_total = self.pos_order_id.amount_total
        
        if total_iva > 0:
            total_impuesto = ET.SubElement(total_impuestos, 'dte:TotalImpuesto')
            total_impuesto.set('NombreCorto', 'IVA')
            total_impuesto.set('TotalMontoImpuesto', f"{total_iva:.2f}")
        
        ET.SubElement(totales_element, 'dte:GranTotal').text = f"{grand_total:.2f}"
    
    def _generate_credit_note_xml(self, fel_config):
        """Generate XML for credit note"""
        # Credit note uses same structure as invoice but with different document type
        return self._generate_invoice_xml(fel_config)
    
    def _generate_debit_note_xml(self, fel_config):
        """Generate XML for debit note"""
        # Debit note uses same structure as invoice but with different document type
        return self._generate_invoice_xml(fel_config)
    
    def send_to_provider(self):
        """Send XML to FEL provider"""
        self.ensure_one()
        
        if not self.xml_content:
            raise ValidationError(_('XML content is required. Generate XML first.'))
        
        try:
            self.state = 'sending'
            
            # Get FEL configuration
            fel_config = self.env['fel.config'].get_active_config(self.company_id.id)
            
            # Send to provider based on type
            if fel_config.provider_id.code == 'infile':
                result = self._send_to_infile(fel_config)
            else:
                result = self._send_to_generic_provider(fel_config)
            
            # Process result
            if result.get('success'):
                self.uuid = result.get('uuid')
                self.series = result.get('series')
                self.number = result.get('number')
                self.certification_date = fields.Datetime.now()
                self.provider_response = result.get('response', '')
                self.state = 'certified'
                
                # Update related invoice/POS order
                if self.invoice_id:
                    self.invoice_id.write({
                        'fel_uuid': self.uuid,
                        'fel_series': self.series,
                        'fel_number': self.number,
                        'fel_status': 'certified',
                        'fel_certification_date': self.certification_date,
                    })
                elif self.pos_order_id:
                    self.pos_order_id.write({
                        'fel_uuid': self.uuid,
                        'fel_status': 'certified',
                    })
                    
                _logger.info(f"FEL document {self.id} certified successfully with UUID: {self.uuid}")
                
            else:
                self.state = 'error'
                self.error_message = result.get('error', 'Unknown error')
                _logger.error(f"FEL certification failed for document {self.id}: {self.error_message}")
                
        except Exception as e:
            self.state = 'error'
            self.error_message = str(e)
            _logger.error(f"Failed to send FEL document {self.id}: {str(e)}")
            raise
    
    def _send_to_infile(self, fel_config):
        """Send to INFILE provider"""
        try:
            url = f"{fel_config.api_url}/api/v1/dte/certify"
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }
            
            # Add authentication
            if fel_config.api_token:
                headers['Authorization'] = f'Bearer {fel_config.api_token}'
            elif fel_config.api_username and fel_config.api_password:
                import base64
                credentials = base64.b64encode(f"{fel_config.api_username}:{fel_config.api_password}".encode()).decode()
                headers['Authorization'] = f'Basic {credentials}'
            
            data = {
                'nit_emisor': fel_config.nit,
                'xml_content': self.xml_content,
                'environment': fel_config.environment,
                'document_type': self.document_type_id.code,
            }
            
            _logger.info(f"Sending FEL document {self.id} to INFILE")
            
            response = requests.post(url, json=data, headers=headers, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            _logger.info(f"INFILE response for document {self.id}: {result}")
            
            # Parse INFILE response
            if result.get('success') or result.get('resultado'):
                return {
                    'success': True,
                    'uuid': result.get('uuid') or result.get('uuid_documento'),
                    'series': result.get('serie') or result.get('series'),
                    'number': result.get('numero') or result.get('number'),
                    'response': str(result),
                }
            else:
                return {
                    'success': False,
                    'error': result.get('mensaje') or result.get('descripcion_errores') or 'Unknown error from INFILE',
                }
                
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Request timeout'}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f'Request error: {str(e)}'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _send_to_generic_provider(self, fel_config):
        """Send to generic provider"""
        return {
            'success': False,
            'error': f'Provider {fel_config.provider_id.name} not implemented',
        }
    
    def action_generate_xml(self):
        """Action to generate XML - can be called from buttons"""
        self.generate_xml()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('XML Generated'),
                'message': _('XML generated successfully for document %s') % self.name,
                'type': 'success',
            }
        }
    
    def action_send_to_provider(self):
        """Action to send to provider - can be called from buttons"""
        self.send_to_provider()
        if self.state == 'certified':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('FEL Certified'),
                    'message': _('Document certified successfully. UUID: %s') % self.uuid,
                    'type': 'success',
                }
            }
    
    def action_download_xml(self):
        """Download XML file"""
        self.ensure_one()
        if not self.xml_file:
            raise ValidationError(_('No XML file available for download.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=fel.document&id={self.id}&field=xml_file&download=true&filename={self.xml_filename}',
            'target': 'self',
        }
    
    def action_download_pdf(self):
        """Download PDF file"""
        self.ensure_one()
        if not self.pdf_file:
            raise ValidationError(_('No PDF file available for download.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model=fel.document&id={self.id}&field=pdf_file&download=true&filename={self.pdf_filename}',
            'target': 'self',
        }
    
    def retry_processing(self):
        """Retry processing after fixing errors"""
        self.ensure_one()
        
        if self.state not in ['error']:
            raise ValidationError(_('Can only retry processing for documents with errors.'))
        
        # Reset error state
        self.write({
            'state': 'draft',
            'error_message': False,
        })
        
        # Try to generate and send again
        try:
            self.generate_xml()
            self.send_to_provider()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Processing Retried'),
                    'message': _('Document processing completed successfully.'),
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Retry Failed'),
                    'message': _('Processing failed again: %s') % str(e),
                    'type': 'warning',
                }
            }
    
    def cancel_document(self):
        """Cancel FEL document"""
        self.ensure_one()
        
        if self.state != 'certified':
            raise ValidationError(_('Only certified documents can be cancelled.'))
        
        try:
            # This would implement cancellation with SAT through provider
            # For now, just mark as cancelled locally
            self.state = 'cancelled'
            
            # Update related records
            if self.invoice_id:
                self.invoice_id.fel_status = 'cancelled'
            elif self.pos_order_id:
                self.pos_order_id.fel_status = 'cancelled'
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Document Cancelled'),
                    'message': _('FEL document has been cancelled.'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise ValidationError(_('Failed to cancel document: %s') % str(e))
    
    def get_portal_url(self):
        """Get URL to view document on provider portal"""
        self.ensure_one()
        
        if not self.uuid:
            return False
        
        try:
            fel_config = self.env['fel.config'].get_active_config(self.company_id.id)
            
            if fel_config.provider_id.code == 'infile':
                # INFILE portal URL format (this would be the actual URL)
                return f"https://portal.infile.com.gt/dte/{self.uuid}"
            
            return False
            
        except Exception:
            return False
    
    @api.model
    def process_pending_documents(self):
        """Cron job to process pending FEL documents"""
        pending_docs = self.search([('state', 'in', ['draft', 'generated'])])
        
        for doc in pending_docs:
            try:
                if doc.state == 'draft':
                    doc.generate_xml()
                if doc.state == 'generated':
                    doc.send_to_provider()
                    
                # Commit after each document to avoid losing progress
                self.env.cr.commit()
                
            except Exception as e:
                _logger.error(f"Failed to process FEL document {doc.id}: {str(e)}")
                doc.write({
                    'state': 'error',
                    'error_message': str(e),
                })
                # Continue with next document
                continue
    
    @api.constrains('invoice_id', 'pos_order_id')
    def _check_source_document(self):
        """Ensure only one source document is set"""
        for record in self:
            if record.invoice_id and record.pos_order_id:
                raise ValidationError(_('A FEL document cannot be linked to both an invoice and a POS order.'))
            
            if not record.invoice_id and not record.pos_order_id:
                if record.document_type_id.is_invoice or record.document_type_id.is_credit_note or record.document_type_id.is_debit_note:
                    raise ValidationError(_('Invoice or POS order is required for this document type.'))
    
    def unlink(self):
        """Prevent deletion of certified documents"""
        for record in self:
            if record.state == 'certified':
                raise ValidationError(_('Cannot delete certified FEL documents. Cancel them first if needed.'))
        return super().unlink()
