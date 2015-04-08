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

from .utils import select, snake_case
from .views import FeaturedFeedTriggerView, APIQueryTriggerView, DailyAPIQueryTriggerView


app = flask.Flask(__name__)
app.config.from_pyfile('../ifttt.cfg', silent=True)


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
    ret = {'samples': 
              {'triggers': 
                  {'wikipedia_article_revisions': 
                      {'title': 'Coffee'}
                  }
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
        self.query_params['titles'] = self.post_data['triggerFields']['title']
        ret = super(WikipediaArticleRevisions, self).get_query()
        return ret

    def get_results(self):
        api_resp = self.get_query()
        page_id = api_resp['query']['pages'].keys()[0]
        try:
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


class RandomWikipediaArticleOfTheDay(DailyAPIQueryTriggerView):
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


for view_class in (ArticleOfTheDay, 
                   PictureOfTheDay, 
                   WordOfTheDay, 
                   RandomWikipediaArticleOfTheDay,
                   WikipediaArticleRevisions):
    slug = snake_case(view_class.__name__)
    app.add_url_rule('/v1/triggers/%s' % slug,
                     view_func=view_class.as_view(slug))
