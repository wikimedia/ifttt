# -*- coding: utf-8 -*-
"""
  Wikipedia channel for IFTTT
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~

  Copyright 2015 Ori Livneh <ori@wikimedia.org>
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

import datetime
import re
import time
import uuid
import socket


def snake_case(s):
    """Convert CamelCase to snake_case."""
    s = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', s)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s).lower()


def select(element, selector):
    """Syntactic sugar for element#cssselect that grabs the first match."""
    matches = element.cssselect(selector)
    return matches[0]


def url_to_uuid5(url):
    """Generate a UUID5 for a given URL."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, url.encode('utf-8')))


def utc_to_iso8601(struct_time):
    """Make a W3-style ISO 8601 UTC timestamp from a struct_time object."""
    struct_time = datetime.datetime.utcfromtimestamp(time.mktime(struct_time))
    return struct_time.date().isoformat()


def utc_to_epoch(struct_time):
    """Convert a struct_time to an integer number of seconds since epoch."""
    return int(time.mktime(struct_time))


def iso8601_to_epoch(iso_time):
    dt = datetime.datetime.strptime(iso_time, '%Y-%m-%dT%H:%M:%SZ')
    epoch = datetime.datetime.utcfromtimestamp(0)
    return int((dt - epoch).total_seconds())


def is_valid_ip(address):
    try:
        socket.inet_aton(address)
        return True
    except socket.error:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, address)
        return True
    except socket.error:
        pass
    return False


# From boltons
HASHTAG_RE = re.compile(r"(?:^|\s)[＃#]{1}(\w+)", re.UNICODE)


def find_hashtags(string):
    """Finds and returns all hashtags in a string, with the hashmark
    removed. Supports full-width hashmarks for Asian languages and
    does not false-positive on URL anchors.
    >>> find_hashtags('#atag http://asite/#ananchor')
    ['atag']
    ``find_hashtags`` also works with unicode hashtags.
    """

    # the following works, doctest just struggles with it
    # >>> find_hashtags(u"can't get enough of that dignity chicken #肯德基 woo")
    # [u'\u80af\u5fb7\u57fa']
    return HASHTAG_RE.findall(string)
