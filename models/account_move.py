# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    # FEL Integration Fields
    fel_document_id = fields.Many2one(
        'fel.document',
        string='FEL Document',
        readonly=True,
        help='Generated FEL document for this invoice'
    )
    
    fel_uuid = fields.Char(
        string='FEL UUID',
        readonly=True,
        help='UUID assigned by SAT for the FEL document'
    )
    
    fel_series = fields.Char(
        string='FEL Series',
        readonly=True,
        help='Series assigned by SAT for the FEL document'
    )
    
    fel_number = fields.Char(
        string='FEL Number',
        readonly=True,
        help='Number assigned by SAT for the FEL document'
    )
    
    fel_document_type_id = fields.Many2one(
        'fel.document.type',
        string='FEL Document Type',
        help='Type of FEL document to generate (FACT, FPEQ, NCRE, etc.)'
    )
    
    fel_status = fields.Selection([
        ('draft', 'Draft'),
        ('generating', 'Generating XML'),
        ('sending', 'Sending to SAT'),
        ('sent', 'Sent to SAT'),
        ('certified', 'Certified by SAT'),
        ('error', 'Error'),
        ('cancelled', 'Cancelled'),
    ], string='FEL Status', default='draft', readonly=True,
       help='Current status of FEL processing')
    
    fel_error_message = fields.Text(
        string='FEL Error Message',
        readonly=True,
        help='Error message if FEL processing failed'
    )
    
    fel_certification_date = fields.Datetime(
        string='FEL Certification Date',
        readonly=True,
        help='Date when the document was certified by SAT'
    )
    
    # Customer information for FEL
    customer_nit = fields.Char(
        string='Customer NIT',
        related='partner_id.nit_gt',
        readonly=True,
        help='Customer NIT for FEL document'
    )
    
    customer_tax_regime = fields.Selection(
        related='partner_id.tax_regime_gt',
        readonly=True,
        help='Customer tax regime'
    )
    
    # Control fields
    requires_fel = fields.Boolean(
        string='Requires FEL',
        compute='_compute_requires_fel',
        help='Whether this invoice requires FEL processing'
    )
    
    can_send_fel = fields.Boolean(
        string='Can Send FEL',
        compute='_compute_can_send_fel',
        help='Whether this invoice can be sent to FEL'
    )
    
    fel_xml_content = fields.Text(
        string='FEL XML Content',
        readonly=True,
        help='Generated XML content for debugging'
    )
    
    @api.depends('move_type', 'state', 'partner_id')
    def _compute_requires_fel(self):
        """Determine if invoice requires FEL processing"""
        for move in self:
            # Only customer invoices and credit notes require FEL
            move.requires_fel = (
                move.move_type in ['out_invoice', 'out_refund'] and
                move.state == 'posted' and
                move.partner_id and
                move.partner_id.country_id.code == 'GT'  # Only for Guatemala
            )
    
    @api.depends('requires_fel', 'fel_status', 'partner_id.nit_gt')
    def _compute_can_send_fel(self):
        """Determine if invoice can be sent to FEL"""
        for move in self:
            move.can_send_fel = (
                move.requires_fel and
                move.fel_status in ['draft', 'error'] and
                bool(move.partner_id.nit_gt)  # Customer must have NIT
            )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set default FEL document type"""
        moves = super().create(vals_list)
        for move in moves:
            if move.requires_fel:
                move._set_default_fel_document_type()
        return moves
    
    def write(self, vals):
        """Override write to handle FEL when invoice is posted"""
        result = super().write(vals)
        
        # Check if invoice was just posted and auto-send is enabled
        if 'state' in vals and vals['state'] == 'posted':
            for move in self:
                if move.requires_fel:
                    move._set_default_fel_document_type()
                    
                    # Auto-send if configured
                    fel_config = self.env['fel.config'].search([
                        ('company_id', '=', move.company_id.id),
                        ('is_active', '=', True)
                    ], limit=1)
                    
                    if fel_config:
                        if (move.move_type == 'out_invoice' and fel_config.auto_send_invoices) or \
                           (move.move_type == 'out_refund' and fel_config.auto_send_credit_notes):
                            try:
                                move.send_to_fel()
                            except Exception as e:
                                _logger.error(f"Auto-send FEL failed for invoice {move.name}: {str(e)}")
        
        return result
    
    def _set_default_fel_document_type(self):
        """Set default FEL document type based on move type and partner"""
        self.ensure_one()
        
        if not self.fel_document_type_id:
            doc_type_model = self.env['fel.document.type']
            
            if self.move_type == 'out_invoice':
                # Determine invoice type based on partner's tax regime
                if self.partner_id.tax_regime_gt == 'pequeno':
                    doc_type = doc_type_model.get_document_type_by_code('FPEQ')
                elif self.partner_id.tax_regime_gt == 'especial':
                    doc_type = doc_type_model.get_document_type_by_code('FESP')
                else:
                    doc_type = doc_type_model.get_document_type_by_code('FACT')
                    
            elif self.move_type == 'out_refund':
                doc_type = doc_type_model.get_document_type_by_code('NCRE')
            else:
                return
            
            if doc_type:
                self.fel_document_type_id = doc_type.id
    
    def send_to_fel(self):
        """Send invoice to FEL provider"""
        self.ensure_one()
        
        # Validations
        if not self.can_send_fel:
            raise ValidationError(_('This invoice cannot be sent to FEL. Please check the requirements.'))
        
        if not self.fel_document_type_id:
            raise ValidationError(_('FEL Document Type is required.'))
        
        if not self.partner_id.nit_gt:
            raise ValidationError(_('Customer NIT is required for FEL. Please verify the customer information.'))
        
        # Validate customer NIT if not already verified
        if not self.partner_id.is_fel_verified and self.partner_id.nit_gt != 'CF':
            try:
                self.partner_id.verify_nit_with_sat()
                if not self.partner_id.is_fel_verified:
                    raise ValidationError(_('Customer NIT verification failed. Please verify the NIT before sending to FEL.'))
            except Exception as e:
                raise ValidationError(_('Customer NIT verification failed: %s') % str(e))
        
        try:
            # Get FEL configuration
            fel_config = self.env['fel.config'].get_active_config(self.company_id.id)
            
            # Check DTE limits
            if fel_config.annual_dte_count >= fel_config.annual_dte_limit:
                raise ValidationError(_('Annual DTE limit (%s) has been reached. Please contact your FEL provider.') % fel_config.annual_dte_limit)
            
            # Create or get existing FEL document
            fel_doc = self.fel_document_id
            if not fel_doc:
                fel_doc = self.env['fel.document'].create({
                    'invoice_id': self.id,
                    'partner_id': self.partner_id.id,
                    'document_type_id': self.fel_document_type_id.id,
                    'company_id': self.company_id.id,
                })
                self.fel_document_id = fel_doc.id
            
            # Update status
            self.fel_status = 'generating'
            
            # Generate XML
            fel_doc.generate_xml()
            
            # Send to provider
            self.fel_status = 'sending'
            fel_doc.send_to_provider()
            
            # Update invoice with results
            if fel_doc.state == 'certified':
                self.write({
                    'fel_status': 'certified',
                    'fel_uuid': fel_doc.uuid,
                    'fel_series': fel_doc.series,
                    'fel_number': fel_doc.number,
                    'fel_certification_date': fel_doc.certification_date,
                    'fel_xml_content': fel_doc.xml_content,
                })
                
                # Increment DTE counter
                fel_config.increment_dte_count()
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('FEL Success'),
                        'message': _('Invoice %s sent to FEL successfully. UUID: %s') % (self.name, fel_doc.uuid),
                        'type': 'success',
                    }
                }
            else:
                self.write({
                    'fel_status': 'error',
                    'fel_error_message': fel_doc.error_message,
                })
                raise ValidationError(_('FEL processing failed: %s') % fel_doc.error_message)
                
        except Exception as e:
            self.write({
                'fel_status': 'error',
                'fel_error_message': str(e),
            })
            _logger.error(f"FEL processing failed for invoice {self.name}: {str(e)}")
            raise ValidationError(_('Failed to send to FEL: %s') % str(e))
    
    def action_send_fel(self):
        """Action to send invoice to FEL - can be called from buttons"""
        return self.send_to_fel()
    
    def view_fel_document(self):
        """View the FEL document"""
        self.ensure_one()
        
        if not self.fel_document_id:
            raise ValidationError(_('No FEL document found for this invoice.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('FEL Document'),
            'res_model': 'fel.document',
            'res_id': self.fel_document_id.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_view_fel_document(self):
        """Action to view FEL document - can be called from buttons"""
        return self.view_fel_document()
    
    def retry_fel(self):
        """Retry FEL processing after fixing errors"""
        self.ensure_one()
        
        if self.fel_status not in ['error']:
            raise ValidationError(_('FEL can only be retried for invoices with errors.'))
        
        # Reset status and retry
        self.write({
            'fel_status': 'draft',
            'fel_error_message': False,
        })
        
        return self.send_to_fel()
    
    def cancel_fel(self):
        """Cancel FEL document with SAT"""
        self.ensure_one()
        
        if not self.fel_document_id or self.fel_status != 'certified':
            raise ValidationError(_('Only certified FEL documents can be cancelled.'))
        
        try:
            # This would implement FEL cancellation with SAT
            # For now, just mark as cancelled locally
            self.write({
                'fel_status': 'cancelled',
            })
            
            if self.fel_document_id:
                self.fel_document_id.state = 'cancelled'
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('FEL Cancelled'),
                    'message': _('FEL document cancelled successfully.'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise ValidationError(_('Failed to cancel FEL: %s') % str(e))
    
    def get_fel_url(self):
        """Get URL to view FEL document on provider portal"""
        self.ensure_one()
        
        if not self.fel_uuid:
            return False
        
        # This would return the provider's portal URL
        # Implementation depends on provider
        try:
            fel_config = self.env['fel.config'].get_active_config(self.company_id.id)
            
            if fel_config.provider_id.code == 'infile':
                # INFILE portal URL format
                base_url = "https://portal.infile.com.gt"
                return f"{base_url}/dte/{self.fel_uuid}"
            
            return False
            
        except Exception:
            return False
    
    @api.onchange('partner_id')
    def _onchange_partner_fel(self):
        """Update FEL fields when partner changes"""
        if self.partner_id and self.move_type in ['out_invoice', 'out_refund']:
            # Reset FEL document type to recalculate based on new partner
            self.fel_document_type_id = False
            self._set_default_fel_document_type()
    
    @api.onchange('fel_document_type_id')
    def _onchange_fel_document_type(self):
        """Validate document type compatibility with partner"""
        if self.fel_document_type_id and self.partner_id:
            doc_type = self.fel_document_type_id
            partner_regime = self.partner_id.tax_regime_gt or 'general'
            
            # Check if document type is available for partner's tax regime
            if partner_regime == 'general' and not doc_type.available_for_general:
                return {
                    'warning': {
                        'title': _('Incompatible Document Type'),
                        'message': _('Document type "%s" is not available for General tax regime.') % doc_type.name
                    }
                }
            elif partner_regime == 'pequeno' and not doc_type.available_for_pequeno:
                return {
                    'warning': {
                        'title': _('Incompatible Document Type'),
                        'message': _('Document type "%s" is not available for Pequeño Contribuyente regime.') % doc_type.name
                    }
                }
            elif partner_regime == 'especial' and not doc_type.available_for_especial:
                return {
                    'warning': {
                        'title': _('Incompatible Document Type'),
                        'message': _('Document type "%s" is not available for Special tax regime.') % doc_type.name
                    }
                }
    
    def _get_fel_document_lines(self):
        """Get invoice lines formatted for FEL XML generation"""
        self.ensure_one()
        
        lines = []
        line_number = 1
        
        for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
            # Calculate tax amounts
            tax_amount = 0
            tax_rate = 0
            
            for tax in line.tax_ids:
                if tax.amount > 0:  # IVA
                    tax_rate = tax.amount
                    tax_amount = line.price_total - line.price_subtotal
                    break
            
            line_data = {
                'line_number': line_number,
                'product_type': 'S' if line.product_id.type == 'service' else 'B',
                'quantity': line.quantity,
                'unit_measure': 'UNI',  # Default unit
                'description': line.name or (line.product_id.name if line.product_id else ''),
                'unit_price': line.price_unit,
                'subtotal': line.price_subtotal,
                'discount': line.discount,
                'tax_rate': tax_rate,
                'tax_amount': tax_amount,
                'total': line.price_total,
            }
            
            lines.append(line_data)
            line_number += 1
        
        return lines
    
    def _get_fel_totals(self):
        """Get invoice totals formatted for FEL XML"""
        self.ensure_one()
        
        # Calculate tax totals
        total_iva = 0
        for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
            line_tax = line.price_total - line.price_subtotal
            total_iva += line_tax
        
        return {
            'subtotal': self.amount_untaxed,
            'total_tax': total_iva,
            'grand_total': self.amount_total,
            'currency': self.currency_id.name,
        }
    
    def _prepare_fel_data(self):
        """Prepare all data needed for FEL XML generation"""
        self.ensure_one()
        
        fel_config = self.env['fel.config'].get_active_config(self.company_id.id)
        
        # Issuer data (company)
        issuer_data = {
            'nit': fel_config.nit,
            'name': fel_config.commercial_name or self.company_id.name,
            'commercial_name': fel_config.commercial_name or self.company_id.name,
            'establishment_code': fel_config.establishment_code or '1',
            'address': fel_config.address_line or self.company_id.street or '',
            'postal_code': fel_config.postal_code or self.company_id.zip or '01001',
            'municipality': fel_config.municipality or self.company_id.city or 'Guatemala',
            'department': fel_config.department or (self.company_id.state_id.name if self.company_id.state_id else 'Guatemala'),
            'country': fel_config.country_code or 'GT',
        }
        
        # Receiver data (customer)
        receiver_data = {
            'nit': self.partner_id.nit_gt or 'CF',
            'name': self.partner_id.name,
            'address': self.partner_id.street or '',
            'postal_code': self.partner_id.zip or '01001',
            'municipality': self.partner_id.city or 'Guatemala',
            'department': self.partner_id.state_id.name if self.partner_id.state_id else 'Guatemala',
            'country': 'GT',
        }
        
        # Document data
        document_data = {
            'type': self.fel_document_type_id.code,
            'date': self.invoice_date,
            'currency': self.currency_id.name,
            'lines': self._get_fel_document_lines(),
            'totals': self._get_fel_totals(),
        }
        
        return {
            'issuer': issuer_data,
            'receiver': receiver_data,
            'document': document_data,
        }
