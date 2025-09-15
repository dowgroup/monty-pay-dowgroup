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

    def _get_payment_link(self, tx_sudo, **kwargs):
        """ Create MontyPay payment session and return redirect URL. """
        if self.code != 'montypay':
            return super()._get_payment_link(tx_sudo, **kwargs)

        # Simple test implementation - replace with real MontyPay API call
        base_url = tx_sudo.get_base_url()
        test_url = f"https://checkout.montypay.com/test?reference={tx_sudo.reference}&amount={tx_sudo.amount}&return_url={base_url}/payment/montypay/return"
        return test_url
