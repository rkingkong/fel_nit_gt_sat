# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class FelDocumentSendWizard(models.TransientModel):
    _name = 'fel.document.send.wizard'
    _description = 'FEL Document Send Wizard'
    
    invoice_ids = fields.Many2many(
        'account.move',
        string='Invoices',
        domain="[('move_type', 'in', ['out_invoice', 'out_refund']), ('state', '=', 'posted')]",
        help='Select invoices to send to FEL'
    )
    
    generate_pdf = fields.Boolean(string="Generate PDF", default=False)
    
    date_from = fields.Date(string="Start Date")
    
    date_to = fields.Date(string="End Date", help="End date for filtering documents")
    
    partner_ids = fields.Many2many('res.partner', string='Customers')
    
    fel_provider = fields.Selection([
        ('sat', 'SAT'),
        ('other', 'Other Provider'),
    ], string='FEL Provider', default='sat',
       help='Select the FEL provider to send documents to') 
    
    # Configuration
    fel_config_id = fields.Many2one(
        'fel.config',
        string='FEL Configuration',
        required=True,
        help='FEL configuration to use for sending documents'
    )
    
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
        string='Auto Retry on Error',
        default=True,
        help='Automatically retry failed documents'
    )
    
    # Processing Results
    documents_processed = fields.Integer(
        string='Documents Processed',
        default=0,
        help='Number of documents processed so far'
    )
    
    documents_success = fields.Integer(
        string='Successful',
        default=0,
        help='Number of successfully sent documents'
    )
    
    documents_failed = fields.Integer(
        string='Failed',
        default=0,
        help='Number of failed documents'
    )
    
    processing_progress = fields.Float(
        string='Progress',
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
                wizard.cost_per_dte = fel_config.dte_cost or 0.33
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
    
    def action_send_documents(self):
        """Send selected documents to FEL"""
        self.ensure_one()
        
        if not self.document_ids:
            raise ValidationError(_('No documents selected.'))
        
        # Filter valid documents
        valid_docs = self.document_ids.filtered(lambda d: d.state == 'draft')
        
        if not valid_docs:
            raise ValidationError(_('No valid documents to send. All documents must be in draft state.'))
        
        # Initialize counters
        self.write({
            'documents_processed': 0,
            'documents_success': 0,
            'documents_failed': 0,
            'processing_log': '<div class="fel_processing_log">',
        })
        
        # Process documents
        failed_docs = self.env['fel.document']
        
        for i, doc in enumerate(valid_docs):
            try:
                # Update progress
                self.write({
                    'documents_processed': i + 1,
                    'processing_log': self.processing_log + f'<p>Processing {doc.name}...</p>',
                })
                
                # Send document
                doc.action_generate_xml()
                doc.action_send_to_provider()
                
                # Update success counter
                self.documents_success += 1
                self.processing_log += f'<p class="text-success">✓ {doc.name} sent successfully</p>'
                
            except Exception as e:
                # Handle error
                self.documents_failed += 1
                self.processing_log += f'<p class="text-danger">✗ {doc.name}: {str(e)}</p>'
                failed_docs |= doc
                
                if not self.ignore_errors:
                    raise ValidationError(_('Error processing %s: %s') % (doc.name, str(e)))
        
        # Close log
        self.processing_log += '</div>'
        
        # Show results
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


class FelInvoiceSendWizard(models.TransientModel):
    _name = 'fel.invoice.send.wizard'
    _description = 'FEL Invoice Send Wizard'
    
    invoice_ids = fields.Many2many(
        'account.move',
        string='Invoices',
        domain="[('move_type', 'in', ['out_invoice', 'out_refund']), ('state', '=', 'posted')]",
        help='Select invoices to send to FEL'
    )
    
    def action_send_invoices(self):
        """Send selected invoices to FEL"""
        self.ensure_one()
        
        if not self.invoice_ids:
            raise ValidationError(_('No invoices selected.'))
        
        # Create FEL documents for invoices
        fel_documents = self.env['fel.document']
        
        for invoice in self.invoice_ids:
            if not invoice.fel_document_id:
                fel_doc = invoice.action_create_fel_document()
                fel_documents |= fel_doc
        
        # Open send wizard for the created documents
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Documents to FEL'),
            'res_model': 'fel.document.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_document_ids': [(6, 0, fel_documents.ids)],
            }
        }


class FelPosSendWizard(models.TransientModel):
    _name = 'fel.pos.send.wizard'
    _description = 'FEL POS Order Send Wizard'
    
    order_ids = fields.Many2many(
        'pos.order',
        string='POS Orders',
        domain="[('requires_fel', '=', True)]",
        help='Select POS orders to send to FEL'
    )
    
    def action_send_orders(self):
        """Send selected POS orders to FEL"""
        self.ensure_one()
        
        if not self.order_ids:
            raise ValidationError(_('No orders selected.'))
        
        # Create FEL documents for orders
        fel_documents = self.env['fel.document']
        
        for order in self.order_ids:
            if not order.fel_document_id:
                fel_doc = order.action_create_fel_document()
                fel_documents |= fel_doc
        
        # Open send wizard for the created documents
        return {
            'type': 'ir.actions.act_window',
            'name': _('Send Documents to FEL'),
            'res_model': 'fel.document.send.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_document_ids': [(6, 0, fel_documents.ids)],
            }
        }