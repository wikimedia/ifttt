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

DB_CONFIG_PATH = os.path.expanduser('~/replica.my.cnf')
TEMPLATES_PATH = 'templates'


def get_hashtags(tag, lang='en', hours=DEFAULT_HOURS):
    query = '''
        SELECT *
        FROM recentchanges
        WHERE rc_type = 0
        AND rc_timestamp > DATE_FORMAT(DATE_SUB(NOW(),
                                       INTERVAL ? HOUR), '%Y%m%d%H%i%s')
        AND rc_comment REGEXP ?'''
    db_title = lang + 'wiki_p'
    db_host = lang + 'wiki.labsdb'
    connection = oursql.connect(db=db_title,
                                host=db_host,
                                read_default_file=DB_CONFIG_PATH,
                                charset=None)
    cursor = connection.cursor(oursql.DictCursor)
    cursor.execute(query, (hours, '(^| )[#]{1}' + tag + '[[:>:]]'))
    ret = cursor.fetchall()
    return ret
