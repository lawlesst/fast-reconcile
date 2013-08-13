"""
An OpenRefine reconciliation service for the API provided by
OCLC for FAST.

See API documentation:
http://www.oclc.org/developer/documentation/fast-linked-data-api/request-types

This code is adapted from Michael Stephens:
https://github.com/mikejs/reconcile-demo
"""

from flask import Flask
from flask import request
from flask import jsonify

import json
from operator import itemgetter
import urllib

#For scoring results
from fuzzywuzzy import fuzz
import requests

app = Flask(__name__)

#some config
api_base_url = 'http://fast.oclc.org/searchfast/fastsuggest'
#For constructing links to FAST.
fast_uri_base = 'http://id.worldcat.org/fast/{0}'

#If it's installed, use the requests_cache library to
#cache calls to the FAST API.
try:
    import requests_cache
    requests_cache.install_cache('fast_cache')
except ImportError:
    app.logger.debug("No request cache found.")
    pass

#Helper text processing
import text

# Basic service metadata. There are a number of other documented options
# but this is all we need for a simple service.
metadata = {
    "name": "Fast Corporate Name Reconciliation Service",
    #ToDo add support for all types.
    "defaultTypes": [
        {"id": "/fast/corporate-name", "name": "Corporate Name"}
    ],
}


def make_uri(fast_id):
    """
    Prepare a FAST url from the ID returned by the API.
    """
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


def search(raw_query):
    """
    Hit the FAST API for names.
    """
    out = []
    unique_fast_ids = []
    query = text.normalize(raw_query).replace('the university of', 'university of').strip()
    try:
        #FAST api requires spaces to be encoded as %20 rather than +
        url = api_base_url + '?query=' + urllib.quote(query) + '&rows=30&queryReturn=suggestall%2Cidroot%2Cauth%2cscore&suggest=autoSubject&queryIndex=suggest10&wt=json'
        resp = requests.get(url)
        results = resp.json()
    except Exception, e:
        app.logger.warning(e)
        return out
    for position, item in enumerate(results['response']['docs']):
        match = False
        name = item.get('auth')
        alternate = item.get('suggestall')
        if (len(alternate) > 0):
            alt = alternate[0]
        else:
            alt = ''
        fid = item.get('idroot')
        fast_uri = make_uri(fid)
        #The FAST service returns many duplicates.  Avoid returning many of the
        #same result
        if fid in unique_fast_ids:
            continue
        else:
            unique_fast_ids.append(fid)
        score_1 = fuzz.token_sort_ratio(query, name)
        score_2 = fuzz.token_sort_ratio(query, alt)
        #Return a maximum score
        score = max(score_1, score_2)
        if query == text.normalize(name):
            match = True
        elif query == text.normalize(alt):
            match = True
        resource = {
            "id": fast_uri,
            "name": name,
            "score": score,
            "match": match,
            "type": [
                {
                    "id": "/fast/corporate-name",
                    "name": "Corporate Name",
                }
            ]
        }
        out.append(resource)
    #Sort this list by score
    sorted_out = sorted(out, key=itemgetter('score'), reverse=True)
    #Refine only will handle top three matches.
    return sorted_out[:2]


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
    opts, args = oparser.parse_args()
    app.debug = opts.debug
    app.run(host='0.0.0.0')
