from . import models
from . import controllers


def post_init_hook(env):
    # Ensure the redirect form is set on the MontyPay provider
    provider = env['payment.provider'].sudo().search([('code', '=', 'montypay')], limit=1)
    if provider:
        try:
            redirect_view = env.ref('payment.payment_redirect_form')
            provider.write({'redirect_form_view_id': redirect_view.id})
        except Exception:
            # Fallback: do nothing if the view ref is not available for any reason
            pass