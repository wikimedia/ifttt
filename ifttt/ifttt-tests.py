# -*- coding: utf-8 -*-
"""
  Wikipedia channel for IFTTT
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~

  Copyright 2016 Alangi Derick <alangiderick@gmail.com>,
                 Stephen LaPorte <stephen.laporte@gmail.com>

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

import core, json

from .utils import snake_case

# Import all triggers in the app before they are 
# being tested. NOTE: The name of the triggers must 
# be in CamelCase so that they can be converted to 
# snake_case before running the tests.
from .triggers import (ArticleOfTheDay,
                       PictureOfTheDay,
                       WordOfTheDay,
                       ArticleRevisions,
                       UserRevisions,
                       NewArticle,
                       NewHashtag,
                       NewCategoryMember,
                       CategoryMemberRevisions,
                       ItemRevisions,
                       PopularPersonsBirthday)

# A list of triggers to be tested by the app. If any 
# trigger is built and wants to be tested, just add 
# the name of the trigger in CamelCase here and run 
# the tests in order to get the results.
ALL_TRIGGERS = [ArticleOfTheDay,
                PictureOfTheDay,
                WordOfTheDay,
                NewArticle,
                ItemRevisions,
                ArticleRevisions,
                NewHashtag,
                UserRevisions,
                NewCategoryMember,
                CategoryMemberRevisions,
                PopularPersonsBirthday]

# Creates a test instance of the applicatoin
app = core.app.test_client()

# Set debug mode to True for @app.before_request to run in 
# core.py and validate CHANNEL_KEY in the test instance 
# without returning 401
app.application.debug = True

def check_response(test_trigger, test_params):
    """Checks the response to see if the data property of the trigger 
    is greater than 3 after the request."""
    RESP_TEST_VALUE = 3

    resp = app.post('/ifttt/v1/triggers/%s' % test_trigger, 
        data=json.dumps({"triggerFields": test_params}), 
        content_type='application/json')

    results = json.loads(resp.data)
    assert len(results['data']) >= RESP_TEST_VALUE

# Gets the trigger and its corresponding default fields and send them 
# to check_response() to perform the POST request.
def test_for_triggers():
    for trigger in ALL_TRIGGERS:
        test_trigger = getattr(trigger, 'url_pattern', None)
        test_params = getattr(trigger, 'default_fields', None)
        if not test_trigger:
            test_trigger = snake_case(trigger.__name__)
        yield check_response, test_trigger, test_params