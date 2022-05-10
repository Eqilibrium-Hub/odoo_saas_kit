# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
# 
#################################################################################

import base64
import logging
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


class MailController(http.Controller):
    _cp_path = '/mail'

    @http.route(['/mail/confirm_domain'], type='json', auth="public", methods=['POST'], website=True)
    def confirm_domain(self, domain_name, contract_id,  **kw):
        """
        This controller is called when the customers submits the domain name from the controller.
        """
        contract = request.env['saas.contract'].sudo().search([('domain_name', '=ilike', domain_name), ('state', '!=', 'cancel')])
        if contract:
            _logger.info("---------ALREADY TAKEN--------%r", contract)
            return dict(
                status=1
            )
        else:
            _logger.info("---------CREATING CLIENT--------%r", contract)
            contract = request.env['saas.contract'].sudo().browse(int(contract_id))
            if contract.state == 'draft' and contract.server_id.total_clients < contract.server_id.max_clients and not contract.saas_client:
                contract.domain_name = domain_name
                try:
                    # Creating Client -- Script Called--START
                    contract.create_saas_client()
                    # Creating Client -- Script Called--END
                    if contract.saas_client and contract.saas_client.client_url:
                        _logger.info("---Success----------")
                        return dict(
                            status=2,
                            url=contract.saas_client.client_url
                        )
                except Exception as e:
                    body = "An Exception is occur while creating client : {}".format(e)
                    contract.message_post(body=body, subject="Client Creation Exceptions")
                    _logger.info("---1----------%r", e)
                    return dict(
                        status=3,
                    )
            _logger.info("---3----------")
            body = "An Exception occur: \n Please Check Contract Not be in Draft State, or Maximum Client Limit Exceeds, or Client Exist with same Contract"
            contract.message_post(body=body, subject="Client Creation Exceptions")
            return dict(
                status=3,
            )

    @http.route('/mail/contract/subdomain', type='http', auth='public', website=True)
    def mail_action_view(self, contract_id=None, token=None, partner_id=None, **kwargs):
        """
        This controller returns the domain selection portal page for the customer.
        """
        if contract_id and token and partner_id:
            contract = request.env['saas.contract'].browse(int(contract_id))
            if contract.exists() and (contract.partner_id.id == int(partner_id)) and (contract.token == token) and (contract.state == 'draft'):
                return request.render('odoo_saas_kit.subdomain_page', {
                    'contract_id': contract_id,
                    'base_url': contract.saas_domain_url,
                    'page_name': 'saas_subdomain',
                })
            else:
                return request.redirect('/my')
        else:
            return request.redirect('/error')

    @http.route('/client/domain-created/redirect', type="http", auth="public", website=True)
    def domain_set_template(self):
        return request.render('odoo_saas_kit.redirect_page')
