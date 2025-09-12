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
        """ Handle return from MontyPay payment page. """
        _logger.info("MontyPay return received")
        return http.request.redirect('/payment/process')

    @http.route('/payment/montypay/cancel', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def montypay_cancel(self, **kwargs):
        """ Handle cancellation from MontyPay payment page. """
        _logger.info("MontyPay cancellation received")
        return http.request.redirect('/payment/process')