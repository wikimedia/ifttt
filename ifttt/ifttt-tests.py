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

from .triggers import (ArticleOfTheDay,
                       PictureOfTheDay,
                       WordOfTheDay,
                       NewArticle)

ALL_TRIGGERS = [ArticleOfTheDay,
                PictureOfTheDay,
                WordOfTheDay,
                NewArticle]

app = core.app.test_client()

def check_response(test_trigger):
    """Checks the response to see if the data property of the trigger 
    is greater than 3 after the request."""
    resp_test_value = 3

    # UserRevision and ArticleRevisions fails the test 
    # since it maybe needs some custom data to be sent 
    # in the post request.
    resp = app.post('/v1/triggers/%s' % test_trigger)

    results = json.loads(resp.data)
    assert results['data'] >= resp_test_value

def test_for_triggers():
    for trigger in ALL_TRIGGERS:
        test_trigger = getattr(trigger, 'url_pattern', None)
        if not test_trigger:
            test_trigger = snake_case(trigger.__name__)
        yield check_response, test_trigger