# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
# 
#################################################################################

from odoo import api, fields, models


class PrductTemplate(models.Model):
    _inherit = 'product.template'

    saas_module_ids = fields.Many2many(
        comodel_name="saas.module",
        relation="product_module_relation",
        column1="product_id",
        column2="module_id",
        string="Related Modules")


# class ProductProduct(models.Model):
#     _inherit = 'product.product'
#
#     contract_id = fields.Many2one("saas.contract", "Saas contract")

#     @api.model
#     def create(self, vals):
#         template_id = vals.get('product_tmpl_id', False)
#         if template_id:
#             template_obj = self.env['product.template'].browse(template_id)
#             vals['recurring_interval'] = template_obj.saas_plan_id and template_obj.saas_plan_id.recurring_interval
#         product = super(ProductProduct, self).create(vals)
#         return product
#
#     recurring_interval = fields.Integer(string='Billing Cycle/Repeat Every',)