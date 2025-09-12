# MontyPay Payment Gateway Integration for Odoo 17

This module integrates MontyPay payment gateway with Odoo 17 Community Edition's Website eCommerce functionality.

## Features

- ✅ Complete MontyPay payment gateway integration
- ✅ Supports sandbox and production environments
- ✅ Secure hash-based authentication (SHA1/MD5)
- ✅ Webhook support for real-time payment status updates
- ✅ Seamless checkout experience similar to Stripe integration
- ✅ Support for major credit/debit cards (Visa, MasterCard, AMEX, Discover)
- ✅ Responsive design and modern UI
- ✅ Full transaction tracking and management

## Installation

1. **Copy the module** to your Odoo addons directory:
   ```bash
   cp -r payment_montypay /path/to/odoo/addons/
   ```

2. **Update the addons list** in Odoo:
   - Go to Apps → Update Apps List
   - Search for "MontyPay"
   - Install the module

3. **Add MontyPay brand assets** (Optional):
   - Add `static/src/img/montypay_logo.png` (200x60px recommended)
   - Add `static/src/img/montypay_icon.png` (32x32px recommended)
   - Update templates to use these images if desired

## Configuration

### 1. Enable MontyPay Payment Provider

1. Navigate to **Invoicing → Configuration → Payment Providers**
2. Find "MontyPay" and click to edit
3. Set the provider to **Enabled**
4. Configure the following fields:

   - **Merchant Key**: Your MontyPay merchant key (e.g., `899de86c-6b8f-11f0-9e25-6ecbc8c8662d`)
   - **Merchant Pass**: Your MontyPay merchant password for hash generation
   - **Environment**: Choose `Sandbox` for testing or `Production` for live transactions

### 2. Configure Webhook URL

Configure your MontyPay dashboard to send webhooks to:
```
https://yourdomain.com/payment/montypay/webhook
```

## API Integration Details

### Hash Generation
The module generates secure hashes using MontyPay's required format:
```
SHA1(MD5(order_number + order_amount + order_currency + order_description + merchant_pass))
```

### Supported Endpoints
- **Session Creation**: `POST /api/v1/session`
- **Webhook Handler**: `POST /payment/montypay/webhook`
- **Return URL**: `GET/POST /payment/montypay/return`
- **Cancel URL**: `GET/POST /payment/montypay/cancel`

### Payment Flow

1. **Checkout**: Customer selects MontyPay on checkout page
2. **Session Creation**: Module creates payment session with MontyPay API
3. **Redirection**: Customer is redirected to MontyPay payment page
4. **Payment**: Customer completes payment on MontyPay's secure page
5. **Webhook**: MontyPay sends real-time status updates via webhook
6. **Return**: Customer is redirected back to Odoo with payment result
7. **Confirmation**: Order is confirmed and customer receives confirmation

## Testing

### Test Environment
Use MontyPay's sandbox environment for testing:
- Set Environment to "Sandbox"
- Use test credentials provided by MontyPay
- Test with cards from: [Mastercard Test Cards](https://test-gateway.mastercard.com/api/documentation/integrationGuidelines/supportedFeatures/testAndGoLive.html)

### Test Cards
Refer to MontyPay's documentation for approved test card numbers.

## Supported Currencies
The module supports all currencies available in your Odoo installation. MontyPay typically supports:
- USD (US Dollar)
- EUR (Euro)  
- GBP (British Pound)
- And other major currencies depending on your MontyPay account configuration

*Currency support depends on your MontyPay account settings and active currencies in Odoo.*

## File Structure
```
payment_montypay/
├── __init__.py
├── __manifest__.py
├── README.md
├── controllers/
│   ├── __init__.py
│   └── main.py
├── data/
│   └── payment_provider_data.xml
├── models/
│   ├── __init__.py
│   ├── payment_provider.py
│   └── payment_transaction.py
├── security/
│   └── ir.model.access.csv
├── static/
│   └── src/
│       ├── css/
│       │   └── payment_montypay.css
│       └── img/
│           ├── montypay_logo.png
│           └── montypay_icon.png
└── views/
    ├── payment_provider_views.xml
    └── payment_montypay_templates.xml
```

## Security

- All sensitive credentials are stored securely with password fields
- Hash validation ensures payment integrity
- Webhook validation prevents unauthorized status updates
- CSRF protection on all forms

## Troubleshooting

### Common Issues

1. **"Payment communication error"**
   - Check internet connectivity
   - Verify MontyPay credentials
   - Ensure MontyPay API is accessible

2. **"No transaction found"**
   - Check webhook URL configuration
   - Verify transaction reference format
   - Check Odoo logs for detailed errors

3. **"Invalid hash"**
   - Verify merchant pass configuration
   - Check order details formatting
   - Ensure string concatenation is correct

### Logging

Enable debug logging to troubleshoot issues:
```python
# Add to Odoo configuration
log_level = debug
log_handler = :DEBUG
```

## Support

For MontyPay-specific issues:
- Documentation: https://docs.montypay.com/checkout_integration
- Webhook Guide: https://docs.montypay.com/checkout_integration#callback-notification

For Odoo integration issues:
- Check Odoo logs in debug mode
- Review transaction records in Payment Transactions menu
- Verify webhook URL is reachable from MontyPay servers

## License

This module is licensed under LGPL-3.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

**Note**: Add MontyPay brand assets for a professional appearance. Contact MontyPay for official logos and branding guidelines. The module works without images using text-based branding.
