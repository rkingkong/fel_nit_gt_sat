# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = 'pos.order'
    
    # FEL Integration Fields
    fel_document_id = fields.Many2one(
        'fel.document',
        string='FEL Document',
        readonly=True,
        help='Generated FEL document for this POS order'
    )
    
    fel_uuid = fields.Char(
        string='FEL UUID',
        readonly=True,
        help='UUID assigned by SAT for the FEL document'
    )
    
    fel_series = fields.Char(
        string='FEL Series',
        readonly=True,
        help='Series assigned by SAT'
    )
    
    fel_number = fields.Char(
        string='FEL Number',
        readonly=True,
        help='Number assigned by SAT'
    )
    
    fel_document_type_id = fields.Many2one(
        'fel.document.type',
        string='FEL Document Type',
        help='Type of FEL document to generate'
    )
    
    fel_status = fields.Selection([
        ('draft', 'Draft'),
        ('generating', 'Generating'),
        ('sending', 'Sending'),
        ('sent', 'Sent'),
        ('certified', 'Certified'),
        ('error', 'Error'),
        ('cancelled', 'Cancelled'),
    ], string='FEL Status', default='draft', readonly=True,
       help='Current FEL processing status')
    
    fel_error_message = fields.Text(
        string='FEL Error Message',
        readonly=True,
        help='Error message if FEL processing failed'
    )
    
    fel_certification_date = fields.Datetime(
        string='FEL Certification Date',
        readonly=True,
        help='Date when certified by SAT'
    )
    
    # Customer information for FEL
    customer_nit = fields.Char(
        string='Customer NIT',
        help='Customer NIT for FEL document'
    )
    
    customer_name = fields.Char(
        string='Customer Name',
        help='Customer name for FEL document'
    )
    
    # Control fields
    requires_fel = fields.Boolean(
        string='Requires FEL',
        compute='_compute_requires_fel',
        help='Whether this order requires FEL processing'
    )
    
    can_send_fel = fields.Boolean(
        string='Can Send FEL',
        compute='_compute_can_send_fel',
        help='Whether this order can be sent to FEL'
    )
    
    # Restaurant specific fields
    table_number = fields.Char(
        string='Table Number',
        help='Restaurant table number'
    )
    
    waiter_id = fields.Many2one(
        'res.users',
        string='Waiter',
        help='Waiter who served this table'
    )
    
    @api.depends('state', 'config_id')
    def _compute_requires_fel(self):
        """Determine if order requires FEL processing"""
        for order in self:
            # Only paid orders in Guatemala require FEL
            order.requires_fel = (
                order.state in ['paid', 'done', 'invoiced'] and
                order.config_id.use_fel and
                order.company_id.country_id.code == 'GT'
            )
    
    @api.depends('requires_fel', 'fel_status', 'customer_nit', 'partner_id')
    def _compute_can_send_fel(self):
        """Determine if order can be sent to FEL"""
        for order in self:
            # Can send if requires FEL, not already processed, and has customer info
            has_customer_info = (
                order.customer_nit or 
                order.partner_id.nit_gt or 
                order.customer_nit == 'CF'
            )
            
            order.can_send_fel = (
                order.requires_fel and
                order.fel_status in ['draft', 'error'] and
                has_customer_info
            )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set default FEL document type"""
        orders = super().create(vals_list)
        for order in orders:
            if order.requires_fel:
                order._set_default_fel_document_type()
        return orders
    
    def write(self, vals):
        """Override write to handle FEL when order is paid"""
        result = super().write(vals)
        
        # Check if order was just paid and auto-send is enabled
        if 'state' in vals and vals['state'] in ['paid', 'done']:
            for order in self:
                if order.requires_fel:
                    order._set_default_fel_document_type()
                    
                    # Auto-send if configured
                    fel_config = self.env['fel.config'].search([
                        ('company_id', '=', order.company_id.id),
                        ('is_active', '=', True)
                    ], limit=1)
                    
                    if fel_config and fel_config.auto_send_pos_orders:
                        try:
                            order.send_to_fel()
                        except Exception as e:
                            _logger.error(f"Auto-send FEL failed for POS order {order.name}: {str(e)}")
        
        return result
    
    def _set_default_fel_document_type(self):
        """Set default FEL document type based on customer"""
        self.ensure_one()
        
        if not self.fel_document_type_id:
            # Determine customer tax regime
            tax_regime = 'general'  # Default
            
            if self.partner_id and self.partner_id.tax_regime_gt:
                tax_regime = self.partner_id.tax_regime_gt
            elif self.customer_nit == 'CF':
                tax_regime = 'general'  # CF uses general regime documents
            
            # Get appropriate document type
            doc_type_model = self.env['fel.document.type']
            if tax_regime == 'pequeno':
                doc_type = doc_type_model.get_document_type_by_code('FPEQ')
            elif tax_regime == 'especial':
                doc_type = doc_type_model.get_document_type_by_code('FESP')
            else:
                doc_type = doc_type_model.get_document_type_by_code('FACT')
            
            if doc_type:
                self.fel_document_type_id = doc_type.id
    
    def send_to_fel(self):
        """Send POS order to FEL provider"""
        self.ensure_one()
        
        # Validations
        if not self.can_send_fel:
            raise ValidationError(_('This order cannot be sent to FEL. Please check the requirements.'))
        
        if not self.fel_document_type_id:
            raise ValidationError(_('FEL Document Type is required.'))
        
        # Prepare customer information
        customer_nit = self._get_customer_nit()
        customer_name = self._get_customer_name()
        
        if not customer_nit:
            raise ValidationError(_('Customer NIT is required for FEL. Please set customer information.'))
        
        try:
            # Get FEL configuration
            fel_config = self.env['fel.config'].get_active_config(self.company_id.id)
            
            # Check DTE limits
            if fel_config.annual_dte_count >= fel_config.annual_dte_limit:
                raise ValidationError(_('Annual DTE limit (%s) has been reached. Please contact your FEL provider.') % fel_config.annual_dte_limit)
            
            # Get or create partner for the customer
            partner = self._get_or_create_customer_partner(customer_nit, customer_name)
            
            # Create or get existing FEL document
            fel_doc = self.fel_document_id
            if not fel_doc:
                fel_doc = self.env['fel.document'].create({
                    'pos_order_id': self.id,
                    'partner_id': partner.id,
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
            
            # Update order with results
            if fel_doc.state == 'certified':
                self.write({
                    'fel_status': 'certified',
                    'fel_uuid': fel_doc.uuid,
                    'fel_series': fel_doc.series,
                    'fel_number': fel_doc.number,
                    'fel_certification_date': fel_doc.certification_date,
                })
                
                # Increment DTE counter
                fel_config.increment_dte_count()
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('FEL Success'),
                        'message': _('Order %s sent to FEL successfully. UUID: %s') % (self.name, fel_doc.uuid),
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
            _logger.error(f"FEL processing failed for POS order {self.name}: {str(e)}")
            raise ValidationError(_('Failed to send to FEL: %s') % str(e))
    
    def _get_customer_nit(self):
        """Get customer NIT for FEL"""
        self.ensure_one()
        
        # Priority order: custom NIT, partner NIT, or CF
        if self.customer_nit:
            return self.customer_nit
        elif self.partner_id and self.partner_id.nit_gt:
            return self.partner_id.nit_gt
        else:
            return 'CF'  # Consumidor Final
    
    def _get_customer_name(self):
        """Get customer name for FEL"""
        self.ensure_one()
        
        # Priority order: custom name, partner name, or default
        if self.customer_name:
            return self.customer_name
        elif self.partner_id and self.partner_id.name:
            return self.partner_id.name
        else:
            return 'Consumidor Final'
    
    def _get_or_create_customer_partner(self, nit, name):
        """Get or create partner for customer"""
        self.ensure_one()
        
        # If already has a partner, use it
        if self.partner_id:
            return self.partner_id
        
        # For CF, use the default customer
        if nit == 'CF':
            cf_partner = self.env['res.partner'].search([
                ('nit_gt', '=', 'CF'),
                ('is_company', '=', False)
            ], limit=1)
            
            if not cf_partner:
                cf_partner = self.env['res.partner'].create({
                    'name': 'Consumidor Final',
                    'nit_gt': 'CF',
                    'is_company': False,
                    'customer_rank': 1,
                    'country_id': self.env.ref('base.gt').id,
                })
            
            return cf_partner
        
        # Search for existing partner with this NIT
        partner = self.env['res.partner'].search([
            ('nit_gt', '=', nit)
        ], limit=1)
        
        if partner:
            return partner
        
        # Create new partner
        partner = self.env['res.partner'].create({
            'name': name,
            'nit_gt': nit,
            'is_company': True,
            'customer_rank': 1,
            'country_id': self.env.ref('base.gt').id,
        })
        
        return partner
    
    def action_send_fel(self):
        """Action to send order to FEL - can be called from buttons"""
        return self.send_to_fel()
    
    def view_fel_document(self):
        """View the FEL document"""
        self.ensure_one()
        
        if not self.fel_document_id:
            raise ValidationError(_('No FEL document found for this order.'))
        
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
            raise ValidationError(_('FEL can only be retried for orders with errors.'))
        
        # Reset status and retry
        self.write({
            'fel_status': 'draft',
            'fel_error_message': False,
        })
        
        return self.send_to_fel()
    
    def set_customer_info_wizard(self):
        """Open wizard to set customer information"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Set Customer Information'),
            'res_model': 'pos.order.customer.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_customer_nit': self.customer_nit,
                'default_customer_name': self.customer_name,
            }
        }
    
    @api.onchange('customer_nit')
    def _onchange_customer_nit(self):
        """Auto-fill customer name when NIT changes"""
        if self.customer_nit and self.customer_nit != 'CF':
            # Search for existing partner
            partner = self.env['res.partner'].search([
                ('nit_gt', '=', self.customer_nit)
            ], limit=1)
            
            if partner:
                self.customer_name = partner.name
                self.partner_id = partner.id


