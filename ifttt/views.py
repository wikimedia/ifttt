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
import datetime
import operator
import urllib2
from urllib import urlencode
import json

import feedparser
import flask
import flask.views
import werkzeug.contrib.cache

from .utils import url_to_uuid5, utc_to_epoch, utc_to_iso8601, iso8601_to_epoch
from .dal import get_hashtags

__all__ = ('FeaturedFeedTriggerView',)

feed_cache = werkzeug.contrib.cache.SimpleCache()


class FeaturedFeedTriggerView(flask.views.MethodView):
    """Generic view for IFTT Triggers based on FeaturedFeeds."""

    URL_FORMAT = 'http://{0.wiki}/w/api.php?action=featuredfeed&feed={0.feed}'

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
        id = url_to_uuid5(entry.id)
        created_at = utc_to_iso8601(entry.published_parsed)
        ts = utc_to_epoch(entry.published_parsed)
        return {'created_at': created_at, 'meta': {'id': id, 'timestamp': ts}}

    def get_items(self):
        """Get the set of items for this trigger."""
        feed = self.get_feed()
        feed.entries.sort(key=operator.attrgetter('published_parsed'),
                          reverse=True)
        return map(self.parse_entry, feed.entries)

    def post(self):
        """Handle POST requests."""
        params = flask.request.get_json(force=True, silent=True) or {}
        limit = params.get('limit', 50)
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
        params = flask.request.get_json(force=True, silent=True) or {}
        limit = params.get('limit', 50)
        self.post_data = json.loads(flask.request.data)
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
        params = flask.request.get_json(force=True, silent=True) or {}
        limit = params.get('limit', 50)
        self.post_data = json.loads(flask.request.data)
        self.trigger_id = self.post_data.get('trigger_identity', '')
        ret = [self.parse_query()]
        ret = ret[:limit]
        return flask.jsonify(data=ret)


class HashtagsTriggerView(flask.views.MethodView):

    url_pattern = 'hashtag'

    def get_hashtags(self):
        self.tag = self.post_data('hashtag')
        if not self.tag:
            flask.abort(400)
        resp = get_hashtags()

    def post(self):
        params = flask.request.get_json(force=True, silent=True) or {}
        limit = params.get('limit', 50)
        self.post_data = json.loads(flask.request.data)

        ret = [self.parse_query()]
        ret = ret[:limit]
        return flask.jsonify(data=ret)
