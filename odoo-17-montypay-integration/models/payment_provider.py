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

    def _get_payment_link(self, tx_sudo, **kwargs):
        """ Create MontyPay payment session and return redirect URL. """
        if self.code != 'montypay':
            return super()._get_payment_link(tx_sudo, **kwargs)

        # Simple implementation - return a test URL for now
        return 'https://checkout.montypay.com/test'