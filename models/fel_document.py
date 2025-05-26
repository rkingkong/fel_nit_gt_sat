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
    
    name = fields.Char(string='Name', compute='_compute_name', store=True)
    
    # Document Information
    document_type_id = fields.Many2one(
        'fel.document.type',
        string='Document Type',
        required=True
    )
    
    # Related Records
    invoice_id = fields.Many2one('account.move', string='Invoice')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True)
    
    # FEL Specific Fields
    uuid = fields.Char(string='UUID', readonly=True)
    series = fields.Char(string='Series', readonly=True)
    number = fields.Char(string='Number', readonly=True)
    
    # XML and PDF
    xml_content = fields.Text(string='XML Content')
    xml_file = fields.Binary(string='XML File')
    xml_filename = fields.Char(string='XML Filename')
    
    pdf_file = fields.Binary(string='PDF File')
    pdf_filename = fields.Char(string='PDF Filename')
    
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
    ], string='State', default='draft', readonly=True)
    
    error_message = fields.Text(string='Error Message', readonly=True)
    
    # Provider Response
    provider_response = fields.Text(string='Provider Response', readonly=True)
    sat_response = fields.Text(string='SAT Response', readonly=True)
    
    # Dates
    generation_date = fields.Datetime(string='Generation Date', readonly=True)
    certification_date = fields.Datetime(string='Certification Date', readonly=True)
    
    @api.depends('document_type_id', 'partner_id', 'invoice_id')
    def _compute_name(self):
        for record in self:
            if record.invoice_id:
                record.name = f"{record.document_type_id.code} - {record.invoice_id.name}"
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
            self.xml_filename = f"{self.document_type_id.code}_{self.partner_id.nit_gt}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
            self.xml_file = base64.b64encode(xml_content.encode('utf-8'))
            self.generation_date = fields.Datetime.now()
            self.state = 'generated'
            
        except Exception as e:
            self.state = 'error'
            self.error_message = str(e)
            _logger.error(f"XML generation failed for FEL document {self.id}: {str(e)}")
            raise
    
    def _generate_invoice_xml(self, fel_config):
        """Generate XML for invoice documents"""
        if not self.invoice_id:
            raise ValidationError(_('Invoice is required for this document type.'))
        
        # XML structure for Guatemala FEL
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
        datos_generales.set('FechaHoraEmision', self.invoice_id.invoice_date.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + '-06:00')
        datos_generales.set('CodigoMoneda', self.invoice_id.currency_id.name)
        
        # Emisor
        emisor = ET.SubElement(datos_emision, 'dte:Emisor')
        emisor.set('NITEmisor', fel_config.nit)
        emisor.set('NombreEmisor', self.company_id.name)
        emisor.set('CodigoEstablecimiento', '1')
        emisor.set('NombreComercial', self.company_id.name)
        
        # DireccionEmisor
        direccion_emisor = ET.SubElement(emisor, 'dte:DireccionEmisor')
        ET.SubElement(direccion_emisor, 'dte:Direccion').text = self.company_id.street or ''
        ET.SubElement(direccion_emisor, 'dte:CodigoPostal').text = self.company_id.zip or '01001'
        ET.SubElement(direccion_emisor, 'dte:Municipio').text = self.company_id.city or 'Guatemala'
        ET.SubElement(direccion_emisor, 'dte:Departamento').text = self.company_id.state_id.name or 'Guatemala'
        ET.SubElement(direccion_emisor, 'dte:Pais').text = 'GT'
        
        # Receptor
        receptor = ET.SubElement(datos_emision, 'dte:Receptor')
        receptor.set('IDReceptor', self.partner_id.nit_gt or 'CF')
        receptor.set('NombreReceptor', self.partner_id.name)
        
        if self.partner_id.nit_gt and self.partner_id.nit_gt != 'CF':
            # DireccionReceptor
            direccion_receptor = ET.SubElement(receptor, 'dte:DireccionReceptor')
            ET.SubElement(direccion_receptor, 'dte:Direccion').text = self.partner_id.street or ''
            ET.SubElement(direccion_receptor, 'dte:CodigoPostal').text = self.partner_id.zip or '01001'
            ET.SubElement(direccion_receptor, 'dte:Municipio').text = self.partner_id.city or 'Guatemala'
            ET.SubElement(direccion_receptor, 'dte:Departamento').text = self.partner_id.state_id.name or 'Guatemala'
            ET.SubElement(direccion_receptor, 'dte:Pais').text = 'GT'
        
        # Items
        items = ET.SubElement(datos_emision, 'dte:Items')
        
        line_number = 1
        for line in self.invoice_id.invoice_line_ids.filtered(lambda l: not l.display_type):
            item = ET.SubElement(items, 'dte:Item')
            item.set('NumeroLinea', str(line_number))
            item.set('BienOServicio', 'S' if line.product_id.type == 'service' else 'B')
            
            ET.SubElement(item, 'dte:Cantidad').text = str(line.quantity)
            ET.SubElement(item, 'dte:UnidadMedida').text = 'UNI'
            ET.SubElement(item, 'dte:Descripcion').text = line.name or line.product_id.name
            ET.SubElement(item, 'dte:PrecioUnitario').text = f"{line.price_unit:.6f}"
            ET.SubElement(item, 'dte:Precio').text = f"{line.price_subtotal:.2f}"
            ET.SubElement(item, 'dte:Descuento').text = f"{line.discount:.2f}"
            
            # Impuestos
            impuestos = ET.SubElement(item, 'dte:Impuestos')
            
            # IVA
            for tax in line.tax_ids:
                if tax.amount > 0:  # IVA
                    impuesto = ET.SubElement(impuestos, 'dte:Impuesto')
                    ET.SubElement(impuesto, 'dte:NombreCorto').text = 'IVA'
                    ET.SubElement(impuesto, 'dte:CodigoUnidadGravable').text = '1'
                    ET.SubElement(impuesto, 'dte:MontoGravable').text = f"{line.price_subtotal:.2f}"
                    ET.SubElement(impuesto, 'dte:MontoImpuesto').text = f"{line.price_total - line.price_subtotal:.2f}"
            
            ET.SubElement(item, 'dte:Total').text = f"{line.price_total:.2f}"
            line_number += 1
        
        # Totales
        totales = ET.SubElement(datos_emision, 'dte:Totales')
        
        # TotalImpuestos
        total_impuestos = ET.SubElement(totales, 'dte:TotalImpuestos')
        
        # Calculate totals
        total_iva = sum(line.price_total - line.price_subtotal for line in self.invoice_id.invoice_line_ids.filtered(lambda l: not l.display_type))
        
        if total_iva > 0:
            total_impuesto = ET.SubElement(total_impuestos, 'dte:TotalImpuesto')
            total_impuesto.set('NombreCorto', 'IVA')
            total_impuesto.set('TotalMontoImpuesto', f"{total_iva:.2f}")
        
        ET.SubElement(totales, 'dte:GranTotal').text = f"{self.invoice_id.amount_total:.2f}"
        
        return ET.tostring(root, encoding='unicode', method='xml')
    
    def _generate_credit_note_xml(self, fel_config):
        """Generate XML for credit note"""
        # Similar structure to invoice but with credit note specifics
        return self._generate_invoice_xml(fel_config)  # Simplified for now
    
    def _generate_debit_note_xml(self, fel_config):
        """Generate XML for debit note"""
        # Similar structure to invoice but with debit note specifics
        return self._generate_invoice_xml(fel_config)  # Simplified for now
    
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
                
                # Update related invoice
                if self.invoice_id:
                    self.invoice_id.write({
                        'fel_uuid': self.uuid,
                        'fel_status': 'certified',
                    })
            else:
                self.state = 'error'
                self.error_message = result.get('error', 'Unknown error')
                
        except Exception as e:
            self.state = 'error'
            self.error_message = str(e)
            _logger.error(f"Failed to send FEL document {self.id}: {str(e)}")
            raise
    
    def _send_to_infile(self, fel_config):
        """Send to INFILE provider"""
        try:
            url = f"{fel_config.api_url}/dte/certify"
            
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {fel_config.api_token}'
            }
            
            data = {
                'nit_emisor': fel_config.nit,
                'xml_content': self.xml_content,
                'environment': fel_config.environment,
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('resultado'):
                return {
                    'success': True,
                    'uuid': result.get('uuid'),
                    'series': result.get('serie'),
                    'number': result.get('numero'),
                    'response': str(result),
                }
            else:
                return {
                    'success': False,
                    'error': result.get('descripcion_errores', 'Unknown error'),
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    def _send_to_generic_provider(self, fel_config):
        """Send to generic provider"""
        return {
            'success': False,
            'error': 'Generic provider not implemented',
        }
