import logging
from odoo import http

_logger = logging.getLogger(__name__)


class MontyPayController(http.Controller):

    @http.route('/payment/montypay/webhook', type='http', auth='public', methods=['POST'], csrf=False)
    def montypay_webhook(self, **post):
        """ Handle MontyPay webhook notifications. """
        _logger.info("MontyPay webhook received")
        return "OK"

    @http.route('/payment/montypay/return', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def montypay_return(self, **kwargs):
        """Handle return from MontyPay payment page and go to order confirmation."""
        _logger.info("MontyPay return received: %s", kwargs)
        reference = kwargs.get('order_number') or kwargs.get('reference')
        try:
            if reference:
                tx_sudo = http.request.env['payment.transaction'].sudo().search([
                    ('reference', '=', reference),
                    ('provider_code', '=', 'montypay')
                ], limit=1)
                if tx_sudo:
                    tx_sudo._process_notification_data(kwargs)
        except Exception:
            # Don't block the user flow on feedback parsing
            pass
        # Go to standard confirmation step
        return http.request.redirect('/shop/payment/validate')

    @http.route('/payment/montypay/cancel', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def montypay_cancel(self, **kwargs):
        """Handle cancellation from MontyPay and return to payment step."""
        _logger.info("MontyPay cancellation received: %s", kwargs)
        return http.request.redirect('/shop/payment')