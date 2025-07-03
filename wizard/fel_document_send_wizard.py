# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class FelDocumentSendWizard(models.TransientModel):
    _name = 'fel.document.send.wizard'
    _description = 'FEL Document Send Wizard'
    
    # Document Selection
    document_ids = fields.Many2many(
        'fel.document',
        string='Documents to Send',
        help='Select documents to send to FEL'
    )
    
    # Summary Fields
    total_documents = fields.Integer(
        string='Total Documents',
        compute='_compute_document_summary',
        help='Total number of documents selected'
    )
    
    valid_documents = fields.Integer(
        string='Valid Documents',
        compute='_compute_document_summary',
        help='Number of documents that can be sent'
    )
    
    invalid_documents = fields.Integer(
        string='Invalid Documents',
        compute='_compute_document_summary',
        help='Number of documents with validation errors'
    )
    
    estimated_cost = fields.Float(
        string='Estimated Cost',
        compute='_compute_estimated_cost',
        help='Estimated cost for sending all documents'
    )
    
    cost_per_dte = fields.Float(
        string='Cost per DTE',
        compute='_compute_estimated_cost',
        help='Cost per document from FEL provider'
    )
    
    # Processing Options
    send_mode = fields.Selection([
        ('sequential', 'Sequential (One by one)'),
        ('parallel', 'Parallel (Multiple at once)'),
    ], string='Send Mode', default='sequential',
       help='How to process the documents')
    
    ignore_errors = fields.Boolean(
        string='Ignore Errors',
        default=False,
        help='Continue processing even if some documents fail'
    )
    
    auto_retry = fields.Boolean(
        string='Auto Retry',
        default=True,
        help='Automatically retry failed documents'
    )
    
    notify_completion = fields.Boolean(
        string='Notify When Complete',
        default=True,
        help='Send notification when processing is complete'
    )
    
    # Document Lines
    document_line_ids = fields.One2many(
        'fel.document.send.line',
        'wizard_id',
        string='Document Lines',
        help='Individual document processing lines'
    )
    
    # Validation Results
    validation_complete = fields.Boolean(
        string='Validation Complete',
        default=False,
        help='Whether validation has been completed'
    )
    
    documents_ready = fields.Integer(
        string='Documents Ready',
        default=0,
        help='Number of documents ready to send'
    )
    
    documents_with_errors = fields.Integer(
        string='Documents with Errors',
        default=0,
        help='Number of documents with validation errors'
    )
    
    validation_results = fields.Html(
        string='Validation Results',
        help='Detailed validation results'
    )
    
    # Processing Status
    processing_started = fields.Boolean(
        string='Processing Started',
        default=False,
        help='Whether processing has started'
    )
    
    documents_processed = fields.Integer(
        string='Documents Processed',
        default=0,
        help='Number of documents processed'
    )
    
    documents_successful = fields.Integer(
        string='Documents Successful',
        default=0,
        help='Number of documents successfully sent'
    )
    
    documents_failed = fields.Integer(
        string='Documents Failed',
        default=0,
        help='Number of documents that failed'
    )
    
    processing_progress = fields.Float(
        string='Processing Progress',
        compute='_compute_processing_progress',
        help='Progress percentage'
    )
    
    processing_log = fields.Html(
        string='Processing Log',
        help='Detailed processing log'
    )
    
    # Detection flags
    has_pos_orders = fields.Boolean(
        string='Has POS Orders',
        compute='_compute_document_summary',
        help='Whether any documents are from POS orders'
    )
    
    @api.depends('document_ids')
    def _compute_document_summary(self):
        """Compute document summary statistics"""
        for wizard in self:
            wizard.total_documents = len(wizard.document_ids)
            
            # Count valid/invalid documents
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
                # Get FEL configuration to get cost per DTE
                fel_config = self.env['fel.config'].get_active_config()
                wizard.cost_per_dte = fel_config.provider_id.cost_per_dte or 0.33
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
    
    @api.model
    def default_get(self, fields_list):
        """Set default values based on context"""
        res = super().default_get(fields_list)
        
        # Get documents from context
        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model')
        
        if active_model == 'fel.document' and active_ids:
            res['document_ids'] = [(6, 0, active_ids)]
        
        return res
    
    def action_validate_documents(self):
        """Validate documents before sending"""
        self.ensure_one()
        
        validation_results = []
        ready_count = 0
        error_count = 0
        
        # Create document lines
        self.document_line_ids.unlink()
        lines_data = []
        
        for doc in self.document_ids:
            can_send = True
            validation_message = "Ready to send"
            
            # Validation checks
            if doc.state != 'draft':
                can_send = False
                validation_message = f"Document state is {doc.state}, must be draft"
            
            if not doc.partner_id:
                can_send = False
                validation_message = "Missing customer information"
            
            if not doc.document_type_id:
                can_send = False
                validation_message = "Missing document type"
            
            # Check if source document exists
            if not doc.invoice_id and not doc.pos_order_id:
                can_send = False
                validation_message = "Missing source document (invoice or POS order)"
            
            if can_send:
                ready_count += 1
            else:
                error_count += 1
            
            lines_data.append({
                'wizard_id': self.id,
                'document_id': doc.id,
                'document_type': doc.document_type_id.name,
                'partner_name': doc.partner_id.name if doc.partner_id else '',
                'amount_total': doc.amount_total,
                'can_send': can_send,
                'validation_message': validation_message,
                'selected': can_send,
            })
            
            validation_results.append(f"<li>{doc.name}: {validation_message}</li>")
        
        # Create lines
        for line_data in lines_data:
            self.env['fel.document.send.line'].create(line_data)
        
        # Update validation results
        self.write({
            'validation_complete': True,
            'documents_ready': ready_count,
            'documents_with_errors': error_count,
            'validation_results': f"<ul>{''.join(validation_results)}</ul>",
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fel.document.send.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_send_documents(self):
        """Send selected documents to FEL"""
        self.ensure_one()
        
        if not self.validation_complete:
            self.action_validate_documents()
        
        selected_lines = self.document_line_ids.filtered('selected')
        if not selected_lines:
            raise ValidationError(_('No documents selected for sending.'))
        
        self.processing_started = True
        processing_log = ["<h4>🚀 Starting FEL Document Processing</h4><ul>"]
        
        successful = 0
        failed = 0
        
        for line in selected_lines:
            try:
                processing_log.append(f"<li>📤 Processing {line.document_id.name}...")
                
                # Send document to FEL
                line.document_id.generate_xml()
                line.document_id.send_to_provider()
                
                if line.document_id.state == 'certified':
                    successful += 1
                    processing_log.append(f" ✅ Success - UUID: {line.document_id.uuid}</li>")
                else:
                    failed += 1
                    processing_log.append(f" ❌ Failed - {line.document_id.error_message}</li>")
                
                # Update progress
                self.documents_processed += 1
                self.documents_successful = successful
                self.documents_failed = failed
                
                # Commit after each document if in sequential mode
                if self.send_mode == 'sequential':
                    self.env.cr.commit()
                
            except Exception as e:
                failed += 1
                self.documents_failed = failed
                processing_log.append(f" ❌ Error - {str(e)}</li>")
                
                if not self.ignore_errors:
                    processing_log.append("</ul><p>❌ Processing stopped due to error.</p>")
                    self.processing_log = ''.join(processing_log)
                    raise ValidationError(_('Processing failed: %s') % str(e))
        
        processing_log.append("</ul>")
        processing_log.append(f"<h4>📊 Final Results:</h4>")
        processing_log.append(f"<ul><li>✅ Successful: {successful}</li>")
        processing_log.append(f"<li>❌ Failed: {failed}</li>")
        processing_log.append(f"<li>💰 Cost: Q{successful * self.cost_per_dte:.2f}</li></ul>")
        
        self.processing_log = ''.join(processing_log)
        
        # Send notification if requested
        if self.notify_completion:
            self.env.user.notify_success(
                f'FEL Processing Complete: {successful} successful, {failed} failed'
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('FEL Processing Complete'),
                'message': _('%d documents sent successfully, %d failed') % (successful, failed),
                'type': 'success' if failed == 0 else 'warning',
            }
        }


class FelDocumentSendLine(models.TransientModel):
    _name = 'fel.document.send.line'
    _description = 'FEL Document Send Line'
    
    wizard_id = fields.Many2one(
        'fel.document.send.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    document_id = fields.Many2one(
        'fel.document',
        string='Document',
        required=True
    )
    
    document_type = fields.Char(
        string='Document Type',
        help='Type of FEL document'
    )
    
    partner_name = fields.Char(
        string='Customer',
        help='Customer name'
    )
    
    amount_total = fields.Float(
        string='Amount',
        help='Document total amount'
    )
    
    can_send = fields.Boolean(
        string='Can Send',
        help='Whether this document can be sent'
    )
    
    validation_message = fields.Text(
        string='Validation Message',
        help='Validation result message'
    )
    
    selected = fields.Boolean(
        string='Selected',
        default=True,
        help='Whether to include this document in processing'
    )


class FelInvoiceSendWizard(models.TransientModel):
    _name = 'fel.invoice.send.wizard'
    _description = 'FEL Invoice Send Wizard'
    
    # Invoice Selection
    invoice_ids = fields.Many2many(
        'account.move',
        string='Invoices',
        domain="[('move_type', 'in', ['out_invoice', 'out_refund']), ('state', '=', 'posted')]",
        help='Select invoices to send to FEL'
    )
    
    date_from = fields.Date(
        string='From Date',
        help='Filter invoices from this date'
    )
    
    date_to = fields.Date(
        string='To Date',
        help='Filter invoices until this date'
    )
    
    partner_ids = fields.Many2many(
        'res.partner',
        string='Customers',
        help='Filter by specific customers'
    )
    
    # Options
    auto_verify_nits = fields.Boolean(
        string='Auto Verify NITs',
        default=False,
        help='Automatically verify customer NITs before sending'
    )
    
    skip_verified_only = fields.Boolean(
        string='Skip Unverified NITs',
        default=False,
        help='Only process invoices with verified NITs'
    )
    
    create_missing_partners = fields.Boolean(
        string='Create Missing Partners',
        default=False,
        help='Create partner records for missing customers'
    )
    
    # Loaded Invoices
    loaded_invoice_ids = fields.Many2many(
        'account.move',
        'fel_invoice_wizard_loaded_rel',
        string='Loaded Invoices',
        readonly=True,
        help='Invoices loaded based on filters'
    )
    
    def action_load_invoices(self):
        """Load invoices based on filters"""
        self.ensure_one()
        
        domain = [
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
        ]
        
        if self.date_from:
            domain.append(('invoice_date', '>=', self.date_from))
        
        if self.date_to:
            domain.append(('invoice_date', '<=', self.date_to))
        
        if self.partner_ids:
            domain.append(('partner_id', 'in', self.partner_ids.ids))
        
        # Filter for FEL requirements
        domain.append(('requires_fel', '=', True))
        
        invoices = self.env['account.move'].search(domain)
        self.loaded_invoice_ids = [(6, 0, invoices.ids)]
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fel.invoice.send.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_send_invoices(self):
        """Send loaded invoices to FEL"""
        self.ensure_one()
        
        if not self.loaded_invoice_ids:
            raise ValidationError(_('No invoices loaded. Please load invoices first.'))
        
        sent_count = 0
        error_count = 0
        
        for invoice in self.loaded_invoice_ids:
            try:
                if invoice.can_send_fel:
                    invoice.send_to_fel()
                    if invoice.fel_status == 'certified':
                        sent_count += 1
            except Exception as e:
                error_count += 1
                _logger.error(f"Failed to send invoice {invoice.name} to FEL: {str(e)}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Invoice Processing Complete'),
                'message': _('%d invoices sent successfully, %d failed') % (sent_count, error_count),
                'type': 'success' if error_count == 0 else 'warning',
            }
        }


