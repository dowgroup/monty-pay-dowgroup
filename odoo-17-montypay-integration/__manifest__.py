{
    'name': 'MontyPay Payment Gateway',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'MontyPay Payment Gateway Integration',
    'description': 'MontyPay Payment Gateway Integration for Odoo Website eCommerce',
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': ['payment', 'website_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}