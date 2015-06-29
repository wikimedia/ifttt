# -*- coding: utf-8 -*-
"""
  Wikipedia channel for IFTTT
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~

  Copyright 2015 Stephen LaPorte <stephen.laporte@gmail.com>

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

"""

import os
import oursql

DEFAULT_HOURS = 2
DEFAULT_LANG = 'en'
DEFAULT_LIMIT = 50

DB_CONFIG_PATH = os.path.expanduser('~/replica.my.cnf')  # Available by default on Labs


def run_query(query, query_params, lang):
    db_title = lang + 'wiki_p'
    db_host = lang + 'wiki.labsdb'
    connection = oursql.connect(db=db_title,
                                host=db_host,
                                read_default_file=DB_CONFIG_PATH,
                                charset=None)
    cursor = connection.cursor(oursql.DictCursor)
    cursor.execute(query, query_params)
    ret = cursor.fetchall()
    return ret


def get_hashtags(tag, lang=DEFAULT_LANG, hours=DEFAULT_HOURS, limit=DEFAULT_LIMIT):
    if tag and tag[0] == '#':
        tag = tag[1:]
    if tag == 'test':
        interval = '14 DAY'
    else:
        interval = '%s HOUR' % hours
    query = '''
        SELECT *
        FROM recentchanges
        WHERE rc_type = 0
        AND rc_timestamp >= DATE_SUB(NOW(), INTERVAL %s)
        AND rc_comment REGEXP ?
        ORDER BY rc_timestamp DESC
        LIMIT ?''' % interval
    query_params = ('(^| )#%s[[:>:]]' % tag, limit)
    ret = run_query(query, query_params, lang)
    return ret


def get_all_hashtags(lang=DEFAULT_LANG, hours=DEFAULT_HOURS, limit=DEFAULT_LIMIT):
    query = '''
        SELECT *
        FROM recentchanges
        WHERE rc_type = 0
        AND rc_timestamp > DATE_SUB(NOW(), INTERVAL ? HOUR)
        AND rc_comment REGEXP ?
        LIMIT ?'''
    query_params = (hours, '(^| )#[[:alpha:]]{2}[[:alnum:]]*[[:>:]]', limit)
    ret = run_query(query, query_params, lang)
    return ret


def get_category_members(category_name, lang=DEFAULT_LANG,
                         hours=DEFAULT_HOURS, limit=DEFAULT_LIMIT):
    query = '''
        SELECT * FROM page, categorylinks
        WHERE categorylinks.cl_to = ?
        AND page.page_id = categorylinks.cl_from
        AND categorylinks.cl_timestamp >= DATE_SUB(NOW(), 
                                                   INTERVAL ? HOUR)
        ORDER BY categorylinks.cl_timestamp DESC
        LIMIT ?'''
    query_params = (category_name.replace(' ', '_'), hours, limit)
    ret = run_query(query, query_params, lang)
    return ret


def get_category_member_revisions(category_name, lang=DEFAULT_LANG,
                                  hours=DEFAULT_HOURS, limit=DEFAULT_LIMIT):
    query = '''
        SELECT rc.rc_id, 
               rc.rc_cur_id, 
               rc.rc_title, 
               rc.rc_timestamp, 
               rc.rc_this_oldid, 
               rc.rc_last_oldid, 
               rc.rc_user_text, 
               rc.rc_old_len, 
               rc.rc_new_len, 
               rc.rc_comment 
         FROM recentchanges AS rc 
         INNER JOIN categorylinks AS cl 
         ON rc.rc_cur_id = cl.cl_from
         WHERE cl.cl_to = ?
         AND rc.rc_type = 0
         AND rc.rc_timestamp >= DATE_SUB(NOW(), 
                                         INTERVAL ? HOUR) 
         ORDER BY rc.rc_timestamp DESC
         LIMIT ?'''
    query_params = (category_name.replace(' ', '_'), hours, limit)
    ret = run_query(query, query_params, lang)
    return ret
