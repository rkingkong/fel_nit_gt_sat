# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class FelDocumentSendWizard(models.TransientModel):
    _name = 'fel.document.send.wizard'
    _description = 'FEL Document Send Wizard'
    
    # All the existing fields remain the same...
    document_ids = fields.Many2many(
        'fel.document',
        string='Documents to Send',
        help='Select documents to send to FEL'
    )
    
    total_documents = fields.Integer(
        string='Total Documents',
        compute='_compute_document_summary',
        store=True
    )
    
    valid_documents = fields.Integer(
        string='Valid Documents',
        compute='_compute_document_summary',
        store=True
    )
    
    invalid_documents = fields.Integer(
        string='Invalid Documents',
        compute='_compute_document_summary',
        store=True
    )
    
    has_pos_orders = fields.Boolean(
        string='Has POS Orders',
        compute='_compute_document_summary',
        store=True
    )
    
    documents_processed = fields.Integer(
        string='Processed',
        readonly=True,
        default=0
    )
    
    documents_success = fields.Integer(
        string='Successful',
        readonly=True,
        default=0
    )
    
    documents_failed = fields.Integer(
        string='Failed',
        readonly=True,
        default=0
    )
    
    processing_log = fields.Html(
        string='Processing Log',
        readonly=True
    )
    
    processing_progress = fields.Float(
        string='Progress',
        compute='_compute_processing_progress',
        store=True
    )
    
    cost_per_dte = fields.Float(
        string='Cost per DTE',
        compute='_compute_estimated_cost',
        store=True
    )
    
    estimated_cost = fields.Float(
        string='Estimated Cost',
        compute='_compute_estimated_cost',
        store=True
    )
    
    ignore_errors = fields.Boolean(
        string='Continue on Error',
        default=False,
        help='Continue processing if individual documents fail'
    )
    
    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")
    partner_ids = fields.Many2many('res.partner', string='Customers')
    
    invoice_ids = fields.Many2many(
        'account.move',
        'fel_send_wizard_invoice_rel',
        'wizard_id',
        'invoice_id',
        string='Invoices to send to FEL',
        domain="[('move_type', 'in', ['out_invoice', 'out_refund']), ('state', '=', 'posted')]"
    )
    
    loaded_invoice_ids = fields.Many2many(
        'account.move',
        'fel_send_wizard_loaded_invoice_rel',
        'wizard_id',
        'invoice_id',
        string='Loaded Invoices'
    )
    
    @api.depends('document_ids')
    def _compute_document_summary(self):
        """Compute document summary statistics"""
        for wizard in self:
            wizard.total_documents = len(wizard.document_ids)
            
            valid_count = 0
            invalid_count = 0
            has_pos = False
            
            for doc in wizard.document_ids:
                if doc.state == 'draft' and doc.partner_id:
                    valid_count += 1
                else:
                    invalid_count += 1
                
                if doc.pos_order_id:
                    has_pos = True
            
            wizard.valid_documents = valid_count
            wizard.invalid_documents = invalid_count
            wizard.has_pos_orders = has_pos
    
    @api.depends('valid_documents')
    def _compute_estimated_cost(self):
        """Compute estimated cost for sending documents"""
        for wizard in self:
            try:
                fel_config = self.env['fel.config'].search([
                    ('company_id', '=', self.env.company.id),
                    ('is_active', '=', True)
                ], limit=1)
                wizard.cost_per_dte = fel_config.dte_cost if fel_config else 0.33
                wizard.estimated_cost = wizard.valid_documents * wizard.cost_per_dte
            except:
                wizard.cost_per_dte = 0.33
                wizard.estimated_cost = wizard.valid_documents * 0.33
    
    @api.depends('documents_processed', 'total_documents')
    def _compute_processing_progress(self):
        """Compute processing progress percentage"""
        for wizard in self:
            if wizard.total_documents > 0:
                wizard.processing_progress = (wizard.documents_processed / wizard.total_documents) * 100
            else:
                wizard.processing_progress = 0
    
    def action_load_invoices(self):
        """Load invoices based on filters"""
        self.ensure_one()
        
        domain = [('move_type', 'in', ['out_invoice', 'out_refund']), ('state', '=', 'posted')]
        if self.date_from:
            domain.append(('invoice_date', '>=', self.date_from))
        if self.date_to:
            domain.append(('invoice_date', '<=', self.date_to))
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))

        invoices = self.env['account.move'].search(domain)
        self.loaded_invoice_ids = [(6, 0, invoices.ids)]
    
    def action_send_documents(self):
        """Send selected documents to FEL"""
        self.ensure_one()
        
        if not self.document_ids:
            raise ValidationError(_('No documents selected.'))
        
        valid_docs = self.document_ids.filtered(lambda d: d.state == 'draft')
        
        if not valid_docs:
            raise ValidationError(_('No valid documents to send. All documents must be in draft state.'))
        
        self.write({
            'documents_processed': 0,
            'documents_success': 0,
            'documents_failed': 0,
            'processing_log': '<div class="fel_processing_log">',
        })
        
        failed_docs = self.env['fel.document']
        
        for i, doc in enumerate(valid_docs):
            try:
                self.write({
                    'documents_processed': i + 1,
                    'processing_log': self.processing_log + f'<p>Processing {doc.name}...</p>',
                })
                
                doc.action_generate_xml()
                doc.send_to_provider()
                
                self.documents_success += 1
                self.processing_log += f'<p class="text-success">✓ {doc.name} sent successfully</p>'
                
            except Exception as e:
                self.documents_failed += 1
                self.processing_log += f'<p class="text-danger">✗ {doc.name}: {str(e)}</p>'
                failed_docs |= doc
                
                if not self.ignore_errors:
                    raise ValidationError(_('Error processing %s: %s') % (doc.name, str(e)))
        
        self.processing_log += '</div>'
        
        message = _('Processing completed: %d successful, %d failed') % (
            self.documents_success, self.documents_failed
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FEL Processing Complete'),
                'message': message,
                'type': 'success' if self.documents_failed == 0 else 'warning',
            }
        }


