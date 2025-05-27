# FEL Guatemala 🇬🇹

[![License: LGPL-3](https://img.shields.io/badge/License-LGPL%20v3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo Version](https://img.shields.io/badge/Odoo-17.0%20Community-875A7B.svg)](https://www.odoo.com)
[![Python Version](https://img.shields.io/badge/Python-3.11%2B-3776AB.svg)](https://www.python.org)
[![AWS Ready](https://img.shields.io/badge/AWS-EC2%20Ready-FF9900.svg)](https://aws.amazon.com/ec2/)

**Factura Electrónica en Línea** - Complete Guatemala SAT compliance for Odoo Community 17

Built specifically for **restaurant operations** and **fast-casual dining** like Kesiyos Restaurant, with full integration for electronic invoicing requirements in Guatemala.

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/rkingkong/fel_nit_gt_sat.git

# Copy to Odoo addons directory
cp -r factura_electronica_gt/fel_nit_gt_sat /path/to/odoo/addons/

# Install Python dependencies
pip install requests xmltodict lxml cryptography

# Update Odoo apps list and install
```

## 📋 Table of Contents

- [Features](#-features)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Restaurant POS Integration](#-restaurant-pos-integration)
- [INFILE Provider Setup](#-infile-provider-setup)
- [SAT Document Types](#-sat-document-types)
- [API Reference](#-api-reference)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features

### 🏢 Core Functionality
- **Complete SAT Compliance** - Full integration with Guatemala's electronic invoicing system
- **NIT Verification** - Real-time customer NIT validation with SAT
- **XML Generation** - Automatic FEL-compliant XML document creation
- **Digital Signature** - Integration with certified providers for document signing
- **Multi-regime Support** - General, Pequeño Contribuyente, and Especial tax regimes

### 🍽️ Restaurant-Specific Features
- **POS Integration** - Seamless Point of Sale electronic invoicing
- **Table Management** - Track orders by table and waiter
- **Consumidor Final** - Support for walk-in customers without NIT
- **Quick Customer Setup** - Easy customer information capture for FEL
- **Batch Processing** - Process multiple orders for FEL at once

### ☁️ Cloud & Infrastructure
- **AWS EC2 Optimized** - Designed for cloud deployment
- **Ubuntu 22 LTS Ready** - Tested on Ubuntu server environments
- **Multi-company Support** - Handle multiple restaurants/locations
- **Scalable Architecture** - Handles high-volume restaurant operations

## 🔧 Installation

### Prerequisites

- **Odoo 17.0 Community Edition**
- **Python 3.11+**
- **PostgreSQL 12+**
- **Ubuntu 22 LTS** (recommended)

### Python Dependencies

```bash
pip install requests xmltodict lxml cryptography
```

### Odoo Dependencies

Ensure these modules are installed:
- `base` (core)
- `account` (accounting)
- `point_of_sale` (POS)
- `l10n_gt` (Guatemala localization)

### Installation Steps

1. **Clone the Repository**
   ```bash
   git clone https://github.com/rkingkong/fel_nit_gt_sat.git
   cd fel_nit_gt_sat
   ```

2. **Copy Module to Odoo**
   ```bash
   cp -r fel_nit_gt_sat /path/to/odoo/addons/
   ```

3. **Update Apps List**
   - Go to Apps menu in Odoo
   - Click "Update Apps List"
   - Search for "FEL Guatemala"
   - Click Install

4. **Configure Module**
   - Navigate to FEL Guatemala menu
   - Complete the configuration wizard

## ⚙️ Configuration

### 1. Company Setup

Navigate to **FEL Guatemala > Configuration > FEL Configuration**

```
Company NIT: [Your company's NIT]
Tax Regime: [General/Pequeño/Especial]
Environment: [Test/Production]
```

### 2. Provider Configuration

The module comes pre-configured with **INFILE, S.A.** provider:

| Setting | Value |
|---------|--------|
| Setup Cost | Q. 995.00 (one-time) |
| Cost per DTE | Q. 0.33 |
| Annual Limit | 1,200 DTEs |
| Annual Cost | Q. 396.00 |

### 3. API Credentials

```
API URL: https://api.infile.com.gt
Username: [Your INFILE username]
Password: [Your INFILE password]
Token: [Your API token]
```

### 4. Restaurant POS Setup

For restaurant operations:

```
POS Configuration:
✅ Use FEL
✅ Allow Consumidor Final
✅ Is Restaurant
✅ Require Waiter
```

## 🍕 Restaurant POS Integration

### Order Workflow

1. **Create Order** - Waiter creates order on POS
2. **Set Table** - Assign table number
3. **Add Items** - Add food/beverage items
4. **Complete Order** - Process payment
5. **Customer Info** - Set customer NIT or use "CF"
6. **Send to FEL** - Generate electronic invoice

### Customer Types

| Customer Type | NIT | Document Type | Use Case |
|---------------|-----|---------------|----------|
| Consumidor Final | CF | FACT | Walk-in customers |
| Pequeño Contribuyente | Valid NIT | FPEQ | Small businesses |
| General/Especial | Valid NIT | FACT/FESP | Regular businesses |

### Table Management

```python
# POS Order with restaurant data
{
    'table_number': 'Mesa 5',
    'waiter_id': user_waiter_juan,
    'customer_nit': 'CF',
    'customer_name': 'Consumidor Final'
}
```

## 🏢 INFILE Provider Setup

### Pricing Structure (October 2024 Proposal)

| Item | Cost |
|------|------|
| **Setup Fee** | Q. 995.00 (one-time) |
| **Annual Base** | Q. 396.00 |
| **DTE Quota** | 1,200 documents/year |
| **Additional DTEs** | Q. 0.33 each |
| **IVA** | 12% included |
| **Payment Terms** | 8 days credit |

### Required Documentation

1. **Company Documents**
   - Copy of business license (Patente)
   - Company registration (Sociedad)
   - RTU (Tax Registration)

2. **Legal Representative**
   - Power of attorney (Nombramiento)
   - DPI copy

3. **Contract**
   - 1-year commitment required
   - Automatic renewal

### API Endpoints

```
Test Environment: https://test-api.infile.com.gt
Production: https://api.infile.com.gt

Endpoints:
- POST /api/v1/nit/verify - NIT verification
- POST /api/v1/dte/certify - Document certification
- GET /api/v1/dte/{uuid} - Document status
```

## 📄 SAT Document Types

### Invoice Types

| Code | Name | Usage |
|------|------|-------|
| **FACT** | Factura | Standard invoice (General/Especial) |
| **FCAM** | Factura Cambiaria | Exchange invoice |
| **FPEQ** | Factura Pequeño Contribuyente | Small taxpayer invoice |
| **FCAP** | Factura Cambiaria Pequeño | Small taxpayer exchange |
| **FESP** | Factura Especial | Special regime invoice |

### Credit/Debit Notes

| Code | Name | Usage |
|------|------|-------|
| **NCRE** | Nota de Crédito | Credit note (returns/adjustments) |
| **NDEB** | Nota de Débito | Debit note (additional charges) |
| **NABN** | Nota de Abono | Payment note |

### Receipts

| Code | Name | Usage |
|------|------|-------|
| **RECI** | Recibo | General receipt |
| **RDON** | Recibo por Donación | Donation receipt |

## 🔗 API Reference

### NIT Verification

```python
# Verify customer NIT
verification_service = self.env['fel.nit.verification.service']
result = verification_service.verify_nit(nit, fel_config)

# Result structure
{
    'verified': True,
    'name': 'Company Name',
    'regime': 'GENERAL',
    'status': 'ACTIVO',
    'message': 'NIT verified successfully'
}
```

### Document Generation

```python
# Create FEL document
fel_doc = self.env['fel.document'].create({
    'invoice_id': invoice.id,
    'partner_id': partner.id,
    'document_type_id': doc_type.id,
    'company_id': company.id,
})

# Generate XML and send
fel_doc.generate_xml()
fel_doc.send_to_provider()
```

### POS Integration

```python
# Send POS order to FEL
pos_order.write({
    'customer_nit': 'CF',
    'customer_name': 'Consumidor Final'
})
pos_order.send_to_fel()
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. NIT Verification Fails
```
Error: "Invalid NIT format"
Solution: Ensure NIT has 8-9 digits, use CF for Consumidor Final
```

#### 2. API Connection Timeout
```
Error: "Connection timeout"
Solution: Check internet connection and API credentials
```

#### 3. XML Generation Error
```
Error: "Invalid document type"
Solution: Verify document type matches customer tax regime
```

#### 4. POS FEL Integration
```
Error: "Customer NIT required"
Solution: Set customer NIT or use CF for walk-in customers
```

### Log Files

Check Odoo logs for detailed error information:

```bash
tail -f /var/log/odoo/odoo.log | grep FEL
```

### Debug Mode

Enable debug mode for detailed error tracking:

```python
import logging
_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)
```

## 🚀 Deployment

### AWS EC2 Deployment

1. **Launch EC2 Instance**
   ```bash
   # Ubuntu 22 LTS
   # t3.medium or larger for restaurant operations
   # Security groups: HTTP (80), HTTPS (443), SSH (22)
   ```

2. **Install Dependencies**
   ```bash
   sudo apt update
   sudo apt install python3-pip postgresql nginx
   pip3 install odoo
   ```

3. **Configure Odoo**
   ```bash
   # Copy module to addons directory
   sudo cp -r fel_nit_gt_sat /opt/odoo/addons/
   
   # Restart Odoo service
   sudo systemctl restart odoo
   ```

4. **SSL Certificate**
   ```bash
   # Use Let's Encrypt for HTTPS
   sudo certbot --nginx -d yourdomain.com
   ```

### Production Checklist

- [ ] INFILE production API credentials configured
- [ ] SSL certificate installed
- [ ] Database backups configured
- [ ] Monitoring setup (CloudWatch)
- [ ] Firewall rules configured
- [ ] Regular security updates scheduled

## 📊 Usage Statistics

### Kesiyos Restaurant Metrics

```
Daily Orders: ~200 orders
Monthly DTEs: ~6,000 documents
Annual Usage: ~72,000 DTEs

INFILE Cost Analysis:
- Base: Q. 396/year
- Additional DTEs: (72,000 - 1,200) × Q. 0.33 = Q. 23,364
- Total Annual Cost: ~Q. 23,760 + IVA
```

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

### Development Setup

```bash
# Clone repository
git clone https://github.com/rkingkong/factura_electronica_gt.git
cd factura_electronica_gt

# Create development branch
git checkout -b feature/your-feature-name

# Make changes and test
# Submit pull request
```

### Code Standards

- Follow PEP 8 for Python code
- Use meaningful variable names
- Add docstrings for all methods
- Include unit tests for new features
- Update documentation

### Testing

```bash
# Run Odoo tests
python3 odoo-bin -d test_db -i fel_nit_gt_sat --test-enable --stop-after-init

# Run specific test
python3 odoo-bin -d test_db --test-tags fel_nit_gt_sat
```

## 📞 Support

### Community Support

- **GitHub Issues**: [Report bugs and feature requests](https://github.com/rkingkong/fel_nit_gt_sat/issues)
- **Discussions**: [Community discussions](https://github.com/rkingkong/fel_nit_gt_sat/discussions)

### Commercial Support

For Kesiyos Restaurant and commercial implementations:

- **Email**: rkong@armku.us
- **AWS Deployment**: Professional deployment services available
- **Odoo Consultation**: Professional consulting services available

### INFILE Support

- **Contact**: Zayda Karina Sontay Herrera
- **Email**: zherrera@infile.com.gt
- **Phone**: 2208-2208 Ext 2426

## 📜 License

This project is licensed under the **GNU Lesser General Public License v3.0** (LGPL-3).

```
FEL Guatemala - Electronic Invoice Integration for Odoo
Copyright (C) 2024 Kesiyos Restaurant Systems

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Lesser General Public License for more details.
```

## 🙏 Acknowledgments

- **INFILE, S.A.** - FEL certification provider
- **SAT Guatemala** - Electronic invoicing regulations
- **Odoo Community** - Open-source ERP platform
- **Kesiyos Restaurant** - Real-world testing and requirements

## 📈 Roadmap

### Version 1.1 (Planned)
- [ ] Additional FEL providers support
- [ ] Advanced reporting and analytics
- [ ] Mobile app integration
- [ ] Webhook support for real-time updates

### Version 1.2 (Future)
- [ ] Multi-currency support
- [ ] Advanced tax calculations
- [ ] Integration with delivery platforms
- [ ] AI-powered NIT validation

---

**Made with ❤️ for Guatemala's restaurant industry**

*Supporting local businesses with world-class technology on AWS infrastructure*
