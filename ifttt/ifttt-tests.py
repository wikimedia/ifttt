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

from triggers import *

from .__init__ import create_app

import requests, unittest

# URL of the server that the app is running on.
# SERVER_URL = "http://127.0.0.1:5000"

class AotdTestCase(unittest.TestCase):
    """Test class for Article of the Day trigger"""

    def setUp(self):
        """Setup to run before each test case."""
        # Create the app using the factory method.
        self.app = create_app()

    def tearDown(self):
        """Teardown to run after each test case."""
        # Once all tests are run, return a pass to indicate
        # all tests where run correctly without any errors.
        pass

    def test_aotd_trigger_with_get(self):
        """Test suite for Article of the Day trigger which checks for 
        proper respone code after the GET request"""

        # response = requests.get(SERVER_URL + '/v1/triggers/article_of_the_day?lang=en')
        # self.assertEquals(response.status_code, 200)
        pass