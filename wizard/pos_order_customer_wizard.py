# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

class PosOrderCustomerWizard(models.TransientModel):
    _name = 'pos.order.customer.wizard'
    _description = 'POS Order Customer Information Wizard'
    
    # POS Order
    pos_order_id = fields.Many2one(
        'pos.order',
        string='POS Order',
        required=True,
        readonly=True,
        help='POS order to update'
    )
    
    order_reference = fields.Char(
        related='pos_order_id.pos_reference',
        string='Order Reference',
        readonly=True
    )
    
    amount_total = fields.Float(
        related='pos_order_id.amount_total',
        string='Total Amount',
        readonly=True
    )
    
    # Customer Information
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        help='Select existing customer'
    )
    
    customer_nit = fields.Char(
        string='Customer NIT',
        help='Customer NIT for FEL (use CF for Consumidor Final)'
    )
    
    customer_name = fields.Char(
        string='Customer Name',
        help='Customer name for the invoice'
    )
    
    customer_address = fields.Char(
        string='Customer Address',
        help='Customer address (optional)'
    )
    
    # Options
    create_partner = fields.Boolean(
        string='Create Customer',
        default=False,
        help='Create new customer if not exists'
    )
    
    verify_nit = fields.Boolean(
        string='Verify NIT',
        default=True,
        help='Verify NIT with SAT before saving'
    )
    
    send_to_fel = fields.Boolean(
        string='Send to FEL',
        default=False,
        help='Send to FEL after setting customer info'
    )
    
    # Verification Results
    nit_verified = fields.Boolean(
        string='NIT Verified',
        readonly=True,
        help='Whether NIT was verified with SAT'
    )
    
    verification_message = fields.Text(
        string='Verification Message',
        readonly=True
    )
    
    @api.model
    def default_get(self, fields_list):
        """Set default values from context"""
        res = super().default_get(fields_list)
        
        # Get POS order from context
        active_id = self.env.context.get('active_id')
        active_model = self.env.context.get('active_model')
        
        if active_model == 'pos.order' and active_id:
            order = self.env['pos.order'].browse(active_id)
            res['pos_order_id'] = order.id
            
            # Pre-fill customer info if available
            if order.partner_id:
                res['partner_id'] = order.partner_id.id
                res['customer_nit'] = order.partner_id.nit_gt or order.customer_nit
                res['customer_name'] = order.partner_id.name or order.customer_name
            elif order.customer_nit:
                res['customer_nit'] = order.customer_nit
                res['customer_name'] = order.customer_name
            
        return res
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Update fields when partner changes"""
        if self.partner_id:
            self.customer_nit = self.partner_id.nit_gt or 'CF'
            self.customer_name = self.partner_id.name
            self.customer_address = self.partner_id.street or ''
    
    @api.onchange('customer_nit')
    def _onchange_customer_nit(self):
        """Try to find partner when NIT changes"""
        if self.customer_nit and self.customer_nit != 'CF':
            # Clean NIT
            clean_nit = self.customer_nit.replace('-', '').replace(' ', '')
            
            # Search for existing partner
            partner = self.env['res.partner'].search([
                ('nit_gt', '=', self.customer_nit)
            ], limit=1)
            
            if partner:
                self.partner_id = partner.id
                self.customer_name = partner.name
                self.customer_address = partner.street or ''
    
    def action_verify_nit(self):
        """Verify NIT with SAT"""
        self.ensure_one()
        
        if not self.customer_nit or self.customer_nit == 'CF':
            raise ValidationError(_('Cannot verify "Consumidor Final" (CF) NIT.'))
        
        # Use NIT verification wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('Verify NIT'),
            'res_model': 'fel.nit.verification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_nit': self.customer_nit,
                'default_partner_id': self.partner_id.id if self.partner_id else False,
            }
        }
    
    def action_set_customer_info(self):
        """Set customer information on POS order"""
        self.ensure_one()
        
        if not self.customer_nit:
            raise ValidationError(_('Customer NIT is required.'))
        
        if not self.customer_name:
            raise ValidationError(_('Customer name is required.'))
        
        # Update POS order
        vals = {
            'customer_nit': self.customer_nit,
            'customer_name': self.customer_name,
        }
        
        # Handle partner
        if self.partner_id:
            vals['partner_id'] = self.partner_id.id
        elif self.create_partner and self.customer_nit != 'CF':
            # Create new partner
            partner_vals = {
                'name': self.customer_name,
                'nit_gt': self.customer_nit,
                'street': self.customer_address or False,
                'customer_rank': 1,
                'is_company': True,  # Assume company if has NIT
            }
            partner = self.env['res.partner'].create(partner_vals)
            vals['partner_id'] = partner.id
            self.partner_id = partner
        
        # Update POS order
        self.pos_order_id.write(vals)
        
        # Show success message
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Customer information updated successfully.'),
                'type': 'success',
            }
        }
    
    def action_send_to_fel(self):
        """Set customer info and send to FEL"""
        self.ensure_one()
        
        # First set customer info
        self.action_set_customer_info()
        
        # Then send to FEL
        return self.pos_order_id.action_send_to_fel()


class PosSessionCloseWizard(models.TransientModel):
    _name = 'pos.session.close.wizard'
    _description = 'POS Session Close Wizard'
    
    session_id = fields.Many2one(
        'pos.session',
        string='POS Session',
        required=True,
        readonly=True
    )
    
    pending_fel_count = fields.Integer(
        string='Pending FEL Orders',
        readonly=True,
        help='Number of orders pending FEL processing'
    )
    
    process_fel_orders = fields.Boolean(
        string='Process FEL Orders',
        default=True,
        help='Process pending FEL orders before closing'
    )
    
    def action_close_session(self):
        """Close session with or without processing FEL"""
        self.ensure_one()
        
        if self.process_fel_orders:
            # Get pending orders
            pending_orders = self.session_id.order_ids.filtered(
                lambda o: o.requires_fel and o.fel_status == 'draft'
            )
            
            if pending_orders:
                # Open wizard to process orders
                return {
                    'type': 'ir.actions.act_window',
                    'name': _('Send POS Orders to FEL'),
                    'res_model': 'fel.pos.send.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_order_ids': [(6, 0, pending_orders.ids)],
                        'close_session_after': True,
                        'session_id': self.session_id.id,
                    }
                }
        
        # Close session normally
        return self.session_id.action_pos_session_close()