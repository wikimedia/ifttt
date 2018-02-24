

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

import os
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

from dal import (get_hashtags, 
                  get_all_hashtags, 
                  get_category_members,
                  get_category_member_revisions,
                  get_article_list_revisions)

from utils import (select,
                    url_to_uuid5,
                    utc_to_epoch,
                    utc_to_iso8601,
                    iso8601_to_epoch,
                    find_hashtags)

LOG_FILE = 'ifttt.log'
CACHE_EXPIRATION = 5 * 60
LONG_CACHE_EXPIRATION = 12 * 60 * 60
DEFAULT_LANG = 'en'
TEST_FIELDS = ['test', 'Coffee', 'ClueBot', 'All stub articles'] 
# test properties currently mixed  with trigger default values
DEFAULT_RESP_LIMIT = 50  # IFTTT spec
MAXRADIUS = 10000  # Wikipedia's max geosearch radius

_cur_dir = os.path.dirname(__file__)
_cache_dir = os.path.join(_cur_dir, '../cache')
cache = werkzeug.contrib.cache.FileSystemCache(_cache_dir)

logging.basicConfig(filename=LOG_FILE,
                    format='%(asctime)s - %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.DEBUG)

# From https://www.mediawiki.org/wiki/Manual:Namespace
NAMESPACE_MAP = {
    0: 'Article',
    1: 'Talk',
    2: 'User',
    3: 'User talk',
    4: 'Wikipedia',
    5: 'Wikipedia talk',
    6: 'File',
    7: 'File talk',
    8: 'MediaWiki',
    9: 'MediaWiki talk',
    10: 'Template',
    11: 'Template talk',
    12: 'Help',
    13: 'Help talk',
    14: 'Category',
    15: 'Category talk',
    100: 'Portal',
    101: 'Portal talk',
    108: 'Book',
    109: 'Book talk',
    118: 'Draft',
    119: 'Draft talk',
    446: 'Education Program',
    447: 'Education Program talk',
    710: 'TimedText',
    711: 'TimedText talk',
    828: 'Module',
    829: 'Module talk',
    -1: 'Special',
    -2: 'Media'
}

DEFAULT_IMAGE = 'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Wikipedia%27s_W.svg/500px-Wikipedia%27s_W.svg.png'

def add_images(get_data):
    def with_images(*args, **kwargs):
        data = get_data(*args, **kwargs)
        titles = [item['title'] for item in data]
        images = get_page_image(titles)
        for i, res in enumerate(data):
            title = res['title']
            data[i]['media_url'] = images.get(title)
            if not data[i]['media_url']:
                data[i]['media_url'] = DEFAULT_IMAGE
        return data
    return with_images
        

def get_page_image(page_titles, lang=DEFAULT_LANG, timeout=LONG_CACHE_EXPIRATION):
    page_images = {}
    base_url = 'https://%s.wikipedia.org/w/api.php'
    formatted_url = base_url % lang
    params = {'action': 'query',
              'prop': 'pageimages',
              'pithumbsize': 500,
              'format': 'json',
              'pilimit': 50,
              'titles': '|'.join([title.replace(' ', '_') for title in page_titles])}
    params = urlencode(params)
    url = '%s?%s' % (formatted_url, params)
    resp = json.load(urllib2.urlopen(url))
    pages = resp.get('query', {}).get('pages', {})
    if not pages:
        return None
    for page_id in pages.keys():
        page_title = pages[page_id]['title']
        image_url = pages[page_id].get('thumbnail', {}).get('source')
        page_images[page_title] = image_url
    return page_images


class BaseTriggerView(flask.views.MethodView):

    default_fields = {}
    optional_fields = []

    def get_data(self):
        pass

    def post(self):
        """Handle POST requests."""
        self.fields = {}
        self.params = flask.request.get_json(force=True, silent=True) or {}
        self.limit = self.params.get('limit', DEFAULT_RESP_LIMIT)
        trigger_identity = self.params.get('trigger_identity')
        trigger_values = self.params.get('triggerFields', {})
        for field, value in trigger_values.items():
            self.fields[field] = value
        for field, default_value in self.default_fields.items():
            if field not in self.fields and field in self.optional_fields:
                if field not in TEST_FIELDS:
                    self.fields[field] = default_value
            elif field not in self.fields:
                flask.abort(400)

        logging.info('%s: %s' % (self.__class__.__name__, trigger_identity))
        data = self.get_data()
        data = data[:self.limit]
        return flask.jsonify(data=data)


class BaseFeaturedFeedTriggerView(BaseTriggerView):
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

    def get_data(self):
        """Get the set of items for this trigger."""
        feed = self.get_feed()
        feed.entries.sort(key=operator.attrgetter('published_parsed'),
                          reverse=True)
        return map(self.parse_entry, feed.entries)

class BaseAPIQueryTriggerView(BaseTriggerView):
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

    def get_data(self):
        resp = self.get_query()
        return map(self.parse_result, resp)


class PictureOfTheDay(BaseFeaturedFeedTriggerView):
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
        # TODO: include authorship for the picture
        item['filename'] = image_node.get('alt')
        item['image_url'] = image_url
        item['filepage_url'] = file_page_node.get('href')
        item['description'] = desc_node.text_content().strip()
        return item


class ArticleOfTheDay(BaseFeaturedFeedTriggerView):
    """Trigger for Wikipedia's Today's Featured Article."""

    default_fields = {'lang': DEFAULT_LANG}
    feed = 'featured'

    @add_images
    def get_data(self):
        self.wiki = '%s.wikipedia.org' % self.fields['lang']
        return super(ArticleOfTheDay, self).get_data()

    def parse_entry(self, entry):
        """Scrape each AotD entry for its URL and title."""
        item = super(ArticleOfTheDay, self).parse_entry(entry)
        summary = lxml.html.fromstring(entry.summary)
        item['summary'] = select(summary, 'p:first-of-type').text_content()
        item['summary'] = item['summary'].replace(u'(Full\xa0article...)', '')
        read_more = select(summary, 'p:first-of-type a:last-of-type')
        item['url'] = read_more.get('href')
        item['title'] = read_more.get('title')
        return item


class WordOfTheDay(BaseFeaturedFeedTriggerView):
    """Trigger for Wiktionary's Word of the Day."""

    default_fields = {'lang': DEFAULT_LANG}
    feed = 'wotd'

    def get_data(self):
        self.wiki = '%s.wiktionary.org' % self.fields['lang']
        return super(WordOfTheDay, self).get_data()

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

class TrendingTopics(BaseTriggerView):
    """Trigger for Wikipedia trending"""

    url = 'https://wikipedia-trending.wmflabs.org'
    default_fields = {'hrs': '24', 'edits': 10, 'editors': 4, 'score': 0.00001,
        'title_contains': False }
    optional_fields = [ 'hrs', 'edits', 'editors', 'score', 'title_contains' ]

    def query(self, path):
        url = '%s%s' % (self.url, path)
        resp = cache.get(url)
        if not resp:
            resp = json.load(urllib2.urlopen(url))
            cache.set(url, resp, timeout=60)
        return resp

    def get_data(self):
        resp = self.query('/api/trending/enwiki/%s'%self.fields['hrs'])
        return filter(self.only_trending, map(self.parse_result, resp['pages']))

    def only_trending(self, page):
        min_edits = self.fields['edits']
        min_editors = self.fields['editors']
        min_score = self.fields['score']
        title_contains = self.fields['title_contains']
        title_match = True
        if title_contains:
            if title_contains.lower() in page['title'].lower():
                title_match = True
            else:
                title_match = False

        return page['edits'] >= min_edits and page['editors'] >= min_editors and \
            page['score'] >= min_score and title_match

    def parse_result(self, page):
        url = "https://en.wikipedia.org/wiki/%s?referrer=ifttt-trending"%page['title'].replace(' ', '_')
        updated = page['updated'][0:19] + 'Z'
        try:
            thumbUrl = page['thumbnail']['source']
        except KeyError:
            thumbUrl = DEFAULT_IMAGE
        return {
            'thumbURL': thumbUrl,
            'bias': page['bias'],
            'tags': page['tags'],
            'title': page['title'],
            'url': url,
            'score': page['trendiness'],
            'date': updated,
            'since': page['start'][0:19] + 'Z',
            'edits': page['edits'],
            'editors': len(page['contributors']),
            'meta': {'id': url_to_uuid5(url),
                 'timestamp': iso8601_to_epoch(updated)},
        }

class NewArticle(BaseAPIQueryTriggerView):
    """Trigger for each new article."""

    default_fields = {'lang': DEFAULT_LANG}
    query_params = {'action': 'query',
                    'list': 'recentchanges',
                    'rctype': 'new',
                    'rclimit': 50,
                    'rcnamespace': 0,
                    'rcprop': 'title|ids|timestamp|user|sizes|comment',
                    'format': 'json'}

    def get_data(self):
        self.wiki = '%s.wikipedia.org' % self.fields['lang']
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


class NewHashtag(BaseTriggerView):
    """Trigger for hashtags in the edit summary."""

    default_fields = {'lang': DEFAULT_LANG, 'hashtag': 'test'}
    optional_fields = ['hashtag']
    url_pattern = 'new_hashtag'
    
    @add_images
    def get_data(self):
        self.wiki = '%s.wikipedia.org' % self.fields['lang']
        self.tag = self.fields['hashtag']
        self.lang = self.fields['lang']
        if self.tag == '':
            res = get_all_hashtags(lang=self.lang, limit=self.limit)
        else:
            res = get_hashtags(self.tag, lang=self.lang, limit=self.limit)
        res.sort(key=lambda rev: rev['rc_timestamp'], reverse=True) 
        return filter(self.validate_tags, map(self.parse_result, res))

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

    def validate_tags(self, rev):
        _not_tags = ['redirect', 'tag', 'ifexist', 'if']
        if set([tag.lower() for tag in rev['raw_tags']]) - set(_not_tags):
            return True
        else:
            return False


class NewCategoryMember(BaseTriggerView):
    """Trigger each time a new article appears in a category"""
    default_fields = {'lang': DEFAULT_LANG, 'category': 'All stub articles'}
    
    @add_images
    def get_data(self):
        self.lang = self.fields['lang']
        self.category = self.fields['category']
        self.wiki = '%s.wikipedia.org' % self.fields['lang']
        cache_name = 'cat-%s-%s-%s' % (self.category, self.lang, self.limit)
        res = cache.get(cache_name)
        if not res:
            res = get_category_members(self.category, lang=self.lang)
            cache.set(cache_name,
                      res,
                      timeout=CACHE_EXPIRATION)
        res.sort(key=lambda rev: rev['cl_timestamp'], reverse=True)
        return map(self.parse_result, res)

    def parse_result(self, rev):
        date = rev['cl_timestamp']
        date = date.isoformat() + 'Z'
        namespace = NAMESPACE_MAP.get(rev['rc_namespace'])
        if namespace and rev['rc_namespace'] > 0:
            title = namespace + ':' + rev['rc_title']
        else:
            title = rev['rc_title']
        if namespace is not None:
            url = 'https://%s/wiki/%s' % (self.wiki, title.replace(' ', '_'))
        else:
            # Use curid because we don't know the namespace
            url = 'https://%s/w/index.php?curid=%s' % (self.wiki, rev['rc_cur_id'])
        ret = {'date': date,
               'url': url,
               'title': title.replace('_', ' '),
               'category' : self.category}
        ret['created_at'] = date
        ret['meta'] = {'id': url_to_uuid5(ret['url']),
                       'timestamp': iso8601_to_epoch(date)}
        return ret


class CategoryMemberRevisions(BaseTriggerView):
    """Trigger for revisions to articles within a specified category."""

    default_fields = {'lang': DEFAULT_LANG, 'category': 'All stub articles'}
    
    @add_images
    def get_data(self):
        self.lang = self.fields['lang']
        self.category = self.fields['category']
        self.wiki = '%s.wikipedia.org' % self.fields['lang']
        cache_name = 'cat-revs-%s-%s-%s' % (self.category, self.lang, self.limit)
        res = cache.get(cache_name)
        if not res:
            res = get_category_member_revisions(self.category, lang=self.lang)
            cache.set(cache_name,
                      res,
                      timeout=CACHE_EXPIRATION)
        res.sort(key=lambda rev: rev['rc_timestamp'], reverse=True)
        return map(self.parse_result, res)

    def parse_result(self, rev):
        date = datetime.datetime.strptime(rev['rc_timestamp'], '%Y%m%d%H%M%S')
        date = date.isoformat() + 'Z'
        if not rev['rc_new_len']:
            rev['rc_new_len'] = 0
        if not rev['rc_old_len']:
            rev['rc_old_len'] = 0
        ret = {'date': date,
               'url': 'https://%s/w/index.php?diff=%s&oldid=%s' %
                      (self.wiki,
                       int(rev['rc_this_oldid']),
                       int(rev['rc_last_oldid'])),
               'user': rev['rc_user_text'],
               'size': rev['rc_new_len'] - rev['rc_old_len'],
               'comment': rev['rc_comment'],
               'title': rev['rc_title'].replace('_', ' ')}
        ret['created_at'] = date
        ret['meta'] = {'id': url_to_uuid5(ret['url']),
                       'timestamp': iso8601_to_epoch(date)}
        return ret


class ArticleRevisions(BaseAPIQueryTriggerView):
    """Trigger for revisions to a specified article."""

    default_fields = {'lang': DEFAULT_LANG, 'title': 'Coffee'}
    query_params = {'action': 'query',
                    'prop': 'revisions',
                    'titles': None,
                    'rvlimit': 50,
                    'rvprop': 'ids|timestamp|user|size|comment',
                    'format': 'json'}

    def get_query(self):
        self.wiki = '%s.wikipedia.org' % self.fields['lang']
        self.query_params['titles'] = self.fields['title']
        return super(ArticleRevisions, self).get_query()

    @add_images
    def get_data(self):
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


class GeoRevisions(BaseAPIQueryTriggerView):
    """Trigger for revisions in a geographic area"""

    default_fields = {'lang': DEFAULT_LANG, 
                      'location': {'lat': 37.34347580224911,
                                   'lng': -121.89543345662234,
                                   'radius': 10000}}
    query_params = {'action': 'query',
                    'list': 'geosearch',
                    'gslimit': 500,
                    'format': 'json'}

    def get_query(self):
        self.lang = self.fields['lang']
        lat = self.fields['location']['lat']
        lon = self.fields['location']['lng']
        if self.fields['location']['radius'] < MAXRADIUS:
            radius = self.fields['location']['radius']
        else:
            radius = MAXRADIUS
        self.wiki = '%s.wikipedia.org' % self.fields['lang']
        self.query_params['gscoord'] = '%s|%s' % (lat, lon)
        self.query_params['gsradius'] = radius
        return super(GeoRevisions, self).get_query()

    def get_data(self):
        api_resp = self.get_query()
        titles = [article['title'] for article in api_resp['query']['geosearch']]
        cache_name = str(titles)
        revisions = get_article_list_revisions(titles)
        return [self.parse_result(rev) for rev in revisions]

    def parse_result(self, rev):
        date = datetime.datetime.strptime(rev['rc_timestamp'], '%Y%m%d%H%M%S')
        date = date.isoformat() + 'Z'
        ret = {'date': date,
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


class UserRevisions(BaseAPIQueryTriggerView):
    """Trigger for revisions from a specified user."""

    default_fields = {'lang': DEFAULT_LANG, 'user': 'ClueBot'}
    query_params = {'action': 'query',
                    'list': 'usercontribs',
                    'ucuser': None,
                    'uclimit': 50,
                    'ucprop': 'ids|timestamp|title|size|comment',
                    'format': 'json'}

    def get_query(self):
        self.wiki = '%s.wikipedia.org' % self.fields['lang']
        self.query_params['ucuser'] = self.fields['user']
        return super(UserRevisions, self).get_query()

    @add_images
    def get_data(self):
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
               'title': contrib['title']}
        ret.update(super(UserRevisions, self).parse_result(ret))
        return ret
