# -*- coding: utf-8 -*-

import json
import logging
import pprint

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class MontyPayController(http.Controller):
    """
    Controller handling MontyPay <-> Odoo communication:
    - webhook  (server-to-server status update)
    - return   (browser redirect after attempting payment)
    - cancel   (browser redirect when user cancels)
    """

    # -------------------------------------------------------------------------
    # Utility helpers
    # -------------------------------------------------------------------------

    def _get_tx_from_reference(self, reference):
        """Find the payment.transaction for this MontyPay reference."""
        if not reference:
            return request.env['payment.transaction']
        return request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'montypay'),
        ], limit=1)

    def _confirm_sale_and_invoice(self, tx_sudo):
        """
        Best effort: confirm related orders and post invoices.

        We mirror Odoo's usual post-payment flow:
        - confirm quotations
        - generate invoices
        - post invoices
        We wrap in try/except so that a failure here doesn't break the redirect.
        """
        try:
            if not tx_sudo:
                return
            orders = tx_sudo.sale_order_ids
            if not orders:
                return

            # 1) confirm the orders if still draft/sent
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

        except Exception as e:
            _logger.exception("Unexpected error in _confirm_sale_and_invoice: %s", e)

    def _redirect_with_message(self, base_url, status_flag, message=None):
        """
        Build a redirect URL like:
        /shop/payment?payment_status=failed&msg=Payment%20declined

        This lets the website payment step render a visible alert.
        """
        # very small escape to avoid breaking the URL
        def _escape(val):
            if not val:
                return ''
            # basic URL-ish escaping for spaces and quotes
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

    # -------------------------------------------------------------------------
    # 1) SERVER WEBHOOK (MontyPay -> Odoo, backend call)
    # -------------------------------------------------------------------------

    @http.route(
        '/payment/montypay/webhook',
        type='json', auth='public', methods=['POST'],
        csrf=False, save_session=False
    )
    def montypay_webhook(self, **kwargs):
        """
        MontyPay calls this (server-to-server) to report final status.

        Expected payload examples:
        {
            "reference": "SO123",
            "status": "SUCCESS" | "APPROVED" | "DECLINED" | "FAILED" | "PENDING" | ...
            "session_id": "abc123",
            ...
        }
        """
        # Try to get the request body as JSON (request.jsonrequest works for JSON).
        # Fallback to raw params / kwargs, to be robust.
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
            _logger.warning("MontyPay webhook: no transaction for reference %s",
                            reference)
            return {"status": "ignored", "reason": "tx not found"}

        # Optionally store MontyPay session/ids so you can debug later
        session_id = payload.get('session_id') or payload.get('id')
        if session_id and hasattr(tx_sudo, 'montypay_session_id'):
            tx_sudo.write({'montypay_session_id': session_id})

        status = (payload.get('status') or '').lower()
        _logger.info("MontyPay webhook status for %s: %s", reference, status)

        if status in ('success', 'approved'):
            # Mark transaction successful
            tx_sudo._set_done()
            result = "done"

            # Optionally confirm sale/invoice
            self._confirm_sale_and_invoice(tx_sudo)

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
            # Mark it as error in Odoo
            tx_sudo._set_error("MontyPay reported status: %s" % status)
            result = "error"

        else:
            # Unknown status => keep it pending, but log it loudly
            tx_sudo._set_pending()
            _logger.info(
                "MontyPay webhook unknown status '%s' for %s; forcing pending",
                status, reference
            )
            result = "pending"

        _logger.info("MontyPay webhook processed tx %s -> %s",
                     reference, result)
        return {"status": result}

    # -------------------------------------------------------------------------
    # 2) BROWSER RETURN (Customer -> Odoo after payment attempt)
    # -------------------------------------------------------------------------

    @http.route(
        '/payment/montypay/return',
        type='http', auth='public', methods=['GET', 'POST'],
        csrf=False, website=True,
    )
    def montypay_return(self, **kwargs):
        """
        Customer lands here after MontyPay redirects them back.
        We decide where to send them next:

        - success/approved  -> normal Odoo confirmation flow (/shop/payment/validate)
        - failed/declined   -> back to /shop/payment with an error banner
        - canceled          -> back to /shop/payment with a cancelled banner
        - pending           -> /shop/payment with "pending" message
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

        # ---------------- SUCCESS / APPROVED ----------------
        if status in ('success', 'approved'):
            if tx_sudo and tx_sudo.state not in ('done', 'authorized'):
                # mark the tx as done
                tx_sudo._set_done()

            # try to confirm SO + post invoices
            self._confirm_sale_and_invoice(tx_sudo)

            # Normal happy path in Odoo, will do final cleanup & redirect
            return request.redirect('/shop/payment/validate')

        # ---------------- FAILURE / DECLINED ----------------
        if status in (
            'failed',
            'error',
            'declined',
            'authentication_failed',
        ):
            if tx_sudo:
                tx_sudo._set_error(
                    "MontyPay reported status: %s %s" % (status, reason)
                )

            # Send them back to payment step with an error banner
            # Example banner you can render:
            #   Payment declined: AUTHENTICATION_FAILED
            return self._redirect_with_message(
                base_url='/shop/payment',
                status_flag='failed',
                message=reason or status,
            )

        # ---------------- CANCELED / CANCELLED ----------------
        if status in ('canceled', 'cancelled'):
            if tx_sudo:
                tx_sudo._set_error("Customer cancelled payment")

            return self._redirect_with_message(
                base_url='/shop/payment',
                status_flag='cancelled',
                message=_("Payment was cancelled"),
            )

        # ---------------- PENDING / PROCESSING ----------------
        if status in ('pending', 'in_progress', 'processing'):
            if tx_sudo:
                tx_sudo._set_pending()
            return self._redirect_with_message(
                base_url='/shop/payment',
                status_flag='pending',
                message=_("Your payment is still being processed."),
            )

        # ---------------- UNKNOWN STATUS ----------------
        # Fallback: treat as pending to avoid accidental confirmation
        if tx_sudo:
            tx_sudo._set_pending()
        _logger.info(
            "MontyPay return: unknown status '%s' for ref %s, treating as pending",
            status, reference
        )
        return self._redirect_with_message(
            base_url='/shop/payment',
            status_flag='pending',
            message=_("We could not confirm the payment yet."),
        )

    # -------------------------------------------------------------------------
    # 3) BROWSER CANCEL (explicit "Cancel" action in MontyPay UI)
    # -------------------------------------------------------------------------

    @http.route(
        '/payment/montypay/cancel',
        type='http', auth='public', methods=['GET', 'POST'],
        csrf=False, website=True,
    )
    def montypay_cancel(self, **kwargs):
        """
        User actively cancelled from MontyPay before completion.
        We'll mark the tx as error/cancelled (if we can find it),
        then send them back to /shop/payment with a banner.
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
