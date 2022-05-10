# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
# 
#################################################################################

from odoo import api, fields, models
from dateutil.relativedelta import relativedelta
import logging
_logger = logging.getLogger(__name__)

BILLING_CRITERIA = [
    ('fixed', "Fixed Rate"),
    ('per_user', 'Based on the No. of users')
]


class ContractCreation(models.TransientModel):
    _name = "saas.contract.creation"
    _description = 'Contract Creation Wizard.'

    plan_id = fields.Many2one(comodel_name="saas.plan", string="Related SaaS Plan", required=False)
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
        required=True,
    )
    recurring_interval = fields.Integer(
        default=1,
        string='Repeat Every',
        help="Repeat every (Days/Week/Month/Year)",
    )
    recurring_rule_type = fields.Selection(
        [('daily', 'Day(s)'),
         ('weekly', 'Week(s)'),
         ('monthly', 'Month(s)'),
         ('monthlylastday', 'Month(s) last day'),
         ('yearly', 'Year(s)'),
         ],
        default='monthly',
        string='Recurrence',
        help="Specify Interval for automatic invoice generation.", readonly=True,
    )
    billing_criteria = fields.Selection(
        selection=BILLING_CRITERIA,
        string="Billing Criteria",
        required=True)
    # invoice_product_id = fields.Many2one(comodel_name="product.product", required=True, string="Invoice Product")
    # product_ids = fields.One2many(comodel_name="product.product", string="Products", inverse_name="contract_id")
    product_ids = fields.Many2many(
        comodel_name="product.product",
        relation="saas_product_contract_creation",
        column1="product_id",
        column2="contract_creation_id",
        string="Related Modules",
        domain="[('type', '=','service')]"
    )
    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string='Pricelist'
    )
    currency_id = fields.Many2one(comodel_name="res.currency")
    # contract_rate = fields.Float(string="Contract Rate")
    auto_create_invoice = fields.Boolean(string="Automatically create next invoice")
    start_date = fields.Date(
        string='Purchase Date',
        required=True
    )
    total_cycles = fields.Integer(
        string="Number of Cycles(Remaining/Total)", default=1)
    trial_period = fields.Integer(
        string="Trial Period(in days)", default=0)

    @api.model
    def get_date_delta(self, interval):
        return relativedelta(months=interval)

    @api.onchange('trial_period')
    def trial_period_change(self):
        relative_delta = relativedelta(days=self.trial_period)
        old_date = fields.Date.from_string(fields.Date.today())
        self.start_date = fields.Date.to_string(old_date + relative_delta)

    @api.onchange('plan_id')
    def plan_id_change(self):
        self.recurring_interval = self.plan_id.recurring_interval
        self.recurring_rule_type = self.plan_id.recurring_rule_type
        self.billing_criteria = self.plan_id.billing_criteria
        self.total_cycles = self.plan_id.total_cycles
        self.trial_period = self.plan_id.trial_period
        relative_delta = relativedelta(days=self.trial_period)
        old_date = fields.Date.from_string(fields.Date.today())
        self.start_date = fields.Date.to_string(old_date + relative_delta)

    @api.onchange('partner_id')
    def partner_id_change(self):
        self.pricelist_id = self.partner_id.property_product_pricelist and self.partner_id.property_product_pricelist.id or False
        self.currency_id = self.partner_id.property_product_pricelist and self.partner_id.property_product_pricelist.currency_id.id or False

    # @api.onchange('invoice_product_id')
    # def invoice_product_id_change(self):
    #     self.contract_rate = self.invoice_product_id and self.invoice_product_id.lst_price or False

    def action_create_contract(self):
        for obj in self:
            vals = dict(
                partner_id=obj.partner_id and obj.partner_id.id or False,
                recurring_interval=obj.recurring_interval,
                recurring_rule_type=obj.recurring_rule_type,
                # invoice_product_id=obj.invoice_product_id and obj.invoice_product_id.id or False,
                pricelist_id=obj.partner_id.property_product_pricelist and obj.partner_id.property_product_pricelist.id or False,
                currency_id=obj.partner_id.property_product_pricelist and obj.partner_id.property_product_pricelist.currency_id and obj.partner_id.property_product_pricelist.currency_id.id or False,
                start_date=obj.start_date,
                total_cycles=obj.total_cycles,
                trial_period=obj.trial_period,
                remaining_cycles=obj.total_cycles,
                next_invoice_date=obj.start_date,
                # contract_rate=obj.contract_rate,
                billing_criteria=obj.billing_criteria,
                auto_create_invoice=obj.auto_create_invoice,
                product_ids=[(6, 0, obj.product_ids.ids)],
                # saas_module_ids=[(6, 0 , obj.plan_id.saas_module_ids.ids)],
                server_id=obj.plan_id.server_id.id,
                db_template=obj.plan_id.db_template,
                plan_id=obj.plan_id.id
            )

            try:
                record_id = self.env['saas.contract'].create(vals)
                _logger.info("--------Contract--Created-------%r", record_id)
            except Exception as e:
                _logger.info("--------Exception-While-Creating-Contract-------%r", e)
            else:
                imd = self.env['ir.model.data']
                action = self.env['ir.actions.act_window']._for_xml_id("odoo_saas_kit.saas_contract_action")
                # action = self._xmlid_to_obj(self.env, 'odoo_saas_kit.saas_contract_action')
                list_view_id = imd._xmlid_to_res_id('odoo_saas_kit.saas_contract_tree_view')
                form_view_id = imd._xmlid_to_res_id('odoo_saas_kit.saas_contract_form_view')

                return {
                    'name': action.get('name'),
                    'res_id': record_id.id,
                    'type': action.get('type'),
                    'views': [[form_view_id, 'form'], [list_view_id, 'tree'], ],
                    'target': action.get('target'),
                    'context': action.get('context'),
                    'res_model': action.get('res_model'),
                }
