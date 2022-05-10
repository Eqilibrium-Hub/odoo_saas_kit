# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
# 
#################################################################################

from odoo import api, fields, models
from odoo.exceptions import Warning
import logging
_logger = logging.getLogger(__name__)


class ClientDisable(models.TransientModel):
    _name = "saas.client.disable"

    name = fields.Char(string="Name")
    client_id = fields.Integer(string="Client Id")

    def confirm_disable(self):
        raise Warning("ok")
