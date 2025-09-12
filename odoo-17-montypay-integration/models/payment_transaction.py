from odoo import fields, models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    montypay_session_id = fields.Char(
        string="MontyPay Session ID",
        help="MontyPay payment session identifier"
    )