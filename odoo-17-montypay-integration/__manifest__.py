{
    'name': 'MontyPay Payment Gateway',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'MontyPay Payment Gateway Integration for Odoo Website eCommerce',
    'description': """
MontyPay Payment Gateway Integration
====================================

This module integrates MontyPay payment gateway with Odoo Website eCommerce checkout.

Features:
- Complete integration with MontyPay payment gateway
- Support for sandbox and production environments
- Secure payment processing with hash validation
- Webhook support for payment status updates
- Seamless checkout experience like Stripe integration
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': [
        'payment',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/payment_provider_data.xml',
        'views/payment_provider_views.xml',
        'views/payment_montypay_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_montypay/static/src/css/payment_montypay.css',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
}
