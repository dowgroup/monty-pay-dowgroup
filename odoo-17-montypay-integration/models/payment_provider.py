import hashlib
import logging
import requests
from urllib.parse import urljoin

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('montypay', 'MontyPay')],
        ondelete={'montypay': 'set default'}
    )
    
    montypay_merchant_key = fields.Char(
        string="Merchant Key",
        help="MontyPay Merchant Key",
        groups='base.group_system'
    )
    
    montypay_merchant_pass = fields.Char(
        string="Merchant Pass",
        help="MontyPay Merchant Pass for hash generation",
        groups='base.group_system'
    )
    
    montypay_environment = fields.Selection(
        [('sandbox', 'Sandbox'), ('production', 'Production')],
        string="Environment",
        default='sandbox'
    )

    @property 
    def _supported_currencies(self):
        """ Return supported currencies for MontyPay. """
        if self.code == 'montypay':
            return self.env['res.currency'].search([('name', 'in', ['USD', 'EUR', 'GBP'])])
        return super()._supported_currencies

    def _get_default_payment_method_codes(self):
        """ Return default payment method codes for MontyPay. """
        if self.code == 'montypay':
            return ['card']
        return super()._get_default_payment_method_codes()

    # ------ MontyPay helpers ------
    def _get_base_url(self):
        """Return MontyPay API base URL based on environment."""
        # MontyPay provides the same host for sandbox/production in docs,
        # but keep the switch for future-proofing.
        return 'https://checkout.montypay.com'

    def _generate_montypay_hash(self, order_number: str, amount: str, currency: str, description: str) -> str:
        """Compute SHA1(MD5(UPPER(order_number+amount+currency+description+merchant_pass)))."""
        if not self.montypay_merchant_pass:
            raise ValidationError(_("MontyPay: Merchant Pass is not configured."))
        to_concat = f"{order_number}{amount}{currency}{description}{self.montypay_merchant_pass}"
        md5_hex = hashlib.md5(to_concat.upper().encode()).hexdigest()
        sha1_hex = hashlib.sha1(md5_hex.encode()).hexdigest()
        return sha1_hex

    def _montypay_make_request(self, endpoint: str, payload: dict) -> dict:
        url = urljoin(self._get_base_url(), endpoint)
        try:
            resp = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)
            if resp.status_code >= 400:
                # Try to surface MontyPay's error for quicker diagnosis
                try:
                    err = resp.json()
                except ValueError:
                    err = {'raw': resp.text}
                _logger.error("MontyPay API %s returned %s: %s", url, resp.status_code, err)
                raise ValidationError(_(f"MontyPay error {resp.status_code}: {err}"))
            return resp.json()
        except requests.RequestException as e:
            _logger.exception("MontyPay API call failed: %s", e)
            raise ValidationError(_("Could not communicate with MontyPay. Please try again."))

    def _get_payment_link(self, tx_sudo, **kwargs):
        """Create MontyPay session and return redirect URL per MontyPay docs."""
        if self.code != 'montypay':
            return super()._get_payment_link(tx_sudo, **kwargs)

        if not self.montypay_merchant_key:
            raise ValidationError(_("MontyPay: Merchant Key is not configured."))

        base_url = tx_sudo.get_base_url()

        # Order details
        order_number = tx_sudo.reference
        amount_str = f"{tx_sudo.amount:.2f}"
        currency = tx_sudo.currency_id.name
        description = f"Order {order_number}"

        # Generate hash
        session_hash = self._generate_montypay_hash(order_number, amount_str, currency, description)

        # Partner/billing details
        partner = tx_sudo.partner_id
        country_code = (partner.country_id and partner.country_id.code) or 'US'
        address = ', '.join([p for p in [partner.street, partner.city] if p]) or 'N/A'
        phone = partner.phone or partner.mobile or 'N/A'

        payload = {
            'merchant_key': self.montypay_merchant_key,
            'operation': 'purchase',
            'success_url': f"{base_url}/payment/montypay/return",
            'cancel_url': f"{base_url}/payment/montypay/cancel",
            'hash': session_hash,
            'order': {
                'description': description,
                'number': order_number,
                'amount': amount_str,
                'currency': currency,
            },
            'methods': ['card'],
            'billing_address': {
                'country': country_code,
                'address': address,
                'phone': phone,
            },
            'customer': {
                'email': partner.email or 'customer@example.com',
                'name': partner.name or 'Customer',
            },
        }

        _logger.info("Creating MontyPay session for tx %s", order_number)
        response = self._montypay_make_request('/api/v1/session', payload)
        redirect_url = response.get('redirect_url')
        if not redirect_url:
            _logger.error("MontyPay: no redirect_url in response: %s", response)
            raise ValidationError(_("MontyPay: invalid response. No redirect_url provided."))
        return redirect_url
