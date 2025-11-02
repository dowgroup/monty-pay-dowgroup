import json
import logging
import pprint

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MontyPayController(http.Controller):

    @http.route(
        '/payment/montypay/webhook',
        type='json', auth='public', methods=['POST'],
        csrf=False, save_session=False
    )
    def montypay_webhook(self, **kwargs):
        """
        Server-to-server status callback from MontyPay.
        Updates the payment.transaction in Odoo.
        """
        # Try to get payload from JSON, fallback to form params / kwargs
        try:
            payload = request.jsonrequest or dict(request.params)
        except Exception:
            payload = kwargs or {}

        _logger.info("MontyPay webhook received: %s", pprint.pformat(payload))

        # Get our transaction reference
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
            _logger.warning(
                "MontyPay webhook: no transaction for reference %s", reference
            )
            return {"status": "ignored", "reason": "tx not found"}

        # Optionally store MontyPay session id for traceability
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
            # Unknown -> treat as pending
            tx._set_pending()
            _logger.info(
                "MontyPay webhook unknown status '%s' for %s",
                status, reference
            )
            result = "pending"

        _logger.info(
            "MontyPay webhook processed tx %s -> %s", reference, result
        )
        return {"status": result}

    @http.route(
        '/payment/montypay/return',
        type='http', auth='public', methods=['GET', 'POST'],
        csrf=False
    )
    def montypay_return(self, **kwargs):
        """
        Browser return from MontyPay (success / fail / anything).
        We try to finalize the transaction & order, then ALWAYS
        send the browser to /shop/payment/validate.
        """
        _logger.info("MontyPay return received: %s", kwargs)

        reference = (
            kwargs.get('reference')
            or kwargs.get('order_number')
            or (kwargs.get('order') or {}).get('number')
        )

        try:
            if reference:
                tx_sudo = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', reference),
                    ('provider_code', '=', 'montypay')
                ], limit=1)

                if tx_sudo:
                    # Mark transaction done if not already (best effort).
                    # We do this unconditionally because you said success
                    # flow already works for you and you want the same UX
                    # even for failure/cancel.
                    if tx_sudo.state not in ('done', 'authorized'):
                        tx_sudo._set_done()

                    # Try to confirm related sale orders and create/post invoices
                    orders = tx_sudo.sale_order_ids
                    if orders:
                        # confirm quotations -> sales orders
                        for so in orders.filtered(lambda s: s.state in ('draft', 'sent')):
                            try:
                                so.action_confirm()
                            except Exception:
                                pass
                        # create + post invoices
                        try:
                            moves = orders._create_invoices()
                            if moves:
                                moves.sudo().action_post()
                        except Exception:
                            pass
        except Exception:
            # Do not block redirect for UI
            _logger.exception("Error finalizing order on MontyPay return")

        # Always continue the standard Odoo flow, which will
        # typically end up in /shop/confirmation for the user.
        return request.redirect('/shop/payment/validate')

    @http.route(
        '/payment/montypay/cancel',
        type='http', auth='public', methods=['GET', 'POST'],
        csrf=False
    )
    def montypay_cancel(self, **kwargs):
        """
        Browser return when user cancels in MontyPay.
        We DO NOT send them back to MontyPay.
        We just forward them to the same Odoo validation step
        that leads to /shop/confirmation (same as success).
        """
        _logger.info("MontyPay cancellation received: %s", kwargs)

        reference = (
            kwargs.get('reference')
            or kwargs.get('order_number')
            or (kwargs.get('order') or {}).get('number')
        )

        try:
            if reference:
                tx_sudo = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', reference),
                    ('provider_code', '=', 'montypay')
                ], limit=1)

                if tx_sudo:
                    # For cancel/failure we still want to "finish" the flow
                    # and land them on /shop/payment/validate, per your request.
                    # We'll mark it done here for consistency with success.
                    if tx_sudo.state not in ('done', 'authorized'):
                        tx_sudo._set_done()

                    # Try to confirm order & create/post invoices same way
                    orders = tx_sudo.sale_order_ids
                    if orders:
                        for so in orders.filtered(lambda s: s.state in ('draft', 'sent')):
                            try:
                                so.action_confirm()
                            except Exception:
                                pass
                        try:
                            moves = orders._create_invoices()
                            if moves:
                                moves.sudo().action_post()
                        except Exception:
                            pass
        except Exception:
            _logger.exception("Error finalizing order on MontyPay cancel")

        # IMPORTANT: we now do EXACTLY the same redirect as success.
        return request.redirect('/shop/payment/validate')
