import os,time,sys,shutil
import random, string
import json
import subprocess
import imp,re,shutil
import argparse
import logging
from collections import defaultdict
import socket
from contextlib import closing
import logging
_logger = logging.getLogger(__name__)
from . pg_query import PgQuery
#import pg_query


#CONF VALUES

def get_user_count(database,host_server = None, db_server = None):
    query = "SELECT COUNT(*) FROM res_users WHERE active=True;"

    pgX = PgQuery(db_server['host'], database, db_server['user'], db_server['password'], db_server['port'])

    with pgX:
        result = pgX.selectQuery(query)
    return result

def get_credentials(database, host_server = None, db_server = None):
    #FOR admin user_id = 2
    query = "SELECT login, COALESCE(password, '') FROM res_users WHERE id=2;"

    pgX = PgQuery(db_server['host'], database, db_server['user'], db_server['password'], db_server['port'])

    with pgX:
        result = pgX.selectQuery(query)
    return result

def update_user(database, user_id, user_data, partner_data,host_server = None, db_server = None):
    #FOR admin user_id = 2
    user_id = user_id or 2
    # print("----------------%-----%---%---%", database, user_data, partner_data, user_id)
    pgX = PgQuery(db_server['host'], database, db_server['user'], db_server['password'], db_server['port'])
    query = "Update res_users set login = '%s' WHERE id =%d;"%(user_data['login'],user_id)

    with pgX:
        result = pgX.executeQuery(query)
    with pgX:
        partner_id = pgX.selectQuery("Select partner_id from res_users where id = %d;"%user_id)[0][0]
    print(partner_id)
    query = "Update res_partner set name = '%s', street = '%s', street2 = '%s', city = '%s', zip = '%s', phone = '%s', mobile = '%s', email = '%s', website = '%s', signup_token = '%s', signup_type = '%s' WHERE id =%s;"%(partner_data['name'],partner_data['street'],partner_data['street2'],partner_data['city'],partner_data['zip'],partner_data['phone'],partner_data['mobile'],partner_data['email'],partner_data['website'], partner_data['signup_token'], partner_data['signup_type'], partner_id)

    with pgX:
        result = pgX.executeQuery(query)

    return result


def set_trial_data(database, trial_data, db_server=None):
    pgX = PgQuery(db_server['host'], database, db_server['user'], db_server['password'], db_server['port'])
    query1 = "Update ir_config_parameter set value ='{}' where key='trial.is_trial_enabled'".format(trial_data['trial.is_trial_enabled'])
    query2 = "Update ir_config_parameter set value ='{}' where key='trial.trial_period'".format(trial_data['trial.trial_period'])
    query3 = "Update ir_config_parameter set value ='{}' where key='trial.purchase_link'".format(trial_data['trial.purchase_link'])
    with pgX:
        result1 = pgX.executeQuery(query1)
        result2 = pgX.executeQuery(query2)
        result3 = pgX.executeQuery(query3)
    return result1 and result2 and result3


if __name__=='__main__':
    data = {
      'database': 'template_test_plan_tid_31',
      'user_id': 6,
      'user_data': {
        'name': 'Aditya Sharma',
        'login': 'aditya.sharma185@webkul.com'
      },
      'partner_data': {
        'name': 'Aditya Sharma',
        'street': '',
        'street2': '',
        'city': '',
        'state_id': False,
        'zip': '',
        'country_id': False,
        'phone': '',
        'mobile': '',
        'email': 'aditya.sharma185@webkul.com',
        'website': '',
        'signup_token': 'asghCKmcBjZ1FIMiI78k',
        'signup_type': 'signup'
      }
    }
    #print(get_credentials())
    #print(update_user(**data))
