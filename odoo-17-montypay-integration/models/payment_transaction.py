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

        # Simple redirect approach - just redirect immediately
        redirect_url = self.provider_id._get_payment_link(self)
        
        # Use a simple JavaScript redirect
        html_form = f'''
        <div class="text-center" style="padding: 20px;">
            <h4>Redirecting to MontyPay...</h4>
            <p>Please wait...</p>
            <script>
                window.open('{redirect_url}', '_top');
            </script>
        </div>
        '''
        
        rendering_values = {
            'redirect_form_html': html_form,
        }
        res.update(rendering_values)
        return res