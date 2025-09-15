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

        # Provide the URL and an explicit redirect form HTML that matches
        # what the frontend expects for redirect flows.
        redirect_url = self.provider_id._get_payment_link(self)
        redirect_form_html = (
            '<form id="o_payment_redirect_form" class="o_payment_redirect_form" '
            '      method="get" target="_top" action="%s">\n'
            '  <input type="hidden" name="reference" value="%s"/>\n'
            '  <input type="hidden" name="amount" value="%s"/>\n'
            '  <button id="o_payment_redirect_button" type="submit" class="d-none">Pay</button>\n'
            '</form>'
        ) % (redirect_url, self.reference, self.amount)

        rendering_values = {
            'api_url': redirect_url,
            'redirect_form_html': redirect_form_html,
        }
        res.update(rendering_values)
        return res

    def _get_specific_processing_values(self, processing_values):
        """Provide provider-specific values used by the frontend to start the flow.

        Odoo's checkout calls an endpoint that returns `processing_values` for the
        selected provider. For redirect flows, the frontend expects at least an
        `api_url` so it can set the action on the standard redirect form.
        """
        res = super()._get_specific_processing_values(processing_values)
        if self.provider_code != 'montypay':
            return res

        redirect_url = self.provider_id._get_payment_link(self)
        # Provide api_url and a minimal redirect form so the frontend can
        # locate the expected node and set the "action" before submitting.
        redirect_form_html = (
            '<form id="o_payment_redirect_form" class="o_payment_redirect_form" '
            '      method="get" target="_top">\n'
            '  <button id="o_payment_redirect_button" type="submit" class="d-none">Pay</button>\n'
            '</form>'
        )

        res.update({
            'api_url': redirect_url,
            'redirect_form_html': redirect_form_html,
            'redirect_form': redirect_form_html,
        })
        return res