class FelPosSendWizard(models.TransientModel):
    _name = 'fel.pos.send.wizard'
    _description = 'FEL POS Send Wizard'
    
    # Order Selection
    session_ids = fields.Many2many(
        'pos.session',
        string='POS Sessions',
        help='Filter by POS sessions'
    )
    
    date_from = fields.Date(
        string='From Date',
        help='Filter orders from this date'
    )
    
    date_to = fields.Date(
        string='To Date', 
        help='Filter orders until this date'
    )
    
    waiter_ids = fields.Many2many(
        'res.users',
        string='Waiters',
        help='Filter by specific waiters'
    )
    
    table_filter = fields.Char(
        string='Table Filter',
        help='Filter by table number (partial match)'
    )
    
    # Restaurant Options
    only_paid_orders = fields.Boolean(
        string='Only Paid Orders',
        default=True,
        help='Only include paid orders'
    )
    
    include_cf_orders = fields.Boolean(
        string='Include CF Orders',
        default=True,
        help='Include Consumidor Final orders'
    )
    
    auto_set_cf = fields.Boolean(
        string='Auto Set CF',
        default=False,
        help='Automatically set missing customers as CF'
    )
    
    require_customer_info = fields.Boolean(
        string='Require Customer Info',
        default=False,
        help='Only process orders with customer information'
    )
    
    # Summary
    orders_loaded = fields.Boolean(
        string='Orders Loaded',
        default=False,
        help='Whether orders have been loaded'
    )
    
    total_orders = fields.Integer(
        string='Total Orders',
        help='Total number of orders found'
    )
    
    orders_with_customer = fields.Integer(
        string='Orders with Customer',
        help='Orders that have customer information'
    )
    
    orders_without_customer = fields.Integer(
        string='Orders without Customer',
        help='Orders missing customer information'
    )
    
    total_amount = fields.Float(
        string='Total Amount',
        help='Total amount of all orders'
    )
    
    estimated_dte_cost = fields.Float(
        string='Estimated DTE Cost',
        help='Estimated cost for FEL processing'
    )
    
    # Loaded Orders
    loaded_order_ids = fields.Many2many(
        'pos.order',
        'fel_pos_wizard_loaded_rel',
        string='Loaded Orders',
        readonly=True,
        help='Orders loaded based on filters'
    )
    
    def action_load_orders(self):
        """Load POS orders based on filters"""
        self.ensure_one()
        
        domain = [('state', 'in', ['paid', 'done', 'invoiced'])]
        
        if self.only_paid_orders:
            domain.append(('state', 'in', ['paid', 'done']))
        
        if self.date_from:
            domain.append(('date_order', '>=', self.date_from))
        
        if self.date_to:
            domain.append(('date_order', '<=', self.date_to))
        
        if self.session_ids:
            domain.append(('session_id', 'in', self.session_ids.ids))
        
        if self.waiter_ids:
            domain.append(('waiter_id', 'in', self.waiter_ids.ids))
        
        if self.table_filter:
            domain.append(('table_number', 'ilike', self.table_filter))
        
        # Filter for FEL requirements
        domain.append(('requires_fel', '=', True))
        
        orders = self.env['pos.order'].search(domain)
        self.loaded_order_ids = [(6, 0, orders.ids)]
        
        # Calculate summary
        with_customer = len(orders.filtered(lambda o: o.customer_nit or o.partner_id))
        without_customer = len(orders) - with_customer
        
        self.write({
            'orders_loaded': True,
            'total_orders': len(orders),
            'orders_with_customer': with_customer,
            'orders_without_customer': without_customer,
            'total_amount': sum(orders.mapped('amount_total')),
            'estimated_dte_cost': len(orders) * 0.33,  # Default cost per DTE
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fel.pos.send.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_set_all_cf(self):
        """Set all orders without customer info to CF"""
        self.ensure_one()
        
        if not self.loaded_order_ids:
            raise ValidationError(_('No orders loaded. Please load orders first.'))
        
        orders_without_customer = self.loaded_order_ids.filtered(
            lambda o: not o.customer_nit and not o.partner_id
        )
        
        cf_partner = self.env.ref('fel_nit_gt_sat.partner_consumidor_final_gt', raise_if_not_found=False)
        
        for order in orders_without_customer:
            order.write({
                'customer_nit': 'CF',
                'customer_name': 'Consumidor Final',
                'partner_id': cf_partner.id if cf_partner else False,
            })
        
        # Refresh summary
        self.action_load_orders()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Customer Info Updated'),
                'message': _('%d orders set to Consumidor Final') % len(orders_without_customer),
                'type': 'success',
            }
        }
    
    def action_send_orders(self):
        """Send loaded POS orders to FEL"""
        self.ensure_one()
        
        if not self.loaded_order_ids:
            raise ValidationError(_('No orders loaded. Please load orders first.'))
        
        # Auto-set CF if requested
        if self.auto_set_cf:
            self.action_set_all_cf()
        
        processable_orders = self.loaded_order_ids.filtered('can_send_fel')
        
        if not processable_orders:
            raise ValidationError(_('No orders can be sent to FEL. Please check customer information.'))
        
        sent_count = 0
        error_count = 0
        
        for order in processable_orders:
            try:
                order.send_to_fel()
                if order.fel_status == 'certified':
                    sent_count += 1
            except Exception as e:
                error_count += 1
                _logger.error(f"Failed to send POS order {order.name} to FEL: {str(e)}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('POS Order Processing Complete'),
                'message': _('%d orders sent successfully, %d failed') % (sent_count, error_count),
                'type': 'success' if error_count == 0 else 'warning',
            }
        }


