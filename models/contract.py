# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
#
#################################################################################

import logging
import random
from odoo import api, fields, models, tools, _
from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode
from odoo.exceptions import UserError, Warning, ValidationError
from odoo.addons.auth_signup.models.res_partner import random_token as generate_token
from . lib import query


_logger = logging.getLogger(__name__)

BILLING_CRITERIA = [
    ('fixed', "Fixed Rate"),
    ('per_user', 'Based on the No. of users')
]

CONTRACT_STATE = [
    ('draft', "Draft"),
    ('open', "Open"),
    ('confirm', "Confirmed"),
    ('expired',"Expired"),
    ('cancel', "Cancelled")]


def random_token():
    chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(random.SystemRandom().choice(chars) for _ in range(20))


class SaasContract(models.Model):
    _name = 'saas.contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    @api.depends('db_template')
    def _compute_saas_domain_url(self):
        for obj in self:
            obj.saas_domain_url = obj.plan_id.saas_base_url

    @api.depends('product_ids')
    def _compute_module_ids(self):
        for obj in self:
            l = []
            for product in obj.product_ids:
                ids = product.product_tmpl_id.saas_module_ids.ids
                l = ids + l
            obj.saas_module_ids = [(6, 0, set(l))]

    name = fields.Char(string='Contract Name')

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.user.company_id,
    )
    journal_id = fields.Many2one(
        'account.journal',
        string='Journal',
        default=lambda s: s._default_journal(),
        domain="[('company_id', '=', company_id)]",
    )
    recurring_interval = fields.Integer(
        default=1,
        string='Billing cycle',
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
    # invoice_product_id = fields.Many2one(comodel_name="product.product", string="Invoice Product")
    # product_ids = fields.One2many(comodel_name="product.product", string="Products", inverse_name="contract_id")
    product_ids = fields.Many2many(
        comodel_name="product.product",
        relation="saas_product_contract",
        column1="product_id",
        column2="contract_id",
        string="Related Modules",
        domain="[('type', '=','service')]")

    # contract_rate = fields.Float(string="Contract Rate")
    pricelist_id = fields.Many2one(
        comodel_name='product.pricelist',
        string='Pricelist',
    )
    currency_id = fields.Many2one(comodel_name="res.currency")

    start_date = fields.Date(
        string='Purchase Date',
        required=True
    )
    invoice_ids = fields.One2many(comodel_name="account.move", inverse_name="contract_id")
    on_create_email_template = fields.Many2one('mail.template', default=lambda self: self.env.ref('odoo_saas_kit.client_credentials_template'), string="Client Creation Email Template")
    auto_create_invoice = fields.Boolean(string="Automatically create next invoice")
    saas_client = fields.Many2one(comodel_name="saas.client", string="SaaS Client")
    saas_module_ids = fields.Many2many(comodel_name="saas.module", relation="saas_contract_module_relation", column1="contract_id", column2="module_id", string="Related Modules", compute="_compute_module_ids")
    state = fields.Selection(selection=CONTRACT_STATE, default="draft", string="State")
    total_cycles = fields.Integer(string="Billing Cycles (Remaining/Total)", default=1)
    remaining_cycles = fields.Integer(string="Remaining Cycles", default=1)
    trial_period = fields.Integer(string="Trial Period(in days)", default=0)
    next_invoice_date = fields.Date(string="Next invoice date")
    server_id = fields.Many2one(comodel_name="saas.server", string="SaaS Server")
    sale_order_id = fields.Many2one(comodel_name="sale.order", related="sale_order_line_id.order_id", string="Related Sale Order")
    sale_order_line_id = fields.Many2one(comodel_name="sale.order.line", string="Related Sale Order Line")
    under_process = fields.Boolean(string="Client Creation Under Process", default=False)
    token = fields.Char(string="Token")
    domain_name = fields.Char(string="Domain name")
    db_template = fields.Char(string="DB Template")
    plan_id = fields.Many2one("saas.plan", string="SaaS Plan")
    user_data_updated = fields.Boolean(string="User data Updated")
    user_data_error = fields.Boolean(string="User data Update Error")
    invitation_mail_sent = fields.Boolean(string="Invitation Mail Sent")
    invitation_mail_error = fields.Boolean(string="Invitation Mail Error")
    subdomain_email_sent = fields.Boolean(string="Sent Subdomain Email", default=False)
    use_separate_domain = fields.Boolean(string="Use custom domain", default=False)
    saas_domain_url = fields.Char(compute='_compute_saas_domain_url', string="SaaS Domain URL")
    is_contract_expiry_mail = fields.Integer(default=0)

    @api.onchange('pricelist_id')
    def pricelist_id_change(self):
        self.currency_id = self.pricelist_id and self.pricelist_id.currency_id and self.pricelist_id.currency_id.id or False

    @api.model
    def _default_journal(self):
        company_id = self.env.context.get(
            'company_id', self.env.user.company_id.id)
        domain = [
            ('company_id', '=', company_id)]
        return self.env['account.journal'].search(domain, limit=1)

    @api.model
    def attach_modules(self, client_id=None):
        module_ids = self.saas_module_ids
        for module in module_ids:
            self.env['saas.module.status'].create(dict(
                module_id=module.id,
                client_id=client_id.id,
            ))

    def send_expiry_mail(self):
        for obj in self:
            template = self.env.ref('odoo_saas_kit.contract_expiry_template')
            mail_id = template.send_mail(obj.id)
            current_mail = self.env['mail.mail'].browse(mail_id)
            res = current_mail.send()
            obj.is_contract_expiry_mail = 2
            obj.message_post(body="Contaract is expired and Expiry mail is sent to the Customer", subject="Expired")

    
    @api.model
    def check_contract_expiry(self):
        contracts = self.search([('state', 'in', ['confirm']), ('remaining_cycles', '=', 0), ('next_invoice_date', '<=', fields.Date.today()), ('sale_order_id', '!=', False), ('domain_name', '!=', False)])
        _logger.info("-------   Contract Expiry Cron ------")
        for contract in contracts:
            _logger.info("----------records  %r    "%contract.id)
            # pass
            # raise Warning("%r"%contract.id)
            contract.is_contract_expiry_mail = 1
            contract.send_expiry_mail()
            database = contract.saas_client and contract.saas_client.database_name or False
            _, db_server = contract.plan_id.server_id.get_server_details()
            response = query.set_contract_expiry(database, str(True), db_server=db_server)
            if response:
                contract.saas_client.restart_client()
            else:
                _logger.info("-------   Exception While writing on client's Instance ------")
            contract.write({'state': 'expired'})
            contract._cr.commit()


    
    @api.model
    def client_creation_cron_action(self):
        IrDefault = self.env['ir.default'].sudo()

        auto_create_client = IrDefault.get('res.config.settings', 'auto_create_client')
        if auto_create_client:
            contracts = self.search([('state', 'in', ['draft', 'open']), ('sale_order_id', '!=', False), ('domain_name', '!=', False)])
            _logger.info("------CRON-ACTION-RECORDS------%r", contracts)
            k = []
            for contract in contracts:
                try:
                    res = contract.create_saas_client()
                    k.append(res)
                except Exception as e:
                    continue
            return k

    @api.model
    def _compute_subdomain_token(self):
        token = random_token()
        contracts = self.env['saas.contract'].search([('token', '=', token), ('state', '!=', 'draft')])
        while contracts:
            token = random_token()
            contracts = self.env['saas.contract'].search([('token', '=', token), ('state', '!=', 'draft')])
        self.token = token

    def cancel_contract(self):
        for obj in self:
            if obj.state == "draft":
                obj.state = "cancel"
            else:
                raise UserError("You cannot cancel an Open/Confirmed contract!")

    def resume_contract(self):
        """
        Called from button on contract "Resume Contract Contract" to resume the normal working of client's instance.
        """
        for obj in self:
            if obj.state == "expired":
                database = obj.saas_client and obj.saas_client.database_name or False
                _, db_server = obj.plan_id.server_id.get_server_details()
                response = query.set_contract_expiry(database, str(False), db_server=db_server)
                if response:
                    obj.saas_client.restart_client()
                else:
                    _logger.info("---------    Error while Updating Contarct expiry  data ---------")
                obj.write({'state': 'confirm'})
                obj._cr.commit()
                _logger.info("---------  Contract Resuming ---------")

    def update_user_data(self):
        """
        Called from The button "Set UserData in the Contract Form"
        """
        for obj in self:
            if not obj.plan_id or (obj.plan_id and not obj.plan_id.use_specific_user_template):
                raise UserError("Database Template User ID Not Set!")
            token = generate_token()
            obj.sudo().set_user_data(token=token)
            obj._cr.commit()
            reset_pwd_url = "{}/web/signup?token={}&db={}".format(obj.saas_client.client_url, token, obj.saas_client.database_name)
            obj.saas_client.invitation_url = reset_pwd_url

    def send_invitation_email(self):
        for obj in self:
            if not obj.plan_id or (obj.plan_id and not obj.plan_id.use_specific_user_template):
                obj.invitation_mail_error = True
                obj.invitation_mail_sent = False
                raise UserError("Database Template User ID Not Set!")

            if not obj.saas_client or (obj.saas_client and not obj.saas_client.client_url):
                obj.invitation_mail_error = True
                obj.invitation_mail_sent = False
                raise UserError("Unable To Send Invitation Email\nERROR: Make Sure That Client Url Is Created!")

            if obj.saas_client and obj.saas_client.client_url and (not obj.saas_client.invitation_url):
                obj.invitation_mail_error = True
                obj.invitation_mail_sent = False
                raise UserError("Unable To Send Invitation Email\nERROR: Please Set User Data First!")
            else:
                obj.invitation_mail_error = False
                obj.invitation_mail_sent = True
                template = obj.on_create_email_template
                mail_id = template.send_mail(obj.saas_client.id)
                current_mail = self.env['mail.mail'].browse(mail_id)
                current_mail.send()
                obj.write({'state': 'confirm'})
                self._cr.commit()


    def set_user_data(self, token=False):
        for obj in self:
            data = dict()
            partner_id = obj.partner_id
            user_id = self.env['res.users'].search([('partner_id', '=', obj.partner_id.id)], limit=1)
            if not user_id and not partner_id.email:
                raise UserError("Please Specify The Email Of The Selected Partner!")
            host_server, db_server = obj.plan_id.server_id.get_server_details()
            data['database'] = obj.saas_client and obj.saas_client.database_name or False
            data['user_id'] = obj.plan_id.template_user_id and int(obj.plan_id.template_user_id)
            data['user_data'] = dict(
                name = user_id and user_id.name or partner_id.name or '',
                login = user_id and user_id.login or partner_id.email or '',
            )

            data['partner_data'] = dict(
                name = partner_id.name or '',
                street = partner_id.street or '',
                street2 = partner_id.street2 or '',
                city = partner_id.city or '',
                state_id = partner_id.state_id and partner_id.state_id.id or False,
                zip = partner_id.zip or '',
                country_id = partner_id.country_id and partner_id.country_id.id or False,
                phone = partner_id.phone or '',
                mobile = partner_id.mobile or '',
                email = partner_id.email or '',
                website = partner_id.website or '',
                signup_token=token or '',
                signup_type="signup",
            )
            data['host_server'] = host_server
            data['db_server'] = db_server
            _logger.info("------DATAAA-------%r", data)
            response = query.update_user(**data)
            if response:
                _logger.info("------1-------")
                obj.user_data_updated = True
                obj.user_data_error = False
                self._cr.commit()
                obj.message_post(
                    body="User Data Update Successfully",
                    subject="User Data Update Response",
                )
            else:
                _logger.info("------2-------")
                obj.user_data_updated = False
                obj.user_data_error = True
                self._cr.commit()
                raise UserError("Unable To Write User Data")


    def send_subdomain_email(self):
        for obj in self:
            obj._compute_subdomain_token()
            template = self.env.ref('odoo_saas_kit.client_subdomain_template')
            mail_id = template.send_mail(obj.id)
            current_mail = self.env['mail.mail'].browse(mail_id)
            current_mail.send()
            obj.subdomain_email_sent = True


    def get_subdomain_url(self):
        self.ensure_one()
        params = {
            'contract_id': self.id,
            'token': self.token,
            'partner_id': self.partner_id.id
        }
        return '/mail/contract/subdomain?' + url_encode(params)


    # Used to confirm the contracts that are in Draft state but has a Client record associated with it. It created the client instance if already not created for a contract and then send the invitation email.
    def mark_confirmed(self):
        for obj in self:
            if obj.saas_client.client_url:
                obj.send_invitation_email()
            else:
                if not obj.domain_name:
                    raise UserError("Please select a domain first!")
                if obj.under_process:
                    raise UserError("Client Creation Already Under Progress!")
                else:

                    contracts = self.sudo().search([('domain_name', '=ilike', obj.domain_name), ('state', '!=', 'cancel')])
                    if len(contracts) > 1:
                        _logger.info("---------ALREADY TAKEN--------%r", contracts)
                        obj.domain_name = False
                        self._cr.commit()
                        raise UserError("This domain name is already in use! please try some other domain name!")

                    obj.under_process = True
                    self._cr.commit()
                if obj.server_id.max_clients <= obj.server_id.total_clients:
                    obj.under_process = False
                    self._cr.commit()
                    raise UserError("Maximum Clients limit reached!")
                vals = dict(
                    saas_contract_id = obj.id,
                    partner_id = obj.partner_id and obj.partner_id.id or False,
                    server_id = obj.server_id.id,
                    admin_username = obj.plan_id.db_template_username or False,
                    admin_password = obj.plan_id.db_template_password or False,
                )
                client_id = self.env['saas.client'].create(vals)
                obj.attach_modules(client_id)
                obj.write({'saas_client': client_id.id})
                self._cr.commit()
                try:
                    client_id.fetch_client_url(obj.domain_name)
                    _logger.info("--------Client--Created-------%r", client_id)
                except Exception as e:
                    obj.under_process = False
                    self._cr.commit()
                    _logger.info("--------Exception-While-Creating-Client-------%r", e)
                    raise UserError("Exceptionc While Creating Client {}".format(e))
                else:
                    obj.write({'state': 'open'})
                    obj.under_process = False
                    self._cr.commit()
                    if client_id.client_url:
                        template = obj.on_create_email_template
                        mail_id = template.send_mail(client_id.id)
                        current_mail = self.env['mail.mail'].browse(mail_id)
                        res = current_mail.send()
                        obj.write({'state': 'confirm'})
                        self._cr.commit()
                        return res


    # Used to create the clients and share credentials for the contracts.
    def create_saas_client(self):
        for obj in self:
            if not obj.domain_name:
                raise UserError("Please select a domain first!")
            if obj.under_process:
                raise UserError("Client Creation Already Under Progress!")
            else:
                domain_name = None
                if obj.use_separate_domain:
                    domain_name = obj.domain_name
                else:
                    domain_name = "{}.{}".format(obj.domain_name, obj.saas_domain_url)

                contracts = self.sudo().search([('domain_name', '=ilike', obj.domain_name), ('state', '!=', 'cancel')])
                if len(contracts) > 1:
                    _logger.info("---------ALREADY TAKEN--------%r", contracts)
                    obj.domain_name = False
                    self._cr.commit()
                    raise UserError("This domain name is already in use! Please try some other domain name!")

                obj.under_process = True
                self._cr.commit()
                if obj.server_id.max_clients <= obj.server_id.total_clients:
                    obj.under_process = False
                    self._cr.commit()
                    raise UserError("Maximum Clients limit reached!")
                vals = dict(
                    saas_contract_id = obj.id,
                    partner_id = obj.partner_id and obj.partner_id.id or False,
                    server_id = obj.server_id.id,
                )
                client_id = self.env['saas.client'].create(vals)
                obj.attach_modules(client_id)
                obj.write({'saas_client': client_id.id})
                self._cr.commit()
                try:
                    client_id.fetch_client_url(domain_name)
                    _logger.info("--------Client--Created-------%r", client_id)
                except Exception as e:
                    obj.under_process = False
                    self._cr.commit()
                    _logger.info("--------Exception-While-Creating-Client-------%r", e)
                    raise UserError("Exceptionc While Creating Client {}".format(e))
                else:
                    obj.write({'state': 'open'})
                    obj.under_process = False
                    self._cr.commit()
                    if client_id.client_url:
                        try:
                            token = generate_token()
                            _logger.info("--------------%r", token)
                            obj.sudo().set_user_data(token=token)
                            self._cr.commit()
                        except Exception as e:
                            _logger.info("--------EXCEPTION-WHILE-UPDATING-DATA-AND-SENDING-INVITE-------%r----", e)
                        else:
                            reset_pwd_url = "{}/web/signup?token={}&db={}".format(client_id.client_url, token, client_id.database_name)
                            client_id.invitation_url = reset_pwd_url
                            template = obj.on_create_email_template
                            mail_id = template.send_mail(client_id.id)
                            current_mail = self.env['mail.mail'].browse(mail_id)
                            res = current_mail.send()
                            obj.write({'state': 'confirm'})
                            self._cr.commit()
                            return res

    def extend_contract(self):
        for obj in self:
            obj.total_cycles += 1
            obj.remaining_cycles += 1

    # Used to create the next invoice for the contract
    def generate_invoice(self):
        for obj in self:
            if obj.remaining_cycles:
                user_count = None
                if obj.billing_criteria == 'per_user':
                    if obj.saas_client and obj.saas_client.database_name:
                        _, db_server = obj.plan_id.server_id.get_server_details()
                        response = query.get_user_count(obj.saas_client.database_name, db_server=db_server)
                        if response:
                            user_count = response[0][0]
                    if not user_count:
                        raise UserError("Couldn't fetch user count! Please try again later.")
                else:
                    user_count = 1
                invoice_vals = {
                    'type': 'out_invoice',
                    'partner_id': obj.partner_id and obj.partner_id.id or False,
                    'currency_id': obj.pricelist_id and obj.pricelist_id.currency_id.id or False,
                    'contract_id': obj.id,
                    # 'invoice_line_ids': [(0, 0, {
                    #     'price_unit': obj.contract_rate * int(user_count),
                    #     'quantity': 1.0,
                    #     'product_id': obj.invoice_product_id.id,
                    # })],
                }
                try:
                    invoice = self.env['account.move'].create(invoice_vals)
                    invoice.action_post()
                    _logger.info("--------Invoice--Created-------%r", invoice)
                except Exception as e:
                    _logger.info("--------Exception-While-Creating-Invoice-------%r", e)
                    raise UserError("Exception While Creating Invoice: {}".format(e))
                else:
                    relative_delta = relativedelta(months=self.recurring_interval)
                    old_date = obj.next_invoice_date and fields.Date.from_string(obj.next_invoice_date) or fields.Date.from_string(fields.Date.today())
                    next_date = fields.Date.to_string(old_date + relative_delta)
                    obj.remaining_cycles -= 1
                    obj.next_invoice_date = next_date
            else:
                raise UserError("This Contract Has Expired!")

    # Sends the subdomain selection url to the customer
    @api.model
    def get_subdomain_email(self, contract_id=None):
        self.browse(int(contract_id)).sudo().send_subdomain_email()

    # Sends the client credentials to the customer.
    # When the Contract is in Open state. Means the instance is created but the credentials haven't been shared yet.
    def send_credential_email(self):
        self.ensure_one()
        if not self.saas_client.client_url:
            raise UserError("SaaS Instance Not Found! Please create it from the associated client record for sharing the credentials.")
        template = self.on_create_email_template
        compose_form = self.env.ref('mail.email_compose_message_wizard_form')


        if self.plan_id.use_specific_user_template:
            try:
                token = generate_token()
                self.sudo().set_user_data(token=token)
                self._cr.commit()
                reset_pwd_url = "{}/web/signup?token={}&db={}".format(self.saas_client.client_url, token, self.saas_client.database_name)
                self.saas_client.invitation_url = reset_pwd_url
            except Exception as e:
                _logger.info("--------EXCEPTION-WHILE-UPDATING-DATA-AND-SENDING-INVITE-------%r----", e)

        ctx = dict(
            default_model='saas.client',
            default_res_id=self.saas_client.id,
            default_use_template=bool(template),
            default_template_id=template and template.id or False,
            default_composition_mode='comment',
        )
        return {
            'name': _('Compose Email'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form.id, 'form')],
            'view_id': compose_form.id,
            'target': 'new',
            'context': ctx,
        }

    @api.model
    def create_recurring_invoice(self):
        valid_contracts = self.search([('remaining_cycles', '>', 0), ('state', '=', 'confirm'), ('next_invoice_date', '<=', fields.Date.today()), ('auto_create_invoice', '=', True)])
        _logger.info("--------RECURRING-INVOICE-CRON--------%r", valid_contracts)

        for contract in valid_contracts:
            contract.generate_invoice()

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('saas.contract')
        res = super(SaasContract,self).create(vals)
        res.message_subscribe(partner_ids=[res.partner_id.id])
        return res

    def unlink(self):
        for obj in self:
            if obj.saas_client:
                raise UserError("Error: You must delete the associated SaaS Client first!")
        return super(SaasContract, self).unlink()