class PosConfig(models.Model):
    _inherit = 'pos.config'
    
    # FEL Configuration for POS
    use_fel = fields.Boolean(
        string='Use FEL',
        help='Enable FEL (Electronic Invoice) for this POS'
    )
    
    fel_auto_generate = fields.Boolean(
        string='Auto Generate FEL',
        help='Automatically generate FEL documents when orders are completed',
        default=False
    )
    
    fel_document_type_id = fields.Many2one(
        'fel.document.type',
        string='Default FEL Document Type',
        help='Default document type for this POS'
    )
    
    fel_require_customer = fields.Boolean(
        string='Require Customer Info',
        help='Require customer information for all orders',
        default=False
    )
    
    fel_allow_cf = fields.Boolean(
        string='Allow Consumidor Final',
        help='Allow orders without specific customer (CF)',
        default=True
    )
    
    # Restaurant specific
    is_restaurant = fields.Boolean(
        string='Is Restaurant',
        help='Enable restaurant-specific features'
    )
    
    require_waiter = fields.Boolean(
        string='Require Waiter',
        help='Require waiter selection for orders'
    )


class PosSession(models.Model):
    _inherit = 'pos.session'
    
    def action_pos_session_close(self):
        """Override to process pending FEL documents before closing"""
        
        # Process any pending FEL orders before closing
        if self.config_id.use_fel:
            pending_orders = self.order_ids.filtered(
                lambda o: o.requires_fel and o.fel_status == 'draft'
            )
            
            if pending_orders:
                # Ask user if they want to process pending FEL orders
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Pending FEL Orders'),
                    'res_model': 'pos.session.close.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_session_id': self.id,
                        'pending_fel_count': len(pending_orders),
                    }
                }
        
        return super().action_pos_session_close()
