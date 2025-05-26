from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class PosOrder(models.Model):
    _inherit = 'pos.order'
    
    # FEL Integration Fields
    fel_document_id = fields.Many2one(
        'fel.document',
        string='FEL Document',
        readonly=True
    )
    
    fel_uuid = fields.Char(
        string='FEL UUID',
        readonly=True
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
    ], string='FEL Status', default='draft', readonly=True)
    
    customer_nit = fields.Char(
        string='Customer NIT',
        help='NIT del cliente para facturación'
    )
    
    @api.model
    def create(self, vals):
        """Override create to handle FEL requirements"""
        order = super().create(vals)
        
        # Auto-set FEL document type for restaurant orders
        if order.config_id.module_pos_restaurant or order.session_id.config_id.module_pos_restaurant:
            # For restaurant orders, use appropriate document type
            if order.partner_id and order.partner_id.nit_gt:
                if order.partner_id.tax_regime_gt == 'pequeno':
                    doc_type = self.env['fel.document.type'].get_document_type_by_code('FPEQ')
                else:
                    doc_type = self.env['fel.document.type'].get_document_type_by_code('FACT')
            else:
                # For consumidor final
                doc_type = self.env['fel.document.type'].get_document_type_by_code('FACT')
            
            if doc_type:
                order.fel_document_type_id = doc_type.id
        
        return order
    
    def generate_fel_document(self):
        """Generate FEL document for POS order"""
        self.ensure_one()
        
        if not self.fel_document_type_id:
            raise ValidationError(_('FEL Document Type is required.'))
        
        # Validate customer information
        if not self.customer_nit and not self.partner_id.nit_gt:
            # For consumidor final, we can proceed
            customer_nit = 'CF'
        else:
            customer_nit = self.customer_nit or self.partner_id.nit_gt
        
        try:
            # Create FEL document
            fel_doc = self.env['fel.document'].create({
                'pos_order_id': self.id,
                'partner_id': self.partner_id.id or self.env.ref('base.public_partner').id,
                'document_type_id': self.fel_document_type_id.id,
                'company_id': self.company_id.id,
            })
            
            # Generate and send XML
            fel_doc.generate_pos_xml()
            fel_doc.send_to_provider()
            
            # Update POS order
            self.write({
                'fel_document_id': fel_doc.id,
                'fel_status': 'sent',
            })
            
            return fel_doc
            
        except Exception as e:
            self.write({
                'fel_status': 'error',
            })
            raise ValidationError(_('Failed to generate FEL document: %s') % str(e))

class PosConfig(models.Model):
    _inherit = 'pos.config'
    
    # FEL Configuration
    use_fel = fields.Boolean(
        string='Use FEL',
        help='Enable FEL (Electronic Invoice) for this POS'
    )
    
    fel_auto_generate = fields.Boolean(
        string='Auto Generate FEL',
        help='Automatically generate FEL documents when orders are completed'
    )
    
    fel_document_type_id = fields.Many2one(
        'fel.document.type',
        string='Default FEL Document Type'
    )
    
    fel_require_nit = fields.Boolean(
        string='Require Customer NIT',
        help='Require customer NIT for all orders'
    )
