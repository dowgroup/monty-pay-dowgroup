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

        # Add MontyPay specific rendering values
        rendering_values = {
            'redirect_form_html': f'''
                <div style="text-align: center; padding: 20px;">
                    <h3>Redirecting to MontyPay...</h3>
                    <p>Please wait while we redirect you to MontyPay's secure payment page.</p>
                    <script>
                        setTimeout(function() {{
                            window.location.href = '{self.provider_id._get_payment_link(self)}';
                        }}, 2000);
                    </script>
                </div>
            '''
        }
        res.update(rendering_values)
        return res