class FelDailyProcessingWizard(models.TransientModel):
    _name = 'fel.daily.processing.wizard'
    _description = 'FEL Daily Processing Wizard'
    
    process_date = fields.Date(
        string='Processing Date',
        default=fields.Date.today,
        help='Date to process documents for'
    )
    
    include_previous_days = fields.Boolean(
        string='Include Previous Days',
        default=False,
        help='Include documents from previous days'
    )
    
    pending_invoices = fields.Integer(
        string='Pending Invoices',
        compute='_compute_pending_documents',
        help='Number of pending invoices'
    )
    
    pending_pos_orders = fields.Integer(
        string='Pending POS Orders',
        compute='_compute_pending_documents',
        help='Number of pending POS orders'
    )
    
    estimated_total_cost = fields.Float(
        string='Estimated Total Cost',
        compute='_compute_pending_documents',
        help='Estimated cost for processing all documents'
    )
    
    @api.depends('process_date', 'include_previous_days')
    def _compute_pending_documents(self):
        """Compute pending documents for processing"""
        for wizard in self:
            date_domain = [('invoice_date', '=', wizard.process_date)]
            if wizard.include_previous_days:
                date_domain = [('invoice_date', '<=', wizard.process_date)]
            
            # Count pending invoices
            invoice_domain = [
                ('requires_fel', '=', True),
                ('fel_status', 'in', ['draft', 'error']),
                ('state', '=', 'posted'),
            ] + date_domain
            
            pending_invoices = self.env['account.move'].search_count(invoice_domain)
            
            # Count pending POS orders
            pos_domain = [
                ('requires_fel', '=', True),
                ('fel_status', 'in', ['draft', 'error']),
                ('state', 'in', ['paid', 'done']),
                ('date_order', '>=', wizard.process_date),
            ]
            
            if wizard.include_previous_days:
                pos_domain[-1] = ('date_order', '<=', wizard.process_date)
            
            pending_pos_orders = self.env['pos.order'].search_count(pos_domain)
            
            total_documents = pending_invoices + pending_pos_orders
            
            wizard.pending_invoices = pending_invoices
            wizard.pending_pos_orders = pending_pos_orders
            wizard.estimated_total_cost = total_documents * 0.33
    
    def action_process_today(self):
        """Process all pending documents for the day"""
        self.ensure_one()
        
        # Process invoices
        invoice_domain = [
            ('requires_fel', '=', True),
            ('fel_status', 'in', ['draft', 'error']),
            ('state', '=', 'posted'),
            ('invoice_date', '=', self.process_date),
        ]
        
        if self.include_previous_days:
            invoice_domain[-1] = ('invoice_date', '<=', self.process_date)
        
        invoices = self.env['account.move'].search(invoice_domain)
        
        # Process POS orders
        pos_domain = [
            ('requires_fel', '=', True),
            ('fel_status', 'in', ['draft', 'error']),
            ('state', 'in', ['paid', 'done']),
            ('date_order', '>=', self.process_date),
        ]
        
        if self.include_previous_days:
            pos_domain[-1] = ('date_order', '<=', self.process_date)
        
        pos_orders = self.env['pos.order'].search(pos_domain)
        
        # Auto-set missing customer info to CF
        pos_orders_no_customer = pos_orders.filtered(
            lambda o: not o.customer_nit and not o.partner_id
        )
        
        cf_partner = self.env.ref('fel_nit_gt_sat.partner_consumidor_final_gt', raise_if_not_found=False)
        
        for order in pos_orders_no_customer:
            order.write({
                'customer_nit': 'CF',
                'customer_name': 'Consumidor Final',
                'partner_id': cf_partner.id if cf_partner else False,
            })
        
        # Send documents
        total_processed = 0
        total_successful = 0
        
        # Process invoices
        for invoice in invoices:
            try:
                if invoice.can_send_fel:
                    invoice.send_to_fel()
                    total_processed += 1
                    if invoice.fel_status == 'certified':
                        total_successful += 1
            except Exception as e:
                total_processed += 1
                _logger.error(f"Failed to process invoice {invoice.name}: {str(e)}")
        
        # Process POS orders
        for order in pos_orders:
            try:
                if order.can_send_fel:
                    order.send_to_fel()
                    total_processed += 1
                    if order.fel_status == 'certified':
                        total_successful += 1
            except Exception as e:
                total_processed += 1
                _logger.error(f"Failed to process POS order {order.name}: {str(e)}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Daily Processing Complete'),
                'message': _('Processed %d documents, %d successful') % (total_processed, total_successful),
                'type': 'success',
            }
        }