class FelPosSendWizard(models.TransientModel):
    _name = 'fel.pos.send.wizard'
    _description = 'FEL POS Order Send Wizard'
    
    # POS Order fields
    order_ids = fields.Many2many(
        'pos.order',
        string='POS Orders',
        domain="[('requires_fel', '=', True)]",
        help='Select POS orders to send to FEL'
    )
    
    loaded_order_ids = fields.Many2many(
        'pos.order',
        'fel_pos_wizard_loaded_order_rel',
        'wizard_id',
        'order_id',
        string='Loaded POS Orders'
    )
    
    # Date range filters
    date_from = fields.Date(
        string='From Date',
        default=fields.Date.context_today
    )
    
    date_to = fields.Date(
        string='To Date',
        default=fields.Date.context_today
    )
    
    # Session filter
    session_ids = fields.Many2many(
        'pos.session',
        string='POS Sessions',
        help='Filter by specific POS sessions'
    )
    
    # Summary fields - THESE WERE MISSING!
    total_orders = fields.Integer(
        string='Total Orders',
        compute='_compute_order_summary',
        store=True
    )
    
    valid_orders = fields.Integer(
        string='Valid Orders',
        compute='_compute_order_summary',
        store=True
    )
    
    invalid_orders = fields.Integer(
        string='Invalid Orders',
        compute='_compute_order_summary',
        store=True
    )
    
    orders_without_customer = fields.Integer(
        string='Orders Without Customer',
        compute='_compute_order_summary',
        store=True
    )
    
    # Processing options
    auto_verify_nits = fields.Boolean(
        string='Auto-Verify NITs',
        default=False,
        help='Automatically verify NITs before sending.'
    )
    
    skip_verified_only = fields.Boolean(
        string='Skip Verified Only',
        default=True,
        help='Only send documents for verified partners.'
    )
    
    create_missing_partners = fields.Boolean(
        string='Create Missing Partners',
        default=True,
        help='Automatically create partners if they are missing.'
    )
    
    @api.depends('loaded_order_ids')
    def _compute_order_summary(self):
        """Compute order summary statistics"""
        for wizard in self:
            wizard.total_orders = len(wizard.loaded_order_ids)
            
            valid_count = 0
            invalid_count = 0
            without_customer = 0
            
            for order in wizard.loaded_order_ids:
                # Check if order is valid for FEL
                if order.partner_id and order.partner_id.nit_gt:
                    # Has customer with NIT
                    if order.state in ('paid', 'done', 'invoiced'):
                        valid_count += 1
                    else:
                        invalid_count += 1
                elif not order.partner_id:
                    # No customer assigned
                    without_customer += 1
                    invalid_count += 1
                else:
                    # Customer without NIT
                    if order.state in ('paid', 'done', 'invoiced'):
                        valid_count += 1  # Can use CF
                    else:
                        invalid_count += 1
            
            wizard.valid_orders = valid_count
            wizard.invalid_orders = invalid_count
            wizard.orders_without_customer = without_customer
    
    def action_load_orders(self):
        """Load POS orders based on filters"""
        self.ensure_one()
        
        domain = [('requires_fel', '=', True)]
        
        if self.date_from:
            domain.append(('date_order', '>=', self.date_from))
        if self.date_to:
            domain.append(('date_order', '<=', self.date_to))
        if self.session_ids:
            domain.append(('session_id', 'in', self.session_ids.ids))
        
        orders = self.env['pos.order'].search(domain)
        self.loaded_order_ids = [(6, 0, orders.ids)]
        
        return {
            'type': 'ir.actions.do_nothing',
        }
    
    def action_send_orders(self):
        """Send selected POS orders to FEL"""
        self.ensure_one()
        
        if not self.loaded_order_ids:
            raise ValidationError(_('No orders loaded. Please load orders first.'))
        
        # Filter valid orders
        valid_orders = self.loaded_order_ids.filtered(
            lambda o: o.state in ('paid', 'done', 'invoiced') and 
                     o.fel_status in ('draft', 'error')
        )
        
        if not valid_orders:
            raise ValidationError(_('No valid orders to send. Orders must be paid and not already sent to FEL.'))
        
        # Process orders
        success_count = 0
        error_count = 0
        errors = []
        
        for order in valid_orders:
            try:
                # Ensure customer info
                if not order.partner_id:
                    if self.create_missing_partners:
                        # Create CF partner
                        order.partner_id = self.env.ref('l10n_gt.consumidor_final_gt')
                    else:
                        raise ValidationError(_('Order %s has no customer') % order.name)
                
                # Verify NIT if enabled
                if self.auto_verify_nits and order.partner_id.nit_gt and order.partner_id.nit_gt != 'CF':
                    if not order.partner_id.nit_verified:
                        order.partner_id.action_verify_nit()
                        if not order.partner_id.nit_verified and self.skip_verified_only:
                            raise ValidationError(_('NIT not verified for %s') % order.partner_id.name)
                
                # Send to FEL
                order.action_send_to_fel()
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"{order.name}: {str(e)}")
                _logger.error(f"Error sending POS order {order.name} to FEL: {str(e)}")
        
        # Show results
        message = _('Processing completed: %d successful, %d failed') % (success_count, error_count)
        if errors:
            message += '\n\nErrors:\n' + '\n'.join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                message += f'\n... and {len(errors) - 5} more errors'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FEL Processing Complete'),
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': error_count > 0,
            }
        }
    
    def action_set_all_cf(self):
        """Set all orders without customer to Consumidor Final"""
        self.ensure_one()
        
        cf_partner = self.env.ref('l10n_gt.consumidor_final_gt', raise_if_not_found=False)
        if not cf_partner:
            # Create CF partner if not exists
            cf_partner = self.env['res.partner'].create({
                'name': 'Consumidor Final',
                'nit_gt': 'CF',
                'is_company': False,
                'customer_rank': 1,
            })
        
        orders_without_customer = self.loaded_order_ids.filtered(lambda o: not o.partner_id)
        orders_without_customer.write({'partner_id': cf_partner.id})
        
        # Reload summary
        self._compute_order_summary()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Customers Updated'),
                'message': _('%d orders set to Consumidor Final') % len(orders_without_customer),
                'type': 'success',
            }
        }