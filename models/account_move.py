from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountMove(models.Model):
    _inherit = 'account.move'
    
    # FEL Integration Fields
    fel_document_id = fields.Many2one(
        'fel.document',
        string='FEL Document',
        readonly=True
    )
    
    fel_uuid = fields.Char(
        string='FEL UUID',
        readonly=True,
        help='UUID assigned by SAT'
    )
    
    fel_document_type_id = fields.Many2one(
        'fel.document.type',
        string='FEL Document Type'
    )
    
    fel_status = fields.Selection([
        ('draft', 'Draft'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('certified', 'Certified'),
        ('error', 'Error'),
        ('cancelled', 'Cancelled'),
    ], string='FEL Status', default='draft', readonly=True)
    
    fel_error_message = fields.Text(string='FEL Error Message', readonly=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set default FEL document type"""
        moves = super().create(vals_list)
        for move in moves:
            if move.move_type in ['out_invoice', 'out_refund']:
                move._set_default_fel_document_type()
        return moves
    
    def _set_default_fel_document_type(self):
        """Set default FEL document type based on move type and partner"""
        if self.move_type == 'out_invoice':
            # Determine document type based on partner's tax regime
            if self.partner_id.tax_regime_gt == 'pequeno':
                doc_type = self.env['fel.document.type'].get_document_type_by_code('FPEQ')
            else:
                doc_type = self.env['fel.document.type'].get_document_type_by_code('FACT')
            
            if doc_type:
                self.fel_document_type_id = doc_type.id
                
        elif self.move_type == 'out_refund':
            doc_type = self.env['fel.document.type'].get_document_type_by_code('NCRE')
            if doc_type:
                self.fel_document_type_id = doc_type.id
    
    def send_to_fel(self):
        """Send invoice to FEL provider"""
        if not self.fel_document_type_id:
            raise ValidationError(_('FEL Document Type is required.'))
        
        if not self.partner_id.nit_gt:
            raise ValidationError(_('Customer NIT is required for FEL.'))
        
        try:
            # Get FEL configuration
            fel_config = self.env['fel.config'].get_active_config()
            
            # Create FEL document
            fel_doc = self.env['fel.document'].create({
                'invoice_id': self.id,
                'partner_id': self.partner_id.id,
                'document_type_id': self.fel_document_type_id.id,
                'company_id': self.company_id.id,
            })
            
            # Generate and send XML
            fel_doc.generate_xml()
            fel_doc.send_to_provider()
            
            # Update invoice
            self.write({
                'fel_document_id': fel_doc.id,
                'fel_status': 'sent',
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success'),
                    'message': _('Invoice sent to FEL successfully.'),
                    'type': 'success',
                }
            }
            
        except Exception as e:
            self.write({
                'fel_status': 'error',
                'fel_error_message': str(e),
            })
            raise ValidationError(_('Failed to send to FEL: %s') % str(e))
    
    def view_fel_document(self):
        """View FEL document"""
        if not self.fel_document_id:
            raise ValidationError(_('No FEL document found.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('FEL Document'),
            'res_model': 'fel.document',
            'res_id': self.fel_document_id.id,
            'view_mode': 'form',
            'target': 'new',
        }
