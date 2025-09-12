import json
import logging
import pprint

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MontyPayController(http.Controller):

    _webhook_url = '/payment/montypay/webhook'
    _return_url = '/payment/montypay/return'
    _cancel_url = '/payment/montypay/cancel'

    @http.route(_webhook_url, type='http', auth='public', methods=['POST'], csrf=False, save_session=False)
    def montypay_webhook(self, **post):
        """ Handle MontyPay webhook notifications. """
        _logger.info("Received MontyPay webhook notification")
        _logger.debug("MontyPay webhook data:\n%s", pprint.pformat(post))

        try:
            # Get the payment provider
            provider_sudo = request.env['payment.provider'].sudo().search([
                ('code', '=', 'montypay'),
                ('state', '!=', 'disabled')
            ], limit=1)

            if not provider_sudo:
                _logger.error("No active MontyPay provider found")
                return "No active provider found", 400

            # Process the webhook data
            provider_sudo._process_feedback_data(post)
            
            _logger.info("MontyPay webhook processed successfully")
            return "OK"

        except Exception as e:
            _logger.error("Error processing MontyPay webhook: %s", e)
            return "Error processing webhook", 500

    @http.route(_return_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def montypay_return(self, **kwargs):
        """ Handle return from MontyPay payment page. """
        _logger.info("MontyPay return URL accessed")
        _logger.debug("MontyPay return data:\n%s", pprint.pformat(kwargs))

        try:
            # Get transaction reference from return data
            reference = kwargs.get('order_number') or kwargs.get('reference')
            
            if not reference:
                _logger.warning("MontyPay return missing transaction reference")
                return request.redirect('/payment/process')

            # Find the transaction
            tx_sudo = request.env['payment.transaction'].sudo().search([
                ('reference', '=', reference),
                ('provider_code', '=', 'montypay')
            ], limit=1)

            if not tx_sudo:
                _logger.warning("No transaction found for reference %s", reference)
                return request.redirect('/payment/process')

            # Process return data if available
            if kwargs:
                provider_sudo = tx_sudo.provider_id
                provider_sudo._process_feedback_data(kwargs)

            # Redirect to payment process page
            return request.redirect('/payment/process')

        except Exception as e:
            _logger.error("Error processing MontyPay return: %s", e)
            return request.redirect('/payment/process')

    @http.route(_cancel_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def montypay_cancel(self, **kwargs):
        """ Handle cancellation from MontyPay payment page. """
        _logger.info("MontyPay cancel URL accessed")
        _logger.debug("MontyPay cancel data:\n%s", pprint.pformat(kwargs))

        try:
            # Get transaction reference from cancel data
            reference = kwargs.get('order_number') or kwargs.get('reference')
            
            if reference:
                # Find and cancel the transaction
                tx_sudo = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', reference),
                    ('provider_code', '=', 'montypay')
                ], limit=1)

                if tx_sudo:
                    tx_sudo._set_canceled("Payment was canceled by user")
                    _logger.info("Transaction %s canceled by user", reference)

            # Redirect to payment process page
            return request.redirect('/payment/process')

        except Exception as e:
            _logger.error("Error processing MontyPay cancellation: %s", e)
            return request.redirect('/payment/process')
