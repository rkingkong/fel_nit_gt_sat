# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = 'pos.order'
    
    # FEL related fields
    fel_status = fields.Selection([
        ('draft', 'Draft'),
        ('generating', 'Generating'),
        ('sending', 'Sending'),
        ('certified', 'Certified'),
        ('cancelled', 'Cancelled'),
        ('error', 'Error'),
    ], string='FEL Status', default='draft', readonly=True)
    
    fel_document_id = fields.Many2one(
        'fel.document',
        string='FEL Document',
        readonly=True,
        ondelete='restrict'
    )
    
    fel_uuid = fields.Char(
        string='FEL UUID',
        readonly=True,
        help='Unique identifier from SAT'
    )
    
    fel_series = fields.Char(
        string='FEL Series',
        readonly=True,
        help='Document series from SAT'
    )
    
    fel_number = fields.Char(
        string='FEL Number',
        readonly=True,
        help='Document number from SAT'
    )
    
    fel_xml_file = fields.Binary(
        string='FEL XML',
        readonly=True,
        attachment=True
    )
    
    fel_xml_filename = fields.Char(
        string='XML Filename',
        readonly=True
    )
    
    fel_pdf_file = fields.Binary(
        string='FEL PDF',
        readonly=True,
        attachment=True
    )
    
    fel_pdf_filename = fields.Char(
        string='PDF Filename',
        readonly=True
    )
    
    fel_error_message = fields.Text(
        string='FEL Error',
        readonly=True,
        help='Last error message from FEL processing'
    )
    
    fel_certification_date = fields.Datetime(
        string='Certification Date',
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
        store=True,
        help='Whether this order requires FEL processing'
    )
    
    can_send_fel = fields.Boolean(
        string='Can Send FEL',
        store=True,
        compute='_compute_can_send_fel',
        help='Whether this order can be sent to FEL'
    )
    
    # Related field to access POS config's use_fel
    use_fel = fields.Boolean(
        string='Use FEL',
        related='config_id.use_fel',
        readonly=True,
        help='Indicates if this POS is configured to use FEL'
    )
    
    # Related field to access POS config's is_restaurant
    is_restaurant = fields.Boolean(
        string='Is Restaurant',
        related='config_id.is_restaurant',
        readonly=True,
        help='Indicates if this POS is configured as restaurant'
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

    waiter_name = fields.Char(
        string='Waiter Name',
        related='waiter_id.name',
        readonly=True
    )

    
    @api.depends('state', 'config_id', 'config_id.use_fel' ,'company_id', 'company_id.country_id')
    def _compute_requires_fel(self):
        """Determine if order requires FEL processing"""
        for order in self:
            # Only paid orders in Guatemala require FEL
            order.requires_fel = (
                order.state in ['paid', 'done', 'invoiced'] and
                order.config_id and  # Add null check
                order.config_id.use_fel and
                order.company_id and  # Add null check
                order.company_id.country_id and  # Add null check
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
                    
                    if fel_config and order.config_id.fel_auto_generate:
                        try:
                            order.action_send_fel()
                        except Exception as e:
                            _logger.error(f"Auto-send FEL failed for order {order.name}: {str(e)}")
        
        return result
    
    def _set_default_fel_document_type(self):
        """Set default FEL document type based on configuration"""
        for order in self:
            if not order.fel_document_id and order.config_id.fel_document_type_id:
                # Create FEL document with default type
                fel_doc = self.env['fel.document'].create({
                    'document_type_id': order.config_id.fel_document_type_id.id,
                    'pos_order_id': order.id,
                    'partner_id': order.partner_id.id,
                    'amount_total': order.amount_total,
                })
                order.fel_document_id = fel_doc
    
    def action_send_fel(self):
        """Send order to FEL for certification"""
        self.ensure_one()
        
        if not self.can_send_fel:
            raise UserError(_('This order cannot be sent to FEL at this time.'))
        
        # Check for required customer information
        if not self.customer_nit and not self.partner_id.nit_gt:
            # Open wizard to set customer info
            return self.set_customer_info_wizard()
        
        # Update status
        self.fel_status = 'generating'
        
        try:
            # Generate and send FEL document
            if not self.fel_document_id:
                self._set_default_fel_document_type()
            
            # Prepare FEL document data
            self.fel_document_id.write({
                'customer_nit': self.customer_nit or self.partner_id.nit_gt or 'CF',
                'customer_name': self.customer_name or self.partner_id.name or 'Consumidor Final',
            })
            
            # Send to FEL
            self.fel_status = 'sending'
            self.fel_document_id.action_send()
            
            # Update with results
            if self.fel_document_id.state == 'certified':
                self.write({
                    'fel_status': 'certified',
                    'fel_uuid': self.fel_document_id.uuid,
                    'fel_series': self.fel_document_id.series,
                    'fel_number': self.fel_document_id.number,
                    'fel_certification_date': self.fel_document_id.certification_date,
                    'fel_xml_file': self.fel_document_id.xml_file,
                    'fel_xml_filename': self.fel_document_id.xml_filename,
                    'fel_pdf_file': self.fel_document_id.pdf_file,
                    'fel_pdf_filename': self.fel_document_id.pdf_filename,
                })
                
                # Show success message
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('FEL Success'),
                        'message': _('Order certified successfully. UUID: %s') % self.fel_uuid,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(self.fel_document_id.error_message or _('FEL certification failed'))
                
        except Exception as e:
            self.write({
                'fel_status': 'error',
                'fel_error_message': str(e)
            })
            raise UserError(_('FEL Error: %s') % str(e))
    
    def retry_fel(self):
        """Retry FEL certification after error"""
        self.ensure_one()
        if self.fel_status != 'error':
            raise UserError(_('Can only retry orders with errors.'))
        
        # Reset status and try again
        self.fel_status = 'draft'
        self.fel_error_message = False
        return self.action_send_fel()
    
    def action_view_fel_document(self):
        """View related FEL document"""
        self.ensure_one()
        if not self.fel_document_id:
            raise UserError(_('No FEL document found for this order.'))
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('FEL Document'),
            'res_model': 'fel.document',
            'res_id': self.fel_document_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def set_customer_info_wizard(self):
        """Open wizard to set customer information"""
        self.ensure_one()
        
        # Create wizard with current values
        wizard = self.env['pos.order.customer.wizard'].create({
            'order_id': self.id,
            'customer_nit': self.customer_nit or self.partner_id.nit_gt or '',
            'customer_name': self.customer_name or self.partner_id.name or '',
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Set Customer Information'),
            'res_model': 'pos.order.customer.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_print_fel(self):
        """Print FEL document"""
        self.ensure_one()
        if not self.fel_pdf_file:
            raise UserError(_('No FEL PDF available to print.'))
        
        # Return PDF as download
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/pos.order/%s/fel_pdf_file/%s?download=true' % (
                self.id, self.fel_pdf_filename
            ),
            'target': 'self',
        }
    
    def action_download_fel_xml(self):
        """Download FEL XML file"""
        self.ensure_one()
        if not self.fel_xml_file:
            raise UserError(_('No FEL XML available to download.'))
        
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/pos.order/%s/fel_xml_file/%s?download=true' % (
                self.id, self.fel_xml_filename
            ),
            'target': 'self',
        }
    
    @api.model
    def _process_pending_fel_orders(self):
        """Cron job to process pending FEL orders"""
        # Find orders that need FEL processing
        pending_orders = self.search([
            ('requires_fel', '=', True),
            ('fel_status', '=', 'draft'),
            ('state', 'in', ['paid', 'done', 'invoiced']),
        ])
        
        for order in pending_orders:
            try:
                if order.can_send_fel:
                    order.action_send_fel()
            except Exception as e:
                _logger.error(f"Failed to process FEL for order {order.name}: {str(e)}")
                order.write({
                    'fel_status': 'error',
                    'fel_error_message': str(e)
                })
    
    def _prepare_invoice_vals(self):
        """Add FEL information to invoice when created from POS order"""
        vals = super()._prepare_invoice_vals()
        
        if self.fel_status == 'certified':
            vals.update({
                'fel_uuid': self.fel_uuid,
                'fel_series': self.fel_series,
                'fel_number': self.fel_number,
                'fel_certification_date': self.fel_certification_date,
            })
        
        return vals

    def set_customer_nit_cf(self):
        """Quick action to set customer as Consumidor Final"""
        self.write({
            'customer_nit': 'CF',
            'customer_name': 'Consumidor Final'
        })
        
    def set_customer_from_partner(self):
        """Set customer info from selected partner"""
        if self.partner_id:
            if not self.partner_id.nit_gt:
                raise UserError(_('Selected customer does not have a NIT configured.'))
            
            self.customer_nit = self.partner_id.nit_gt
            self.customer_name = self.partner_id.name
        else:
            raise UserError(_('Please select a customer first.'))