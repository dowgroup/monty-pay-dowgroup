import json
import logging
import pprint

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MontyPayController(http.Controller):

    @http.route('/payment/montypay/webhook', type='json', auth='public', methods=['POST'], csrf=False, save_session=False)
    def montypay_webhook(self, **kwargs):
        """Webhook endpoint to receive MontyPay payment status callbacks.

        Accepts JSON or form-encoded payloads. Expected keys include at
        least a transaction reference and a status, e.g.:
        - reference / order_number / order.number
        - status: success | approved | pending | failed | error | declined
        """
        # Extract raw body (works for JSON and form) for logging/troubleshooting
        try:
            payload = request.jsonrequest or dict(request.params)
        except Exception:
            payload = kwargs or {}

        _logger.info("MontyPay webhook received: %s", pprint.pformat(payload))

        # Normalize reference
        reference = (
            payload.get('reference')
            or payload.get('order_number')
            or (payload.get('order') or {}).get('number')
        )

        if not reference:
            _logger.warning("MontyPay webhook missing reference: %s", payload)
            return {"status": "ignored", "reason": "missing reference"}

        tx = request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'montypay')
        ], limit=1)

        if not tx:
            _logger.warning("MontyPay webhook: no transaction for reference %s", reference)
            return {"status": "ignored", "reason": "tx not found"}

        # Optional: store MontyPay session/ids if available
        session_id = payload.get('session_id') or payload.get('id')
        if session_id and hasattr(tx, 'montypay_session_id'):
            tx.write({'montypay_session_id': session_id})

        status = (payload.get('status') or '').lower()
        if status in ('success', 'approved'):
            tx._set_done()
            result = "done"
        elif status in ('pending', 'in_progress', 'processing'):
            tx._set_pending()
            result = "pending"
        elif status in ('failed', 'error', 'declined', 'canceled', 'cancelled'):
            tx._set_error("MontyPay reported status: %s" % status)
            result = "error"
        else:
            # Unknown status; mark pending but log it for follow-up
            tx._set_pending()
            _logger.info("MontyPay webhook unknown status '%s' for %s", status, reference)
            result = "pending"

        _logger.info("MontyPay webhook processed tx %s -> %s", reference, result)
        return {"status": result}

    @http.route('/payment/montypay/return', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def montypay_return(self, **kwargs):
        """Handle return from MontyPay payment page and go to order confirmation."""
        _logger.info("MontyPay return received: %s", kwargs)
        reference = kwargs.get('reference') or kwargs.get('order_number')
        try:
            if reference:
                tx_sudo = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', reference),
                    ('provider_code', '=', 'montypay')
                ], limit=1)
                if tx_sudo:
                    # Consider the transaction done at this point; webhooks will confirm
                    # but we complete the order flow immediately for the customer.
                    if tx_sudo.state not in ('done', 'authorized'):
                        tx_sudo._set_done()
        except Exception:
            # Don't block the user flow on feedback parsing
            pass
        # Go to standard confirmation step
        return request.redirect('/shop/confirmation')

    @http.route('/payment/montypay/cancel', type='http', auth='public', methods=['GET', 'POST'], csrf=False)
    def montypay_cancel(self, **kwargs):
        """Handle cancellation from MontyPay and return to payment step."""
        _logger.info("MontyPay cancellation received: %s", kwargs)
        return request.redirect('/shop/payment')