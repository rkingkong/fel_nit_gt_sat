# -*- coding: utf-8 -*-

from odoo import models, fields, api

class PosConfig(models.Model):
    _inherit = 'pos.config'
    
    # FEL Integration Settings
    use_fel = fields.Boolean(
        string='Use FEL',
        default=True,
        help='Enable FEL integration for this POS'
    )
    
    fel_auto_generate = fields.Boolean(
        string='Auto Generate FEL',
        default=False,
        help='Automatically generate FEL documents when order is completed'
    )
    
    fel_document_type_id = fields.Many2one(
        'fel.document.type',
        string='Default FEL Document Type',
        domain="[('is_invoice', '=', True)]",
        help='Default document type for POS sales'
    )
    
    fel_require_customer = fields.Boolean(
        string='Require Customer',
        default=False,
        help='Require customer information before completing order'
    )
    
    fel_allow_cf = fields.Boolean(
        string='Allow Consumidor Final',
        default=True,
        help='Allow sales to Consumidor Final (CF)'
    )
    
    is_restaurant = fields.Boolean(
        string='Is Restaurant',
        default=False,
        help='Enable restaurant features (tables, waiters, etc.)'
    )
    
    require_waiter = fields.Boolean(
        string='Require Waiter',
        default=False,
        help='Require waiter selection for orders'
    )