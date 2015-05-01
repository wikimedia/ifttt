# -*- coding: utf-8 -*-
"""
  Wikipedia channel for IFTTT
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~

  Copyright 2015 Ori Livneh <ori@wikimedia.org>

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
import re
import datetime
import operator
import urllib2
from urllib import urlencode
import json
import time

import feedparser
import flask
import flask.views
import werkzeug.contrib.cache
import logging

from .utils import url_to_uuid5, utc_to_epoch, utc_to_iso8601, iso8601_to_epoch
from .dal import get_hashtags, get_all_hashtags

__all__ = ('FeaturedFeedTriggerView',)

feed_cache = werkzeug.contrib.cache.SimpleCache()

LOG_FILE = 'ifttt.log'
logging.basicConfig(filename=LOG_FILE,
                    format='%(asctime)s - %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.DEBUG)

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


class FeaturedFeedTriggerView(flask.views.MethodView):
    """Generic view for IFTT Triggers based on FeaturedFeeds."""

    URL_FORMAT = 'https://{0.wiki}/w/api.php?action=featuredfeed&feed={0.feed}'

    def get_feed(self):
        """Fetch and parse the feature feed for this class."""
        url = self.URL_FORMAT.format(self)
        feed = feed_cache.get(url)
        if not feed:
            feed = feedparser.parse(urllib2.urlopen(url))
            feed_cache.set(url, feed, timeout=5 * 60)
        return feed

    def parse_entry(self, entry):
        """Parse a single feed entry into an IFTTT trigger item."""
        # Not sure why, but sometimes we get http entry IDs. If we
        # don't have consistency between https/http, we get mutliple
        # unique UUIDs for the same entry.
        meta_id = url_to_uuid5(entry.id.replace('http:', 'https:'))
        date = entry.published_parsed
        created_at = utc_to_iso8601(date)
        ts = utc_to_epoch(date)
        return {'created_at': created_at, 
                'entry_id': meta_id, 
                'url': entry.id, 
                'meta': {'id': meta_id, 'timestamp': ts}}

    def get_items(self):
        """Get the set of items for this trigger."""
        feed = self.get_feed()
        feed.entries.sort(key=operator.attrgetter('published_parsed'),
                          reverse=True)
        return map(self.parse_entry, feed.entries)

    def post(self):
        """Handle POST requests."""
        self.params = flask.request.get_json(force=True, silent=True) or {}
        logging.info('%s: %s' %
                    (self.__class__.__name__,
                     self.params.get('trigger_identity')))
        limit = self.params.get('limit', 50)
        items = self.get_items()
        items = items[:limit]
        return flask.jsonify(data=items)


class APIQueryTriggerView(flask.views.MethodView):

    API_URL = 'http://{0.wiki}/w/api.php'
    TIMEOUT = 5 * 60

    def get_query(self):
        url_base = self.API_URL.format(self)
        params = urlencode(self.query_params)
        url = '%s?%s' % (url_base, params)
        resp = feed_cache.get(url)
        if not resp:
            resp = json.load(urllib2.urlopen(url))
            feed_cache.set(url, resp, timeout=self.TIMEOUT)
        return resp

    def parse_result(self, result):
        meta_id = url_to_uuid5(result['url'])
        created_at = result['date']
        ts = iso8601_to_epoch(result['date'])
        return {'created_at': created_at, 'meta': {
            'id': meta_id, 'timestamp': ts}
        }

    def get_results(self):
        resp = self.get_query()
        return map(self.parse_result, resp)

    def post(self):
        self.params = flask.request.get_json(force=True, silent=True) or {}
        logging.info('%s: %s' %
                    (self.__class__.__name__,
                     self.params.get('trigger_identity')))
        limit = self.params.get('limit', 50)
        ret = self.get_results()
        ret = ret[:limit]
        return flask.jsonify(data=ret)


class DailyAPIQueryTriggerView(flask.views.MethodView):

    API_URL = 'http://{0.wiki}/w/api.php'
    TIMEOUT = 1440 * 60

    def get_query(self):
        url_base = self.API_URL.format(self)
        params = urlencode(self.query_params)
        url = '%s?%s' % (url_base, params)
        resp = feed_cache.get(url + self.trigger_id)
        if not resp:
            resp = json.load(urllib2.urlopen(url))
            resp['published_parsed'] = datetime.datetime.utcnow().timetuple()
            feed_cache.set(url + self.trigger_id, resp, timeout=self.TIMEOUT)
        return resp

    def parse_query(self):
        query_resp = self.get_query()
        meta_id = url_to_uuid5(query_resp.get('article_url', ''))
        created_at = utc_to_iso8601(query_resp.get('published_parsed'))
        ts = utc_to_epoch(query_resp.get('published_parsed'))
        query_resp['created_at'] = created_at
        query_resp['meta'] = {'id': meta_id, 'timestamp': ts}
        return query_resp

    def post(self):
        self.params = flask.request.get_json(force=True, silent=True) or {}
        limit = self.params.get('limit', 50)
        self.trigger_id = self.params.get('trigger_identity', '')
        ret = [self.parse_query()]
        ret = ret[:limit]
        return flask.jsonify(data=ret)


class HashtagsTriggerView(flask.views.MethodView):

    url_pattern = 'hashtag'
    wiki = 'en.wikipedia.org'

    def get_hashtags(self):
        trigger_fields = self.params.get('triggerFields', {})
        self.tag = trigger_fields.get('hashtag')
        if self.tag is None:
            flask.abort(400)
        if self.tag == '':
            res = get_all_hashtags()
        else:
            res = get_hashtags(self.tag)
        return map(self.parse_result, res)

    def filter_hashtags(self, revs):
        not_tags = ['redirect', 'ifexist', 'if']
        for not_tag in not_tags:
            revs = [r for r in revs if not all(tag.lower() == not_tag for
                                              tag in r['raw_tags'])]
        return revs

    def parse_result(self, rev):
        date = datetime.datetime.strptime(rev['rc_timestamp'], '%Y%m%d%H%M%S')
        date = date.isoformat() + 'Z'
        tags = find_hashtags(rev['rc_comment'])
        ret = {
            'raw_tags': tags,
            'input_hashtag': self.tag,
            'return_hashtags': ' '.join(tags),
            'date': date,
            'url': 'https://%s/w/index.php?diff=%s&oldid=%s' %
                   (self.wiki,
                    int(rev['rc_this_oldid']),
                    int(rev['rc_last_oldid'])),
            'user': rev['rc_user_text'],
            'size': rev['rc_new_len'] - rev['rc_old_len'],
            'comment': rev['rc_comment'],
            'title': rev['rc_title']
        }
        ret['created_at'] = date
        ret['meta'] = {
            'id': url_to_uuid5(ret['url']),
            'timestamp': iso8601_to_epoch(date)
        }
        return ret

    def post(self):
        self.params = flask.request.get_json(force=True, silent=True) or {}
        logging.info('%s: %s' %
                    (self.__class__.__name__,
                     self.params.get('trigger_identity')))
        limit = self.params.get('limit', 50)
        ret = self.get_hashtags()
        ret = self.filter_hashtags(ret)
        ret = ret[:limit]
        return flask.jsonify(data=ret)

