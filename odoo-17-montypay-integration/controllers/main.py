# -*- coding: utf-8 -*-

import json
import logging
import pprint

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class MontyPayController(http.Controller):

    def _get_tx_from_reference(self, reference):
        if not reference:
            return request.env['payment.transaction']
        return request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'montypay'),
        ], limit=1)

    def _confirm_sale_and_invoice(self, tx_sudo):
        """
        Confirm related sale orders, create/post invoices.
        Safe best-effort: failures are logged but won't crash redirect.
        """
        try:
            if not tx_sudo:
                return
            orders = tx_sudo.sale_order_ids
            if not orders:
                return

            # 1) confirm quotations
            for so in orders.filtered(lambda s: s.state in ('draft', 'sent')):
                try:
                    so.action_confirm()
                except Exception as e:
                    _logger.exception("Could not confirm SO %s: %s", so.id, e)

            # 2) create invoices
            try:
                moves = orders._create_invoices()
            except Exception as e:
                _logger.exception("Could not create invoices for %s: %s", orders.ids, e)
                moves = False

            # 3) post invoices
            if moves:
                try:
                    moves.sudo().action_post()
                except Exception as e:
                    _logger.exception("Could not post invoices %s: %s", moves.ids, e)

            # VERY IMPORTANT:
            # store last order id in session so /shop/confirmation works
            # If multiple SOs, take the first (typical checkout = 1 SO).
            if orders:
                request.session['sale_last_order_id'] = orders[0].id

        except Exception as e:
            _logger.exception("Unexpected error in _confirm_sale_and_invoice: %s", e)

    def _redirect_with_message(self, base_url, status_flag, message=None):
        """
        Build redirect like:
        /shop/payment?payment_status=failed&msg=Payment%20declined
        """
        def _escape(val):
            if not val:
                return ''
            return (
                str(val)
                .replace(" ", "%20")
                .replace('"', '%22')
                .replace("'", '%27')
                .replace("\n", "%0A")
                .replace("\r", "")
            )

        url = f"{base_url}?payment_status={_escape(status_flag)}"
        if message:
            url += f"&msg={_escape(message)}"
        return request.redirect(url)

    @http.route(
        '/payment/montypay/webhook',
        type='json', auth='public', methods=['POST'],
        csrf=False, save_session=False
    )
    def montypay_webhook(self, **kwargs):
        """
        MontyPay server-to-server status push.
        """
        try:
            payload = request.jsonrequest or dict(request.params)
        except Exception:
            payload = kwargs or {}

        _logger.info("MontyPay webhook received:\n%s",
                     pprint.pformat(payload))

        reference = (
            payload.get('reference')
            or payload.get('order_number')
            or (payload.get('order') or {}).get('number')
        )

        if not reference:
            _logger.warning("MontyPay webhook missing reference. Payload: %s",
                            payload)
            return {"status": "ignored", "reason": "missing reference"}

        tx_sudo = self._get_tx_from_reference(reference)
        if not tx_sudo:
            _logger.warning("MontyPay webhook: no transaction for ref %s",
                            reference)
            return {"status": "ignored", "reason": "tx not found"}

        # store MontyPay session id (for traceability/debug)
        session_id = payload.get('session_id') or payload.get('id')
        if session_id and hasattr(tx_sudo, 'montypay_session_id'):
            tx_sudo.write({'montypay_session_id': session_id})

        status = (payload.get('status') or '').lower()
        _logger.info("MontyPay webhook status for %s: %s", reference, status)

        if status in ('success', 'approved'):
            tx_sudo._set_done()
            self._confirm_sale_and_invoice(tx_sudo)
            result = "done"

        elif status in ('pending', 'in_progress', 'processing'):
            tx_sudo._set_pending()
            result = "pending"

        elif status in (
            'failed',
            'error',
            'declined',
            'canceled',
            'cancelled',
            'authentication_failed',
        ):
            tx_sudo._set_error("MontyPay reported status: %s" % status)
            result = "error"

        else:
            tx_sudo._set_pending()
            _logger.info(
                "MontyPay webhook unknown status '%s' for %s; forcing pending",
                status, reference
            )
            result = "pending"

        _logger.info("MontyPay webhook processed tx %s -> %s",
                     reference, result)
        return {"status": result}

    @http.route(
        '/payment/montypay/return',
        type='http', auth='public', methods=['GET', 'POST'],
        csrf=False, website=True,
    )
    def montypay_return(self, **kwargs):
        """
        Browser lands here after MontyPay finishes (success, fail, cancel, etc.).
        We redirect accordingly:
          - success -> confirm order, set session, go to /shop/confirmation
          - fail/decline -> back to /shop/payment with banner
          - cancel -> back to /shop/payment with banner
          - pending -> back to /shop/payment with banner
        """

        _logger.info("MontyPay return received:\n%s",
                     pprint.pformat(kwargs))

        status = (kwargs.get('status') or '').lower()
        reason = (
            kwargs.get('reason')
            or kwargs.get('message')
            or kwargs.get('error_description')
            or kwargs.get('error_message')
            or ''
        )

        reference = (
            kwargs.get('reference')
            or kwargs.get('order_number')
            or (kwargs.get('order') or {}).get('number')
        )

        tx_sudo = self._get_tx_from_reference(reference)

        # SUCCESS / APPROVED
        if status in ('success', 'approved'):
            if tx_sudo and tx_sudo.state not in ('done', 'authorized'):
                tx_sudo._set_done()

            self._confirm_sale_and_invoice(tx_sudo)

            # instead of bouncing through /shop/payment/validate and risking /shop,
            # we jump straight to confirmation
            return request.redirect('/shop/confirmation')

        # FAILURE / DECLINED
        if status in ('failed', 'error', 'declined', 'authentication_failed'):
            if tx_sudo:
                tx_sudo._set_error("MontyPay reported status: %s %s" % (status, reason))

            return self._redirect_with_message(
                base_url='/shop/payment',
                status_flag='failed',
                message=reason or status,
            )

        # CANCELLED
        if status in ('canceled', 'cancelled'):
            if tx_sudo:
                tx_sudo._set_error("Customer cancelled payment")

            return self._redirect_with_message(
                base_url='/shop/payment',
                status_flag='cancelled',
                message=_("Payment was cancelled"),
            )

        # PENDING / PROCESSING
        if status in ('pending', 'in_progress', 'processing'):
            if tx_sudo:
                tx_sudo._set_pending()

            return self._redirect_with_message(
                base_url='/shop/payment',
                status_flag='pending',
                message=_("Your payment is still being processed."),
            )

        # UNKNOWN -> treat as pending
        if tx_sudo:
            tx_sudo._set_pending()
        _logger.info("MontyPay return unknown status '%s' for ref %s -> pending",
                     status, reference)

        return self._redirect_with_message(
            base_url='/shop/payment',
            status_flag='pending',
            message=_("We could not confirm the payment yet."),
        )

    @http.route(
        '/payment/montypay/cancel',
        type='http', auth='public', methods=['GET', 'POST'],
        csrf=False, website=True,
    )
    def montypay_cancel(self, **kwargs):
        """
        User explicitly hit 'Cancel' in MontyPay UI.
        Mark tx as cancelled/error and send them back to payment step
        with a nice yellow banner.
        """
        _logger.info("MontyPay cancellation received:\n%s",
                     pprint.pformat(kwargs))

        reference = (
            kwargs.get('reference')
            or kwargs.get('order_number')
            or (kwargs.get('order') or {}).get('number')
        )

        tx_sudo = self._get_tx_from_reference(reference)
        if tx_sudo:
            tx_sudo._set_error("Customer cancelled payment")

        return self._redirect_with_message(
            base_url='/shop/payment',
            status_flag='cancelled',
            message=_("Payment was cancelled"),
        )
