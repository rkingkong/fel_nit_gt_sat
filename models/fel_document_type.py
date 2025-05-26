class FelDocumentType(models.Model):
    _name = 'fel.document.type'
    _description = 'FEL Document Type'
    
    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')
    
    # Document Configuration
    is_invoice = fields.Boolean(string='Is Invoice')
    is_credit_note = fields.Boolean(string='Is Credit Note')
    is_debit_note = fields.Boolean(string='Is Debit Note')
    is_receipt = fields.Boolean(string='Is Receipt')
    
    # Tax Regime Compatibility
    available_for_general = fields.Boolean(string='Available for General Regime', default=True)
    available_for_pequeno = fields.Boolean(string='Available for Pequeño Contribuyente', default=True)
    available_for_especial = fields.Boolean(string='Available for Special Regime', default=True)
    
    # Template Configuration
    xml_template = fields.Text(string='XML Template')
    
    @api.model
    def get_document_type_by_code(self, code):
        """Get document type by code"""
        return self.search([('code', '=', code)], limit=1)
