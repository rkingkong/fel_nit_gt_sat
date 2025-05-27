# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re

class PosOrderCustomerWizard(models.TransientModel):
    _name = 'pos.order.customer.wizard'
    _description = 'POS Order Customer Information Wizard'
    
    # Order information
    order_id = fields.Many2one(
        'pos.order',
        string='POS Order',
        required=True,
        readonly=True
    )
    
    order_name = fields.Char(
        string='Order',
        related='order_id.name',
        readonly=True
    )
    
    order_amount = fields.Float(
        string='Order Amount',
        related='order_id.amount_total',
        readonly=True
    )
    
    # Customer information
    customer_nit = fields.Char(
        string='Customer NIT',
        help='Customer NIT for FEL document (enter CF for Consumidor Final)'
    )
    
    customer_name = fields.Char(
        string='Customer Name',
        help='Customer name for FEL document'
    )
    
    # Options
    create_partner = fields.Boolean(
        string='Create Customer Record',
        default=False,
        help='Create a customer record for this NIT'
    )
    
    verify_nit = fields.Boolean(
        string='Verify NIT with SAT',
        default=True,
        help='Verify the NIT with SAT before setting'
    )
    
    # Existing partner selection
    partner_id = fields.Many2one(
        'res.partner',
        string='Existing Customer',
        domain="[('customer_rank', '>', 0)]",
        help='Select an existing customer instead of entering NIT manually'
    )
    
    # Validation fields
    clean_nit = fields.Char(
        string='Cleaned NIT',
        compute='_compute_clean_nit',
        help='NIT formatted for processing'
    )
    
    is_consumidor_final = fields.Boolean(
        string='Is Consumidor Final',
        compute='_compute_is_consumidor_final',
        help='Whether this is a consumidor final order'
    )
    
    show_verification = fields.Boolean(
        string='Show Verification',
        compute='_compute_show_verification',
        help='Whether to show NIT verification option'
    )
    
    @api.depends('customer_nit')
    def _compute_clean_nit(self):
        """Clean and format NIT"""
        for wizard in self:
            if wizard.customer_nit:
                if wizard.customer_nit.upper() == 'CF':
                    wizard.clean_nit = 'CF'
                else:
                    wizard.clean_nit = re.sub(r'\D', '', wizard.customer_nit)
            else:
                wizard.clean_nit = ''
    
    @api.depends('clean_nit')
    def _compute_is_consumidor_final(self):
        """Check if this is consumidor final"""
        for wizard in self:
            wizard.is_consumidor_final = wizard.clean_nit == 'CF' or not wizard.clean_nit
    
    @api.depends('clean_nit', 'verify_nit')
    def _compute_show_verification(self):
        """Show verification option for valid NITs"""
        for wizard in self:
            wizard.show_verification = (
                wizard.verify_nit and 
                wizard.clean_nit and 
                wizard.clean_nit != 'CF' and 
                len(wizard.clean_nit) >= 8
            )
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Fill customer info when partner is selected"""
        if self.partner_id:
            self.customer_nit = self.partner_id.nit_gt or 'CF'
            self.customer_name = self.partner_id.name
            self.create_partner = False
        else:
            self.customer_nit = ''
            self.customer_name = ''
    
    @api.onchange('customer_nit')
    def _onchange_customer_nit(self):
        """Auto-fill customer name and find existing partner"""
        if self.customer_nit:
            # Reset partner selection
            self.partner_id = False
            
            if self.clean_nit == 'CF':
                self.customer_name = 'Consumidor Final'
                self.create_partner = False
                self.verify_nit = False
            elif self.clean_nit and len(self.clean_nit) >= 8:
                # Search for existing partner
                partner = self.env['res.partner'].search([
                    ('nit_gt', '=', self.clean_nit)
                ], limit=1)
                
                if partner:
                    self.partner_id = partner.id
                    self.customer_name = partner.name
                    self.create_partner = False
                else:
                    self.create_partner = True
                    
                self.verify_nit = True
    
    def action_set_customer_info(self):
        """Set customer information on the POS order"""
        self.ensure_one()
        
        # Validation
        if not self.customer_nit:
            raise ValidationError(_('Customer NIT is required.'))
        
        if not self.customer_name:
            raise ValidationError(_('Customer name is required.'))
        
        # Clean NIT validation
        if self.clean_nit != 'CF' and len(self.clean_nit) < 8:
            raise ValidationError(_('Invalid NIT format. Please enter a valid Guatemala NIT.'))
        
        try:
            # Get or create partner if requested
            partner = self.partner_id
            
            if not partner and self.create_partner and self.clean_nit != 'CF':
                # Create new partner
                partner = self.env['res.partner'].create({
                    'name': self.customer_name,
                    'nit_gt': self.clean_nit,
                    'is_company': True,
                    'customer_rank': 1,
                    'country_id': self.env.ref('base.gt').id,
                })
            elif not partner and self.clean_nit == 'CF':
                # Use or create CF partner
                partner = self.env['res.partner'].search([
                    ('nit_gt', '=', 'CF'),
                    ('is_company', '=', False)
                ], limit=1)
                
                if not partner:
                    partner = self.env['res.partner'].create({
                        'name': 'Consumidor Final',
                        'nit_gt': 'CF',
                        'is_company': False,
                        'customer_rank': 1,
                        'country_id': self.env.ref('base.gt').id,
                    })
            
            # Update POS order
            update_data = {
                'customer_nit': self.clean_nit,
                'customer_name': self.customer_name,
            }
            
            if partner:
                update_data['partner_id'] = partner.id
            
            self.order_id.write(update_data)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Customer Information Set'),
                    'message': _('Customer information updated for order %s') % self.order_id.name,
                    'type': 'success',
                }
            }
            
        except Exception as e:
            raise ValidationError(_('Failed to set customer information: %s') % str(e))
    
    def action_verify_nit(self):
        """Verify NIT with SAT"""
        self.ensure_one()
        
        if not self.show_verification:
            raise ValidationError(_('NIT verification is not available for this NIT.'))
        
        # Open NIT verification wizard
        return {
            'type': 'ir.actions.act_window',
            'name': _('Verify NIT'),
            'res_model': 'fel.nit.verification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_nit': self.customer_nit,
                'default_partner_name': self.customer_name,
                'default_create_partner': True,
                'default_update_partner': True,
            }
        }
    
    def action_send_to_fel(self):
        """Set customer info and send order to FEL"""
        self.ensure_one()
        
        # First set customer information
        self.action_set_customer_info()
        
        # Then send to FEL
        try:
            self.order_id.send_to_fel()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Order Sent to FEL'),
                    'message': _('Order %s sent to FEL successfully') % self.order_id.name,
                    'type': 'success',
                }
            }
            
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('FEL Error'),
                    'message': _('Failed to send to FEL: %s') % str(e),
                    'type': 'warning',
                }
            }


class PosSessionCloseWizard(models.TransientModel):
    _name = 'pos.session.close.wizard'
    _description = 'POS Session Close with FEL Check'
    
    session_id = fields.Many2one(
        'pos.session',
        string='POS Session',
        required=True,
        readonly=True
    )
    
    pending_fel_count = fields.Integer(
        string='Pending FEL Orders',
        readonly=True
    )
    
    process_pending_fel = fields.Boolean(
        string='Process Pending FEL Orders',
        default=True,
        help='Process all pending FEL orders before closing the session'
    )
    
    ignore_fel_errors = fields.Boolean(
        string='Ignore FEL Errors',
        default=False,
        help='Close session even if some FEL orders fail'
    )
    
    def action_close_session(self):
        """Close session with FEL processing"""
        self.ensure_one()
        
        if self.process_pending_fel:
            # Process pending FEL orders
            pending_orders = self.session_id.order_ids.filtered(
                lambda o: o.requires_fel and o.fel_status == 'draft'
            )
            
            success_count = 0
            error_count = 0
            
            for order in pending_orders:
                try:
                    # Set default customer info if missing
                    if not order.customer_nit:
                        order.write({
                            'customer_nit': 'CF',
                            'customer_name': 'Consumidor Final'
                        })
                    
                    # Send to FEL
                    order.send_to_fel()
                    if order.fel_status == 'certified':
                        success_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
            
            # Check if we should proceed with errors
            if error_count > 0 and not self.ignore_fel_errors:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('FEL Processing Incomplete'),
                        'message': _('%d orders processed successfully, %d errors. Enable "Ignore FEL Errors" to close anyway.') % (success_count, error_count),
                        'type': 'warning',
                    }
                }
        
        # Close the session
        return self.session_id.action_pos_session_close()
