# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
# 
#################################################################################

from dateutil.relativedelta import relativedelta
from odoo import fields, models, api
import logging
_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    contract_id = fields.Many2one(comodel_name="saas.contract", string="SaaS Contract")

    @api.model
    def get_date_delta(self, interval):
        return relativedelta(months=interval)

    def action_view_contract(self):
        action = self.env.ref('odoo_saas_kit.saas_contract_action').read()[0]

        contract = self.env['saas.contract'].search([('sale_order_id', '=', self.id)])
        action['domain'] = [('id', 'in', contract.ids)]
        return action

    def process_contract(self):
        for order in self:
            plan_name = order.order_line[0].product_id.product_template_attribute_value_ids._get_combination_name()
            plan = self.env["saas.plan"].search([("name", "=ilike", plan_name)])

            # self.env["sale.plan"].search([("name","=", )])

            # all_contract_lines = list(filter(lambda line: line.product_id.saas_plan_id, order.order_line))
            if plan:
                product_ids = []

                for line in order.order_line:
                    product_ids.append(line.product_id.id)
                # contract_rate = contract_line.price_unit
                relative_delta = relativedelta(days=plan.trial_period)
                old_date = fields.Date.from_string(fields.Date.today())
                start_date = fields.Date.to_string(old_date + relative_delta)
                # recurring_interval_delta = relativedelta(months=(int(con.recurring_interval)))

                vals = dict(
                    partner_id = order.partner_id and order.partner_id.id or False,
                    recurring_interval = plan.recurring_interval,
                    recurring_rule_type = plan.recurring_rule_type,
                    # invoice_product_id = contract_product and contract_product.id or False,
                    pricelist_id = order.pricelist_id and order.pricelist_id.id or False,
                    currency_id = order.pricelist_id and order.pricelist_id.currency_id and order.pricelist_id.currency_id.id or False,
                    start_date = start_date,
                    # total_cycles = contract_line.product_uom_qty,
                    trial_period = plan.trial_period,
                    remaining_cycles = 0,
                    # next_invoice_date = fields.Date.to_string(fields.Date.from_string(start_date) + recurring_interval_delta),
                    # contract_rate = contract_rate,
                    auto_create_invoice = False,
                    # saas_module_ids = [(6, 0 , )],
                    on_create_email_template = self.env.ref('odoo_saas_kit.client_credentials_template').id,
                    server_id = plan.server_id.id,
                    # sale_order_line_id = contract_line.id,
                    plan_id = plan.id,
                    db_template = plan.db_template,
                    billing_criteria = plan.billing_criteria,
                    product_ids = product_ids
                )
                try:
                    record_id = self.env['saas.contract'].create(vals)
                    _logger.info("------VIA-ORDER--Contract--Created-------%r", record_id)
                except Exception as e:
                    _logger.info("-----VIA-ORDER---Exception-While-Creating-Contract-------%r", e)
                else:
                    order.contract_id = record_id and record_id.id
                    record_id.send_subdomain_email()
    
    
    def _action_confirm(self):
        res = super(SaleOrder, self)._action_confirm()
        self.process_contract()
        return res