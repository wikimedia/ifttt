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
import flask
import lxml.html
import json
import socket

from .utils import select, snake_case
from .views import (FeaturedFeedTriggerView,
                    APIQueryTriggerView,
                    DailyAPIQueryTriggerView)


app = flask.Flask(__name__)
app.config.from_pyfile('../ifttt.cfg', silent=True)


@app.errorhandler(400)
def unauthorized(e):
    """There was something wrong with incoming data from IFTTT. """
    error = {'message': 'missing required trigger field'}
    return flask.jsonify(errors=[error]), 400


@app.errorhandler(401)
def unauthorized(e):
    """Issue an HTTP 401 Unauthorized response with a JSON body."""
    error = {'message': 'Unauthorized'}
    return flask.jsonify(errors=[error]), 401


@app.after_request
def force_content_type(response):
    """RFC 4627 stipulates that 'application/json' takes no charset parameter,
    but IFTTT expects one anyway. We have to twist Flask's arm to get it to
    break the spec."""
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


@app.before_request
def validate_channel_key():
    """Verify that the 'IFTTT-Channel-Key' header is present on each request
    and that its value matches the channel key we got from IFTTT. If a request
    fails this check, we reject it with HTTP 401."""
    channel_key = flask.request.headers.get('IFTTT-Channel-Key')
    if not app.debug and channel_key != app.config.get('CHANNEL_KEY'):
        flask.abort(401)


@app.route('/v1/test/setup', methods=['POST'])
def test_setup():
    """Required by the IFTTT endpoint test suite."""
    ret = {
        'samples': {
            'triggers': {
                'wikipedia_article_revisions': {'title': 'Coffee'},
                'wikipedia_user_revisions': {'user': 'Slaporte'},
            },
            'triggerFieldValidations': {
                'wikipedia_article_revisions': {
                    'title': {
                        'valid': 'Coffee',
                        'invalid': 'ThisPageDoesNotExist'
                    },
                },
                'wikipedia_user_revisions': {
                    'user': {
                        'valid': 'ClueBot',
                        'invalid': 'ThisUserDoesNotExist'
                    },
                }
            },
        }
    }
    return flask.jsonify(data=ret)


@app.route('/v1/status')
def status():
    """Return HTTP 200 and an empty body, as required by the IFTTT spec."""
    return ''


class PictureOfTheDay(FeaturedFeedTriggerView):
    """Trigger view for Wikimedia Commons Picture of the Day"""

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
    """Trigger view for English Wikipedia's Today's Featured Article."""

    feed = 'featured'
    wiki = 'en.wikipedia.org'

    def parse_entry(self, entry):
        """Scrape each AotD entry for its URL and title."""
        item = super(ArticleOfTheDay, self).parse_entry(entry)
        summary = lxml.html.fromstring(entry.summary)
        read_more = select(summary, 'p:first-of-type > a:last-of-type')
        item['url'] = read_more.get('href')
        item['title'] = read_more.get('title')
        return item


class WordOfTheDay(FeaturedFeedTriggerView):
    """Trigger view for English Wiktionary's Word of the Day."""

    feed = 'wotd'
    wiki = 'en.wiktionary.org'

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


class WikipediaArticleRevisions(APIQueryTriggerView):

    wiki = 'en.wikipedia.org'
    query_params = {'action': 'query',
                    'prop': 'revisions',
                    'titles': None,
                    'rvlimit': 50,
                    'rvprop': 'ids|timestamp|user|size|comment',
                    'format': 'json'}

    def get_query(self):
        trigger_fields = self.post_data.get('triggerFields', {})
        self.query_params['titles'] = trigger_fields.get('title')
        if not self.query_params['titles']:
            flask.abort(400)
        ret = super(WikipediaArticleRevisions, self).get_query()
        return ret

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
               'title': self.post_data['triggerFields']['title']}
        ret.update(super(WikipediaArticleRevisions, self).parse_result(ret))
        return ret


