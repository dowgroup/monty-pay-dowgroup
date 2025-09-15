from odoo import fields, models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    montypay_session_id = fields.Char(
        string="MontyPay Session ID",
        help="MontyPay payment session identifier"
    )

    def _get_specific_rendering_values(self, processing_values):
        """ Override to provide MontyPay specific rendering values. """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'montypay':
            return res

        # Provide the URL for the standard redirect form
        redirect_url = self.provider_id._get_payment_link(self)
        rendering_values = {
            'api_url': redirect_url,
        }
        res.update(rendering_values)
        return res