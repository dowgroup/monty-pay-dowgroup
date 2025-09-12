import hashlib
import json
import logging
import requests
from urllib.parse import urljoin

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('montypay', 'MontyPay')],
        ondelete={'montypay': 'set default'}
    )
    
    # MontyPay specific configuration fields
    montypay_merchant_key = fields.Char(
        string="Merchant Key",
        help="MontyPay Merchant Key",
        required_if_provider='montypay',
        groups='base.group_system'
    )
    
    montypay_merchant_pass = fields.Char(
        string="Merchant Pass",
        help="MontyPay Merchant Pass for hash generation",
        required_if_provider='montypay',
        groups='base.group_system'
    )
    
    montypay_environment = fields.Selection(
        [('sandbox', 'Sandbox'), ('production', 'Production')],
        string="Environment",
        default='sandbox',
        required_if_provider='montypay'
    )

    @api.model
    def _get_compatible_providers(self, *args, company_id=None, **kwargs):
        """ Override to include MontyPay in compatible providers. """
        providers = super()._get_compatible_providers(*args, company_id=company_id, **kwargs)
        return providers.filtered(lambda p: p.code != 'montypay' or p.state != 'disabled')

    def _get_base_url(self):
        """ Return the base URL for MontyPay API based on environment. """
        if self.montypay_environment == 'production':
            return 'https://checkout.montypay.com'
        else:
            return 'https://checkout.montypay.com'  # Use same URL for now, adjust if needed

    def _generate_montypay_hash(self, order_number, order_amount, order_currency, order_description):
        """ Generate MontyPay hash using SHA1(MD5(concatenated_string)). """
        # Concatenate parameters as per MontyPay documentation
        to_hash = f"{order_number}{order_amount}{order_currency}{order_description}{self.montypay_merchant_pass}"
        
        # Generate MD5 hash first, then SHA1
        md5_hash = hashlib.md5(to_hash.upper().encode()).hexdigest()
        sha1_hash = hashlib.sha1(md5_hash.encode()).hexdigest()
        
        return sha1_hash

    def _montypay_make_request(self, endpoint, payload=None):
        """ Make HTTP request to MontyPay API. """
        url = urljoin(self._get_base_url(), endpoint)
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error("MontyPay API request failed: %s", e)
            raise ValidationError(_("Payment communication error. Please try again."))

    def _get_supported_currencies(self):
        """ Return supported currencies for MontyPay. """
        montypay_currencies = ['USD', 'EUR', 'GBP']  # Add more as supported
        if self.code == 'montypay':
            return montypay_currencies
        return super()._get_supported_currencies()

    def _get_default_payment_method_codes(self):
        """ Return default payment method codes for MontyPay. """
        if self.code == 'montypay':
            return ['card']
        return super()._get_default_payment_method_codes()

    def _get_payment_link(self, tx_sudo, **kwargs):
        """ Create MontyPay payment session and return redirect URL. """
        if self.code != 'montypay':
            return super()._get_payment_link(tx_sudo, **kwargs)

        # Prepare order data
        order_data = {
            'number': tx_sudo.reference,
            'amount': f"{tx_sudo.amount:.2f}",
            'currency': tx_sudo.currency_id.name,
            'description': f"Order {tx_sudo.reference}"
        }

        # Generate hash
        hash_value = self._generate_montypay_hash(
            order_data['number'],
            order_data['amount'],
            order_data['currency'],
            order_data['description']
        )

        # Prepare payment session payload
        payload = {
            'merchant_key': self.montypay_merchant_key,
            'operation': 'purchase',
            'success_url': urljoin(tx_sudo.get_base_url(), '/payment/montypay/return'),
            'cancel_url': urljoin(tx_sudo.get_base_url(), '/payment/montypay/cancel'),
            'hash': hash_value,
            'order': order_data,
            'billing_address': {
                'country': tx_sudo.partner_country_id.code or 'US',
                'address': tx_sudo.partner_address or 'N/A',
                'phone': tx_sudo.partner_phone or 'N/A'
            },
            'customer': {
                'email': tx_sudo.partner_email,
                'name': tx_sudo.partner_name
            }
        }

        # Add ZIP if available
        if tx_sudo.partner_zip:
            payload['billing_address']['zip'] = tx_sudo.partner_zip

        _logger.info("Creating MontyPay payment session for transaction %s", tx_sudo.reference)
        
        try:
            response = self._montypay_make_request('/api/v1/session', payload)
            redirect_url = response.get('redirect_url')
            
            if not redirect_url:
                raise ValidationError(_("Invalid response from MontyPay API"))
                
            _logger.info("MontyPay session created successfully for transaction %s", tx_sudo.reference)
            return redirect_url
            
        except Exception as e:
            _logger.error("Failed to create MontyPay payment session: %s", e)
            raise ValidationError(_("Unable to create payment session. Please try again."))

    def _process_feedback_data(self, data):
        """ Process feedback data from MontyPay. """
        if self.code != 'montypay':
            return super()._process_feedback_data(data)

        # Extract transaction reference from feedback data
        reference = data.get('order_number') or data.get('reference')
        if not reference:
            _logger.warning("MontyPay feedback missing transaction reference")
            return

        tx_sudo = self.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'montypay')
        ])

        if not tx_sudo:
            _logger.warning("No transaction found for MontyPay feedback with reference %s", reference)
            return

        # Update transaction state based on feedback
        status = data.get('status', '').lower()
        
        if status == 'success':
            tx_sudo._set_done()
            _logger.info("MontyPay transaction %s marked as done", reference)
        elif status in ['failed', 'error', 'declined']:
            tx_sudo._set_error(_("Payment was declined or failed"))
            _logger.info("MontyPay transaction %s marked as failed", reference)
        elif status == 'pending':
            tx_sudo._set_pending()
            _logger.info("MontyPay transaction %s marked as pending", reference)
        else:
            _logger.warning("Unknown MontyPay status '%s' for transaction %s", status, reference)

        return tx_sudo