class WikipediaUserRevisions(APIQueryTriggerView):

    wiki = 'en.wikipedia.org'
    query_params = {'action': 'query',
                    'list': 'usercontribs',
                    'ucuser': None,
                    'uclimit': 50,
                    'ucprop': 'ids|timestamp|title|size|comment',
                    'format': 'json'}

    def get_query(self):
        trigger_fields = self.post_data.get('triggerFields', {})
        self.query_params['ucuser'] = trigger_fields.get('user')
        if not self.query_params['ucuser']:
            flask.abort(400)
        ret = super(WikipediaUserRevisions, self).get_query()
        return ret

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
               'user': self.post_data['triggerFields']['user'],
               'size': contrib['size'],
               'comment': contrib['comment'],
               'title': contrib['user']}
        ret.update(super(WikipediaUserRevisions, self).parse_result(ret))
        return ret


class RandomWikipediaArticleOfTheDay(DailyAPIQueryTriggerView):
    """This trigger doesn't exactly fit IFTTT's model, so I'm leaving it
       inactive for now."""

    wiki = 'en.wikipedia.org'
    query_params = {'action': 'query',
                    'list': 'random',
                    'rnnamespace': 0,
                    'rnlimit': 1,
                    'format': 'json'}

    def parse_query(self):
        rand_query = super(RandomWikipediaArticleOfTheDay, self).parse_query()
        page_title = rand_query['query']['random'][0]['title']
        url = 'https://%s/wiki/%s' % (self.wiki, page_title.replace(' ', '_'))
        rand_query['article_title'] = page_title
        rand_query['article_url'] = url
        rand_query.pop('query', None)
        rand_query.pop('published_parsed', None)
        rand_query.pop('warnings', None)
        return rand_query


class ValidateArticleTitle(APIQueryTriggerView):

    url_pattern = 'wikipedia_article_revisions/fields/title/validate'
    wiki = 'en.wikipedia.org'
    query_params = {'action': 'query',
                    'prop': 'info',
                    'titles': None,
                    'format': 'json'}

    def get_query(self):
        self.query_params['titles'] = self.post_data.get('value')
        if not self.query_params['titles']:
            flask.abort(400)
        ret = super(ValidateArticleTitle, self).get_query()
        return ret

    def check_page(self):
        api_resp = self.get_query()
        page_ids = api_resp['query']['pages'].keys()
        if int(page_ids[0]) > 0:
            return True
        return False

    def post(self):
        params = flask.request.get_json(force=True, silent=True) or {}
        self.post_data = json.loads(flask.request.data)
        exists = self.check_page()
        title = self.query_params['titles']
        ret = {
            'valid': exists
        }
        if not exists:
            ret['message'] = ('A Wikipedia article on %s does not (yet)'
                              ' exist (go write it!)' % title)
        return flask.jsonify(data=ret)


class ValidateUser(APIQueryTriggerView):

    url_pattern = 'wikipedia_user_revisions/fields/user/validate'
    wiki = 'en.wikipedia.org'
    query_params = {'action': 'query',
                    'list': 'users',
                    'ususers': None,
                    'format': 'json'}

    def get_query(self):
        self.query_params['ususers'] = self.post_data.get('value')
        if not self.query_params['ususers']:
            flask.abort(400)
        ret = super(ValidateUser, self).get_query()
        return ret

    def check_user(self):
        api_resp = self.get_query()
        page_ids = api_resp['query']['users']
        if page_ids[0].get('userid'):
            return True
        # The MW API doesn't validate unregistered users,
        # so the next few lines allow any valid IP address
        username = self.query_params['ususers']
        try:
            socket.inet_aton(username)
            return True
        except socket.error:
            pass
        try:
            socket.inet_pton(socket.AF_INET6, username)
            return True
        except socket.error:
            pass
        return False

    def post(self):
        params = flask.request.get_json(force=True, silent=True) or {}
        self.post_data = json.loads(flask.request.data)
        exists = self.check_user()
        title = self.query_params['ususers']
        ret = {
            'valid': exists
        }
        if not exists:
            ret['message'] = ('There is no Wikipedian named %s'
                              % title)
        return flask.jsonify(data=ret)


for view_class in (ArticleOfTheDay,
                   PictureOfTheDay,
                   WordOfTheDay,
                   RandomWikipediaArticleOfTheDay,
                   WikipediaArticleRevisions,
                   WikipediaUserRevisions,
                   ValidateArticleTitle,
                   ValidateUser):
    slug = getattr(view_class, 'url_pattern', None)
    if not slug:
        slug = snake_case(view_class.__name__)
    app.add_url_rule('/v1/triggers/%s' % slug,
                     view_func=view_class.as_view(slug))
