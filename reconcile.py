"""
A Google Refine reconcillation servce for the api provided by
the JournalTOCs project.

See API documentation:
http://www.journaltocs.ac.uk/api_help.php?subAction=journals

An example reconciliation service API for Google Refine 2.0.

See http://code.google.com/p/google-refine/wiki/ReconciliationServiceApi.
"""

from flask import Flask
from flask import request
from flask import jsonify

import json
from operator import itemgetter
import urllib

import feedparser
#For scoring results
from fuzzywuzzy import fuzz
import requests
import requests_cache
requests_cache.install_cache('fast_corporate_cache')

import text

app = Flask(__name__)

# Basic service metadata. There are a number of other documented options
# but this is all we need for a simple service.
metadata = {
    "name": "Fast Corporate Name Reconciliation Service",
    "defaultTypes": [{"id": "http://www.w3.org/2004/02/skos/core#", "name": "skos:Concept"}],
}

api_base_url = 'http://fast.oclc.org/searchfast/fastsuggest'

fast_uri_base = 'http://id.worldcat.org/fast/{0}'
def make_uri(fast_id):
    fid = fast_id.lstrip('fst').lstrip('0')
    fast_uri = fast_uri_base.format(fid)
    return fast_uri

def jsonpify(obj):
    """
    Helper to support JSONP
    """
    try:
        callback = request.args['callback']
        response = app.make_response("%s(%s)" % (callback, json.dumps(obj)))
        response.mimetype = "text/javascript"
        return response
    except KeyError:
        return jsonify(obj)

#skip these terms for lookup
skip_words = [
    'the university of',
    'univ',
    'univer',
    'universi',
    'university'
    'of',
    'the'
]


def search(raw_query):
    """
    Hit the FAST API for names.
    """
    out = []
    #Hit the suggest api for each token
    #tokens = [text.normalize(t) for t in text.tokenize(raw_query)]
    tokens = []
    done = False
    query_scrubbed = text.normalize(raw_query).replace('the university of', 'university of').strip()
    #minimum of 4 characters
    for i in xrange(4, len(query_scrubbed) + 2, 2):
        tokens.append(''.join(query_scrubbed[:i]))
    for token in [query_scrubbed]:
        if done is True:
            break
        if token in skip_words:
            continue
        try:
            #FAST api requires spaces to be encoded as %20 rather than +
            url = api_base_url + '?query=' + urllib.quote(token) + '&rows=30&queryReturn=suggestall%2Cidroot%2Cauth%2cscore&suggest=autoSubject&queryIndex=suggest10&wt=json'
            resp = requests.get(url)
            results = resp.json()
        except Exception, e:
            print e
        for position, item in enumerate(results['response']['docs']):
            match = False
            score2 = 0
            name = item.get('auth')
            alternate = item.get('suggestall')
            score = item.get('score')
            if (len(alternate) > 0):
                alt = alternate[0]
            else:
                alt = ''
            pid = item.get('idroot')
            normal_query = text.normalize(raw_query)
            if normal_query == text.normalize(name):
                match = True
            elif normal_query == text.normalize(alt):
                match = True
            resource = {
                "id": make_uri(pid),
                "name": name,
                "score": score,
                "match": match,
                "type": [
                    {
                        "id": "http://www.w3.org/2004/02/skos/core#",
                        "name": "skos:Concept",
                    }
                ]
            }
            #The FAST service returns many duplicates.
            if resource not in out:
                out.append(resource)
            #Break out of the query loop if we've found a good candidate
            if (match is True):
                done = True
                break
    #Sort this list by score
    sorted_out = sorted(out, key=itemgetter('score'), reverse=True)
    return sorted_out


@app.route("/fast-corporate/reconcile", methods=['POST', 'GET'])
def reconcile():
    #Look first for form-param requests.
    query = request.form.get('query')
    if query is None:
        #Then normal get param.s
        query = request.args.get('query')
    if query:
        # If the 'query' param starts with a "{" then it is a JSON object
        # with the search string as the 'query' member. Otherwise,
        # the 'query' param is the search string itself.
        if query.startswith("{"):
            query = json.loads(query)['query']
        results = search(query)
        return jsonpify({"result": results})
    # If a 'queries' parameter is supplied then it is a dictionary
    # of (key, query) pairs representing a batch of queries. We
    # should return a dictionary of (key, results) pairs.
    queries = request.form.get('queries')
    if queries:
        queries = json.loads(queries)
        results = {}
        for (key, query) in queries.items():
            results[key] = {"result": search(query['query'])}
        return jsonpify(results)

    # If neither a 'query' nor 'queries' parameter is supplied then
    # we should return the service metadata.
    return jsonpify(metadata)

if __name__ == '__main__':
    from optparse import OptionParser
    oparser = OptionParser()
    oparser.add_option('-d', '--debug', action='store_true', default=False)
    oparser.add_option('-u', '--user', dest='api_user', default=False)
    opts, args = oparser.parse_args()
    if opts.api_user is False:
        raise Exception("No API user provided.\
                        Pass as --user.\
                        Typically an email address.")
    else:
        TOC_USER = opts.api_user
    app.debug = opts.debug
    app.run(host='0.0.0.0')
