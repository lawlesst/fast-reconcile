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
    'university',
    'school',
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
    query_scrubbed = text.normalize(raw_query.lower().replace('the university of', 'university of'))
    #minimum of 4 characters
    for i in xrange(4, len(query_scrubbed) + 1, 2):
        tokens.append(''.join(query_scrubbed[:i]))
    for token in tokens:
        if done is True:
            break
        if token in skip_words:
            continue
        params = {
            'query': token,
            #corporate names only for now
            'queryIndex': 'suggest10',
            'rows': 30,
            'wt': 'json',
            'queryReturn': 'suggestall,idroot,auth',
            'suggest': 'autoSubject',
        }
        try:
            resp = requests.get(api_base_url, params=params)
            print resp.url
            results = resp.json()
        except Exception, e:
            print e
        for position, item in enumerate(results['response']['docs']):
            match = False
            score2 = 0
            name = item.get('auth')
            score = fuzz.ratio(raw_query, name)
            #Try the alternate if the score is low:
            if score < 50:
                alternate = item.get('suggestall')
                try:
                    alt = alternate[0]
                    score2 = fuzz.ratio(raw_query, alt)
                except IndexError:
                    pass
            high_score = max(score, score2)
            pid = item.get('idroot')
            #skip low scores
            if high_score < 50:
                continue
            if text.normalize(name) == text.normalize(raw_query):
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
            if (match is True) or (high_score > 90):
                done = True
                break
    #Sort this list by score
    sorted_out = sorted(out, key=itemgetter('score'), reverse=True)
    #Return top 5 matches
    return sorted_out[:5]


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
