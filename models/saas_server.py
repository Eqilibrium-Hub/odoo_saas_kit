# -*- coding: utf-8 -*-
#################################################################################
#
#   Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>)
#   See LICENSE file for full copyright and licensing details.
#   License URL : <https://store.webkul.com/license.html/>
# 
#################################################################################
from odoo import api, fields, models
from odoo.exceptions import UserError, Warning, ValidationError
from . lib import check_connectivity
from . lib import check_if_db_accessible

SERVER_TYPE = [
    ('containerized', "Containerized Instance"),
    # ('same_odoo_server', "Current Odoo Server"),
    # ('different_odoo_server', "Same machine with different odoo server"),
    # ('different_odoo_server', "Different Odoo Server"),
]
DB_SCHEME = [
    ('create', "Database creation"),
    ('clone', "Database cloning"),
]
HOST_SERVER = [
    ('self', "Self (Same Server)"),
    ('remote', "Remote Server"),
]
DB_SERVER = [
    ('self', "Self (Same Server)"),
    ('remote', "Remote Server"),
]
STATE = [
    ('draft', "Draft"),
    ('confirm', "Confirm"),
]


class SaasServer(models.Model):
    _name = "saas.server"
    _description = 'Class for managing server types for deploying SaaS architecture.'

    def _compute_total_clients(self):
        for server in self:
            number_of_clients = len(
                self.env['saas.client'].search(
                    [('server_id.id', '=', server.id)]))
            server.total_clients = number_of_clients

    name = fields.Char(string="Plan", required=True)
    server_type = fields.Selection(
        selection=SERVER_TYPE,
        string="Type",
        required=True,
        default="containerized",
        readonly=True)
    host_server = fields.Selection(
        selection=HOST_SERVER,
        string="Host Server",
        required=True,
        default="self")
    db_server = fields.Selection(
        selection=DB_SERVER,
        string="Database Host Server",
        required=True,
        default="self")
    max_clients = fields.Integer(
        string="Maximum Allowed Clients",
        default="10",
        required=True)
    server_domain = fields.Char(string="Server Domain(Default)", required="True")
    odoo_url = fields.Char(string="Odoo URL")
    db_host = fields.Char(string="Database Host", default="localhost")
    db_port = fields.Char(string="Database Port", default="5432")
    db_user = fields.Char(string="Database Username")
    db_pass = fields.Char(string="Database Password")
    sftp_host = fields.Char(string="SFTP Host")
    sftp_port = fields.Char(
        string="SFTP Port",
        default="22")
    sftp_user = fields.Char(string="User")
    sftp_password = fields.Char(string="Password")
    db_creation_scheme = fields.Selection(
        selection=DB_SCHEME,
        string="Database Scheme",
        default="create")
    base_db = fields.Char(string="Base Database Name")
    sequence = fields.Integer(
        'sequence',
        help="Sequence for the handle.",
        default=10)
    total_clients = fields.Integer(
        compute='_compute_total_clients',
        string="No. Of Clients")
    state = fields.Selection(selection=STATE, string="State", default="draft")

    def test_host_connection(self):
        for obj in self:
            host_server, _ = obj.get_server_details()
            try:
                check_connectivity.ishostaccessible(host_server)
            except Exception as e:
                raise UserError("Connection Failure!\n{}".format(e))
            else:
                raise UserError("Connection successful!")

    def test_db_connection(self):
        for obj in self:
            _, db_server = obj.get_server_details()
            try:
                #check_connectivity.isdbaccessible(db_server)
                check_if_db_accessible.isdbaccessible(host_server = _ , db_server = db_server)
            except Exception as e:
                raise UserError("Connection Failure!\n{}".format(e))
            else:
                raise UserError("Connection successful!")

    def set_confirm(self):
        for obj in self:
            obj.state = 'confirm'

    def reset_to_draft(self):
        for obj in self:
            plans = self.env['saas.plan'].search([('server_id', '=', obj.id), ('state', '=', 'confirm')])
            if plans:
                raise UserError("This Server has some confirmed SaaS Plan(s)!")
            obj.state = 'draft'

    def unlink(self):
        for obj in self:
            if obj.state == 'confirm':
                raise UserError("You must reset the SaaS Server to draft first!")
            plans = self.env['saas.plan'].search([('server_id', '=', obj.id), ('state', '=', 'confirm')])
            if plans:
                raise UserError("You must delete the associated SaaS Plan(s) first!")
        return super(SaasServer, self).unlink()

    @api.model
    def get_server_details(self):
        host_server = dict(
            server_type=self.host_server,
            host=self.sftp_host,
            port=self.sftp_port,
            user=self.sftp_user,
            password=self.sftp_password,
            server_domain = self.server_domain
        )
        db_server = dict(
            server_type=self.db_server,
            host= self.db_host,
            port= self.db_port or 5432,
            user=self.db_user,
            password=self.db_pass
        )
        return host_server, db_server
