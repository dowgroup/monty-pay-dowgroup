import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # MontyPay specific fields
    montypay_session_id = fields.Char(
        string="MontyPay Session ID",
        help="MontyPay payment session identifier"
    )

    def _get_specific_rendering_values(self, processing_values):
        """ Override to provide MontyPay specific rendering values. """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'montypay':
            return res

        rendering_values = {
            'api_url': self.provider_id._get_payment_link(self),
        }
        return rendering_values

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override to get transaction from MontyPay notification data. """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'montypay' or len(tx) == 1:
            return tx

        reference = notification_data.get('order_number')
        if not reference:
            raise ValueError("MontyPay: " + _("Received data with missing reference"))

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'montypay')])
        if not tx:
            raise ValueError("MontyPay: " + _("No transaction found matching reference %s", reference))
        
        return tx

    def _process_notification_data(self, notification_data):
        """ Override to process MontyPay notification data. """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'montypay':
            return

        # Store MontyPay session ID if provided
        session_id = notification_data.get('session_id')
        if session_id:
            self.montypay_session_id = session_id

        # Process status from notification
        status = notification_data.get('status', '').lower()
        
        if status == 'success':
            self._set_done()
        elif status in ['failed', 'error', 'declined']:
            self._set_error(_("Payment was declined: %s") % notification_data.get('message', 'Unknown error'))
        elif status == 'pending':
            self._set_pending()
        else:
            _logger.warning(
                "Received notification with unknown status %s for transaction %s",
                status, self.reference
            )
