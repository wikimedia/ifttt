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
import operator
import urllib2
import json
import lxml.html
import logging

import flask
import flask.views

import feedparser
import werkzeug.contrib.cache

from urllib import urlencode

from .dal import get_hashtags, get_all_hashtags
from .utils import (select,
                    url_to_uuid5,
                    utc_to_epoch,
                    utc_to_iso8601,
                    iso8601_to_epoch,
                    find_hashtags)

LOG_FILE = 'ifttt.log'
CACHE_EXPIRATION = 5 * 60
DEFAULT_LANG = 'en'

cache = werkzeug.contrib.cache.SimpleCache()

logging.basicConfig(filename=LOG_FILE,
                    format='%(asctime)s - %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.DEBUG)


class FeaturedFeedTriggerView(flask.views.MethodView):
    """Generic view for IFTT Triggers based on FeaturedFeeds."""

    _base_url = 'https://{0.wiki}/w/api.php?action=featuredfeed&feed={0.feed}'

    def get_feed(self):
        """Fetch and parse the feature feed for this class."""
        url = self._base_url.format(self)
        feed = cache.get(url)
        if not feed:
            feed = feedparser.parse(urllib2.urlopen(url))
            cache.set(url, feed, timeout=CACHE_EXPIRATION)
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
    """Generic view for IFTT Triggers based on API MediaWiki Queries."""

    _base_url = 'http://{0.wiki}/w/api.php'

    def get_query(self):
        formatted_url = self._base_url.format(self)
        params = urlencode(self.query_params)
        url = '%s?%s' % (formatted_url, params)
        resp = cache.get(url)
        if not resp:
            resp = json.load(urllib2.urlopen(url))
            cache.set(url, resp, timeout=CACHE_EXPIRATION)
        return resp

    def parse_result(self, result):
        meta_id = url_to_uuid5(result['url'])
        created_at = result['date']
        ts = iso8601_to_epoch(result['date'])
        return {'created_at': created_at,
                'meta': {'id': meta_id, 'timestamp': ts}}

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


class PictureOfTheDay(FeaturedFeedTriggerView):
    """Trigger for Wikimedia Commons Picture of the Day"""

    feed = 'potd'
    wiki = 'commons.wikimedia.org'

    def parse_entry(self, entry):
        """Scrape each PotD entry for its description and URL."""
        item = super(PictureOfTheDay, self).parse_entry(entry)
        summary = lxml.html.fromstring(entry.summary)
        image_node = select(summary, 'a.image img')
        file_page_node = select(summary, 'a.image')
        thumb_url = image_node.get('src')
        width = image_node.get('width')  # 300px per MediaWiki:Ffeed-potd-page
        image_url = thumb_url.rsplit('/' + width, 1)[0].replace('thumb/', '')
        desc_node = select(summary, '.description.en')
        item['image_url'] = image_url
        item['filepage_url'] = file_page_node.get('href')
        item['description'] = desc_node.text_content().strip()
        return item


class ArticleOfTheDay(FeaturedFeedTriggerView):
    """Trigger for Wikipedia's Today's Featured Article."""

    feed = 'featured'

    def get_items(self):
        trigger_fields = self.params.get('triggerFields', {})
        if not trigger_fields:
            flask.abort(400)
        self.lang = trigger_fields.get('lang')
        if not self.lang:
            flask.abort(400)
        if self.lang == '':
            self.lang = DEFAULT_LANG
        self.wiki = '%s.wikipedia.org' % self.lang
        return super(ArticleOfTheDay, self).get_items()

    def parse_entry(self, entry):
        """Scrape each AotD entry for its URL and title."""
        item = super(ArticleOfTheDay, self).parse_entry(entry)
        summary = lxml.html.fromstring(entry.summary)
        read_more = select(summary, 'p:first-of-type > a:last-of-type')
        item['url'] = read_more.get('href')
        item['title'] = read_more.get('title')
        return item


class WordOfTheDay(FeaturedFeedTriggerView):
    """Trigger for Wiktionary's Word of the Day."""

    feed = 'wotd'

    def get_items(self):
        trigger_fields = self.params.get('triggerFields', {})
        if not trigger_fields:
            flask.abort(400)
        self.lang = trigger_fields.get('lang')
        if not self.lang:
            flask.abort(400)  # required per IFTTT spec
        if self.lang == '':
            self.lang = DEFAULT_LANG
        self.wiki = '%s.wiktionary.org' % self.lang
        return super(WordOfTheDay, self).get_items()

    def parse_entry(self, entry):
        """Scrape each WotD entry for the word, article URL, part of speech,
        and definition."""
        item = super(WordOfTheDay, self).parse_entry(entry)
        summary = lxml.html.fromstring(entry.summary)
        div = summary.get_element_by_id('WOTD-rss-description')
        anchor = summary.get_element_by_id('WOTD-rss-title').getparent()
        item['word'] = anchor.get('title')
        item['url'] = anchor.get('href')
        item['part_of_speech'] = anchor.getparent().getnext().text_content()
        item['definition'] = div.text_content().strip()
        return item


class NewArticle(APIQueryTriggerView):
    """Trigger for each new article."""

    query_params = {'action': 'query',
                    'list': 'recentchanges',
                    'rctype': 'new',
                    'rclimit': 50,
                    'rcnamespace': 0,
                    'rcprop': 'title|ids|timestamp|user|sizes|comment',
                    'format': 'json'}

    def get_results(self):
        trigger_fields = self.params.get('triggerFields', {})
        if not trigger_fields:
            flask.abort(400)
        self.lang = trigger_fields.get('lang')
        if not self.lang:
            flask.abort(400)
        if self.lang == '':
            self.lang = DEFAULT_LANG
        self.wiki = '%s.wikipedia.org' % self.lang
        api_resp = self.get_query()
        try:
            pages = api_resp['query']['recentchanges']
        except KeyError:
            return []
        return map(self.parse_result, pages)

    def parse_result(self, rev):
        ret = {'date': rev['timestamp'],
               'url': 'https://%s/wiki/%s' %
                      (self.wiki, rev['title'].replace(' ', '_')),
               'user': rev['user'],
               'size': rev['newlen'] - rev['oldlen'],
               'comment': rev['comment'],
               'title': rev['title']}
        ret.update(super(NewArticle, self).parse_result(ret))
        return ret


class NewHashtag(flask.views.MethodView):
    """Trigger for hashtags in the edit summary."""

    url_pattern = 'hashtag'

    def get_hashtags(self):
        trigger_fields = self.params.get('triggerFields', {})
        if not trigger_fields:
            flask.abort(400)
        self.lang = trigger_fields.get('lang')
        if not self.lang:
            flask.abort(400)
        if self.lang == '':
            self.lang = DEFAULT_LANG
        self.wiki = '%s.wikipedia.org' % self.lang
        self.tag = trigger_fields.get('hashtag')
        if self.tag == '':
            res = cache.get('allhashtags')
            if not res:
                res = get_all_hashtags()
                cache.set('allhashtags', res, timeout=CACHE_EXPIRATION)
        else:
            res = cache.get('hashtags-%s' % self.tag)
            if not res:
                res = get_hashtags(self.tag)
                cache.set('hashtags-%s' % self.tag,
                          res,
                          timeout=CACHE_EXPIRATION)
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
        ret = {'raw_tags': tags,
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
               'title': rev['rc_title']}
        ret['created_at'] = date
        ret['meta'] = {'id': url_to_uuid5(ret['url']),
                       'timestamp': iso8601_to_epoch(date)}
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


class ArticleRevisions(APIQueryTriggerView):
    """Trigger for revisions to a specified article."""

    query_params = {'action': 'query',
                    'prop': 'revisions',
                    'titles': None,
                    'rvlimit': 50,
                    'rvprop': 'ids|timestamp|user|size|comment',
                    'format': 'json'}

    def get_query(self):
        trigger_fields = self.params.get('triggerFields', {})
        if not trigger_fields:
            flask.abort(400)
        self.lang = trigger_fields.get('lang')
        if not self.lang:
            flask.abort(400)
        if self.lang == '':
            self.lang = DEFAULT_LANG
        self.wiki = '%s.wikipedia.org' % self.lang
        self.query_params['titles'] = trigger_fields.get('title')
        if not self.query_params['titles']:
            flask.abort(400)
        return super(ArticleRevisions, self).get_query()

    def get_results(self):
        api_resp = self.get_query()
        try:
            page_id = api_resp['query']['pages'].keys()[0]
            revisions = api_resp['query']['pages'][page_id]['revisions']
        except KeyError:
            return []
        return map(self.parse_result, revisions)

    def parse_result(self, revision):
        ret = {'date': revision['timestamp'],
               'url': 'https://%s/w/index.php?diff=%s&oldid=%s' %
                      (self.wiki, revision['revid'], revision['parentid']),
               'user': revision['user'],
               'size': revision['size'],
               'comment': revision['comment'],
               'title': self.params['triggerFields']['title']}
        ret.update(super(ArticleRevisions, self).parse_result(ret))
        return ret


class UserRevisions(APIQueryTriggerView):
    """Trigger for revisions from a specified user."""

    query_params = {'action': 'query',
                    'list': 'usercontribs',
                    'ucuser': None,
                    'uclimit': 50,
                    'ucprop': 'ids|timestamp|title|size|comment',
                    'format': 'json'}

    def get_query(self):
        trigger_fields = self.params.get('triggerFields', {})
        if not trigger_fields:
            flask.abort(400)
        self.lang = trigger_fields.get('lang')
        if not self.lang:
            flask.abort(400)
        if self.lang == '':
            self.lang = DEFAULT_LANG
        self.wiki = '%s.wikipedia.org' % self.lang
        self.query_params['ucuser'] = trigger_fields.get('user')
        if not self.query_params['ucuser']:
            flask.abort(400)
        return super(UserRevisions, self).get_query()

    def get_results(self):
        api_resp = self.get_query()
        try:
            revisions = api_resp['query']['usercontribs']
        except KeyError:
            return []
        return map(self.parse_result, revisions)

    def parse_result(self, contrib):
        ret = {'date': contrib['timestamp'],
               'url': 'https://%s/w/index.php?diff=%s&oldid=%s' %
                      (self.wiki, contrib['revid'], contrib['parentid']),
               'user': self.params['triggerFields']['user'],
               'size': contrib['size'],
               'comment': contrib['comment'],
               'title': contrib['user']}
        ret.update(super(UserRevisions, self).parse_result(ret))
        return ret
