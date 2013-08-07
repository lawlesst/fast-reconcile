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

app = Flask(__name__)

# Basic service metadata. There are a number of other documented options
# but this is all we need for a simple service.
metadata = {
    "name": "JournalTOC Reconciliation Service",
    "defaultTypes": [{"id": "http://purl.org/ontology/bibo/Periodical", "name": "bibo:Periodical"}],
}

api_base_url = 'http://www.journaltocs.ac.uk/api/journals/{0}?output=journals&user={1}'


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
    Hit the JournalTOC api for journal names.
    """
    out = []
    try:
        query = urllib.quote(raw_query)
    except Exception:
        return []
    api_url = api_base_url.format(query, TOC_USER)
    print api_url
    api_results = feedparser.parse(api_url)
    for position, item in enumerate(api_results['entries']):
        #Check for no results
        #ToDo - improve this.
        if position == 0:
            if item.get('summary_detail', {}).get('value').lower().startswith('0 hits'):
                return out
        #Result spec of the list comprehension
        title = item.get('title', 'No title found')
        issn = item.get('prism_issn')
        #Skip results without an ISSN for now.
        if issn is None:
            continue
        #Give the resource a crossref dummy issn uri for now.
        pid = 'http://id.crossref.org/issn/' + issn
        #import ipdb; ipdb.set_trace()
        if title.lower() == raw_query.lower():
            match = True
        else:
            match = False
        #Construct a score using FuzzyWuzzy's token set ratio.
        #https://github.com/seatgeek/fuzzywuzzy
        score = fuzz.token_sort_ratio(raw_query, title)
        out.append({
            "id": pid,
            "name": title,
            "score": score,
            "match": match,
            "type": [
                {
                    "id": "http://purl.org/ontology/bibo/Periodical",
                    "name": "bibo:Periodical",
                }
            ]
        })
    #Sort this list by score
    sorted_out = sorted(out, key=itemgetter('score'), reverse=True)
    return sorted_out


@app.route("/reconcile", methods=['POST', 'GET'])
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
