# -*- coding: utf-8 -*-
"""
  Wikipedia channel for IFTTT
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~

  Copyright 2015 Ori Livneh <ori@wikimedia.org>
                 Stephen LaPorte <stephen.laporte@gmail.com>
                 Alangi Derick <alangiderick@gmail.com>

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

import core, json, unittest

from .utils import snake_case

# Import all triggers in the app
from .triggers import (ArticleOfTheDay,
                       PictureOfTheDay,
                       WordOfTheDay,
                       ArticleRevisions,
                       UserRevisions,
                       NewArticle,
                       NewHashtag,
                       NewCategoryMember,
                       CategoryMemberRevisions,
                       ItemRevisions)

# A list of triggers to be tested
ALL_TRIGGERS = [ArticleOfTheDay,
                PictureOfTheDay,
                WordOfTheDay,
                NewArticle,
                ItemRevisions,
                ArticleRevisions,
                NewHashtag,
                UserRevisions]

app = core.app.test_client()

def check_response(test_trigger):
    """Checks the response to see if the data property of the trigger 
    is greater than 3 after the request."""
    RESP_TEST_VALUE = 3

    # Test for Article Revisions
    if test_trigger == 'article_revisions':
      resp = app.post('/ifttt/v1/triggers/%s' % test_trigger, 
        data=json.dumps({"triggerFields":{"lang":"en","title":"Coffee"}}), 
        content_type='application/json')

      results = json.loads(resp.data)
      assert len(results['data']) >= RESP_TEST_VALUE

    # Testing for User Revisions
    if test_trigger == 'user_revisions':
      resp = app.post('/ifttt/v1/triggers/%s' % test_trigger, 
        data=json.dumps({"triggerFields":{"lang":"en","user":"ClueBot"}}), 
        content_type='application/json')

      results = json.loads(resp.data)
      assert len(results['data']) >= RESP_TEST_VALUE

    # Testing for Item Revisions
    if test_trigger == 'item_revisions':
      resp = app.post('/ifttt/v1/triggers/%s' % test_trigger, 
        data=json.dumps({"triggerFields":{"itemid":"Q12345"}}), 
        content_type='application/json')

      results = json.loads(resp.data)
      assert len(results['data']) >= RESP_TEST_VALUE

    # Testing for AotD
    if test_trigger == 'article_of_the_day':
      resp = app.post('/ifttt/v1/triggers/%s' % test_trigger, 
        data=json.dumps({"triggerFields":{"lang":"en"}}), 
        content_type='application/json')

      results = json.loads(resp.data)
      assert len(results['data']) >= RESP_TEST_VALUE
      
    # Testing for WotD (Word of the Day)
    if test_trigger == 'word_of_the_day':
      resp = app.post('/ifttt/v1/triggers/%s' % test_trigger, 
        data=json.dumps({"triggerFields":{"lang":"en"}}), 
        content_type='application/json')

      results = json.loads(resp.data)
      assert len(results['data']) >= RESP_TEST_VALUE

    # Testing for New Article
    if test_trigger == 'new_article':
      resp = app.post('/ifttt/v1/triggers/%s' % test_trigger, 
        data=json.dumps({"triggerFields":{"lang":"en"}}), 
        content_type='application/json')

      results = json.loads(resp.data)
      assert len(results['data']) >= RESP_TEST_VALUE

    # Testing for PotD (Picture of the Day)
    if test_trigger == 'picture_of_the_day':
      resp = app.post('/ifttt/v1/triggers/%s' % test_trigger, 
        data=json.dumps({"triggerFields":{"lang":"en"}}), 
        content_type='application/json')

      results = json.loads(resp.data)
      assert len(results['data']) >= RESP_TEST_VALUE

    # Testing for New hash tag
    if test_trigger == 'new_hashtag':
      resp = app.post('/ifttt/v1/triggers/%s' % test_trigger, 
        data=json.dumps({"triggerFields":{"lang":"en","hashtag":"test"}}), 
        content_type='application/json')

      results = json.loads(resp.data)
      assert len(results['data']) >= RESP_TEST_VALUE

# Routine to test the triggers one after the other
def test_for_triggers():
    for trigger in ALL_TRIGGERS:
        test_trigger = getattr(trigger, 'url_pattern', None)
        if not test_trigger:
            test_trigger = snake_case(trigger.__name__)
        yield check_response, test_trigger