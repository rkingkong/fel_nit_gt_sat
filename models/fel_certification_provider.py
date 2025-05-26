class FelCertificationProvider(models.Model):
    _name = 'fel.certification.provider'
    _description = 'FEL Certification Provider'
    
    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code', required=True)
    website = fields.Char(string='Website')
    
    # API Configuration
    api_base_url = fields.Char(string='API Base URL')
    api_version = fields.Char(string='API Version')
    
    # Supported Features
    supports_nit_verification = fields.Boolean(string='Supports NIT Verification', default=True)
    supports_xml_generation = fields.Boolean(string='Supports XML Generation', default=True)
    supports_digital_signature = fields.Boolean(string='Supports Digital Signature', default=True)
    
    # Contact Information
    contact_name = fields.Char(string='Contact Name')
    contact_email = fields.Char(string='Contact Email')
    contact_phone = fields.Char(string='Contact Phone')
    
    @api.model
    def get_infile_provider(self):
        """Get or create INFILE provider"""
        provider = self.search([('code', '=', 'infile')], limit=1)
        if not provider:
            provider = self.create({
                'name': 'INFILE, S.A.',
                'code': 'infile',
                'website': 'https://www.infile.com',
                'api_base_url': 'https://api.infile.com',
                'contact_email': 'zherrera@infile.com.gt',
                'contact_phone': '2208-2208',
            })
        return provider
