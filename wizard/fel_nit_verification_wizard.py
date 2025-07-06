# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re
import logging

_logger = logging.getLogger(__name__)

class FelNitVerificationWizard(models.TransientModel):
    _name = 'fel.nit.verification.wizard'
    _description = 'FEL NIT Verification Wizard'

    error_message = fields.Text(string="Error Message", readonly=True)
    is_verified = fields.Boolean(string="Is Verified", readonly=True)
    verification_date = fields.Datetime(string="Verification Date", readonly=True)
    verification_result = fields.Text(string="Verification Result", readonly=True)
    fel_verification_status = fields.Selection([
        ('valid', 'Valid'),
        ('invalid', 'Invalid'),
        ('error', 'Error'), 
    ], string="FEL Verification Status", readonly=True, default='valid')
    fel_verification_date = fields.Datetime(string="FEL Verification Date", readonly=True)
    fel_verification_result = fields.Text(string="FEL Verification Result", readonly=True)
    sat_name = fields.Char(string="SAT Name", readonly=True)
    sat_address = fields.Text(string="SAT Address", readonly=True)
    sat_status = fields.Char(string="SAT Status", readonly=True)
    tax_regime_gt = fields.Selection([
        ('general', 'Régimen General'),
        ('pequeno', 'Pequeño Contribuyente'),
        ('especial', 'Régimen Especial'),
    ], string="Tax Regime", readonly=True, help="Tax regime as per SAT classification")
    
    nit_gt = fields.Char(string="NIT", readonly=True, help="NIT as per SAT classification")
    tax_regime_description = fields.Text(string="Tax Regime Description", readonly=True)

    
    # Input fields
    nit = fields.Char(string='NIT to Verify', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner')

    # Result fields
    verification_state = fields.Selection([
        ('draft', 'Ready to Verify'),
        ('verifying', 'Verifying...'),
        ('verified', 'Verified'),
        ('error', 'Error'),
    ], default='draft', readonly=True)
    is_verified = fields.Boolean(readonly=True)
    verification_message = fields.Text(readonly=True)

    # SAT Info
    sat_name = fields.Char(readonly=True)
    sat_address = fields.Text(readonly=True)
    tax_regime = fields.Selection([
        ('general', 'Régimen General'),
        ('pequeno', 'Pequeño Contribuyente'),
        ('especial', 'Régimen Especial'),
    ], readonly=True)
    regime_description = fields.Text(string="Descripción del Régimen", compute="_compute_regime_description")
    sat_status = fields.Char(readonly=True)

    # Options
    update_partner = fields.Boolean(default=True)
    create_partner = fields.Boolean(default=False)
    partner_name = fields.Char()

    # Computed
    clean_nit = fields.Char(compute='_compute_clean_nit')
    can_verify = fields.Boolean(compute='_compute_can_verify')
    show_partner_creation = fields.Boolean(compute='_compute_show_partner_creation')

    @api.depends('tax_regime')
    def _compute_regime_description(self):
        for wizard in self:
            if wizard.tax_regime == 'general':
                wizard.regime_description = _("Régimen General: Standard taxpayers (most companies)")
            elif wizard.tax_regime == 'pequeno':
                wizard.regime_description = _("Pequeño Contribuyente: Small taxpayers with limited annual income")
            elif wizard.tax_regime == 'especial':
                wizard.regime_description = _("Régimen Especial: Special regime taxpayers (specific industries)")
            else:
                wizard.regime_description = ''

    @api.depends('nit')
    def _compute_clean_nit(self):
        for wizard in self:
            if wizard.nit:
                wizard.clean_nit = 'CF' if wizard.nit.upper() == 'CF' else re.sub(r'\D', '', wizard.nit)
            else:
                wizard.clean_nit = ''

    @api.depends('clean_nit')
    def _compute_can_verify(self):
        for wizard in self:
            wizard.can_verify = bool(wizard.clean_nit and wizard.clean_nit != 'CF' and len(wizard.clean_nit) >= 8)

    @api.depends('is_verified', 'partner_id', 'create_partner')
    def _compute_show_partner_creation(self):
        for wizard in self:
            wizard.show_partner_creation = wizard.is_verified and not wizard.partner_id and wizard.create_partner

    @api.onchange('nit')
    def _onchange_nit(self):
        if self.nit:
            self.verification_state = 'draft'
            self.is_verified = False
            self.verification_message = ''
            self.sat_name = ''
            self.sat_address = ''
            self.tax_regime = False
            self.sat_status = ''
            if self.clean_nit and self.clean_nit != 'CF':
                partner = self.env['res.partner'].search([('nit_gt', '=', self.clean_nit)], limit=1)
                self.partner_id = partner.id if partner else False
                self.partner_name = partner.name if partner else ''

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id and self.partner_id.nit_gt:
            self.nit = self.partner_id.nit_gt
            self.partner_name = self.partner_id.name

    def action_verify_nit(self):
        self.ensure_one()
        if not self.can_verify:
            raise ValidationError(_('Invalid NIT format.'))
        try:
            self.verification_state = 'verifying'
            config = self.env['fel.config'].get_active_config()
            result = self.env['fel.nit.verification.service'].verify_nit(self.clean_nit, config)
            self.write({
                'verification_state': 'verified' if result.get('verified') else 'error',
                'is_verified': result.get('verified', False),
                'verification_message': result.get('message', ''),
                'sat_name': result.get('name', ''),
                'sat_address': result.get('address', ''),
                'sat_status': result.get('status', ''),
            })
            regime = {
                'GENERAL': 'general',
                'RÉGIMEN GENERAL': 'general',
                'PEQUEÑO': 'pequeno',
                'PEQUEÑO CONTRIBUYENTE': 'pequeno',
                'ESPECIAL': 'especial',
                'RÉGIMEN ESPECIAL': 'especial',
            }.get(result.get('regime', '').upper())
            if regime:
                self.tax_regime = regime
            if self.is_verified and not self.partner_name and self.sat_name:
                self.partner_name = self.sat_name
        except Exception as e:
            self.write({
                'verification_state': 'error',
                'is_verified': False,
                'verification_message': str(e),
            })
            raise ValidationError(_('NIT verification failed: %s') % str(e))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fel.nit.verification.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_update_partner(self):
        self.ensure_one()
        if not self.is_verified:
            raise ValidationError(_('Only verified NITs can update partners.'))
        partner = self.partner_id
        if not partner and self.create_partner:
            if not self.partner_name:
                raise ValidationError(_('Partner name is required.'))
            partner = self.env['res.partner'].create({
                'name': self.partner_name,
                'nit_gt': self.clean_nit,
                'is_company': True,
                'customer_rank': 1,
                'country_id': self.env.ref('base.gt').id,
            })
            self.partner_id = partner.id
        if not partner:
            raise ValidationError(_('No partner selected.'))
        data = {
            'nit_gt': self.clean_nit,
            'is_fel_verified': True,
            'fel_verification_date': fields.Datetime.now(),
            'fel_verification_result': self.verification_message,
            'fel_verification_status': 'valid',
            'sat_name': self.sat_name,
            'sat_status': self.sat_status,
            'sat_address': self.sat_address,
        }
        if self.tax_regime:
            data['tax_regime_gt'] = self.tax_regime
        if not partner.name and self.sat_name:
            data['name'] = self.sat_name
        partner.write(data)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Partner Updated'),
                'message': _('Partner "%s" updated.') % partner.name,
                'type': 'success',
            }
        }

    def action_view_partner(self):
        self.ensure_one()
        if not self.partner_id:
            raise ValidationError(_('No partner to view.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_verify_another(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Verify NIT'),
            'res_model': 'fel.nit.verification.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_create_partner': self.create_partner},
        }

    @api.model
    def action_batch_verify(self, partner_ids):
        partners = self.env['res.partner'].browse(partner_ids)
        verified = 0
        errors = 0
        for partner in partners.filtered(lambda p: p.nit_gt and p.nit_gt != 'CF' and not p.is_fel_verified):
            try:
                wizard = self.create({
                    'nit': partner.nit_gt,
                    'partner_id': partner.id,
                    'update_partner': True,
                })
                wizard.action_verify_nit()
                if wizard.is_verified:
                    wizard.action_update_partner()
                    verified += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                _logger.error(f"Batch error for partner {partner.id}: {str(e)}")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Verification Complete'),
                'message': _('Verified %d, Errors %d') % (verified, errors),
                'type': 'success' if verified > 0 else 'warning',
            }
        }
