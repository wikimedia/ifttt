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

import flask

from .triggers import APIQueryTriggerView
from .utils import is_valid_ip


class ValidateArticleTitle(APIQueryTriggerView):

    url_pattern = 'article_revisions/fields/title/validate'
    wiki = 'en.wikipedia.org'
    query_params = {'action': 'query',
                    'prop': 'info',
                    'titles': None,
                    'format': 'json'}

    def get_query(self):
        self.query_params['titles'] = self.params.get('value')
        if not self.query_params['titles']:
            flask.abort(400)
        return super(ValidateArticleTitle, self).get_query()

    def check_page(self):
        api_resp = self.get_query()
        page_ids = api_resp['query']['pages'].keys()
        if int(page_ids[0]) > 0:
            return True
        return False

    def post(self):
        self.params = flask.request.get_json(force=True, silent=True) or {}
        exists = self.check_page()
        title = self.query_params['titles']
        ret = {'valid': exists}
        if not exists:
            ret['message'] = ('A Wikipedia article on %s does not (yet)'
                              ' exist (go write it!)' % title)
        return flask.jsonify(data=ret)


class ValidateUser(APIQueryTriggerView):

    url_pattern = 'user_revisions/fields/user/validate'
    wiki = 'en.wikipedia.org'
    query_params = {'action': 'query',
                    'list': 'users',
                    'ususers': None,
                    'format': 'json'}

    def get_query(self):
        self.query_params['ususers'] = self.params.get('value')
        if not self.query_params['ususers']:
            flask.abort(400)
        return super(ValidateUser, self).get_query()

    def check_user(self):
        api_resp = self.get_query()
        user_ids = api_resp['query']['users']
        if user_ids[0].get('userid'):
            return True
        return is_valid_ip(self.query_params['ususers'])

    def post(self):
        self.params = flask.request.get_json(force=True, silent=True) or {}
        exists = self.check_user()
        title = self.query_params['ususers']
        ret = {'valid': exists}
        if not exists:
            ret['message'] = ('There is no Wikipedian named %s'
                              % title)
        return flask.jsonify(data=ret)
