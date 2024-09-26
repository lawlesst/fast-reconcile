"""
An OpenRefine reconciliation service for the API provided by OCLC for FAST.
This module provides a Flask web service that interfaces with the FAST API to 
perform reconciliation of terms. It supports both single and batch queries, 
returning results in a format compatible with OpenRefine's reconciliation 
service.
Classes:
    None
Functions:
    make_uri(fast_id)
        Prepare a FAST URL from the ID returned by the API.
    jsonpify(obj)
        Helper to support JSONP responses.
    search(raw_query, query_type='/fast/all')
        Perform a search against the FAST API for the given query and query type.
    reconcile()
        Handle reconciliation requests from OpenRefine, supporting both single 
        and batch queries.
Variables:
    app (Flask): The Flask application instance.
    api_base_url (str): Base URL for the FAST API.
    fast_uri_base (str): Base URL for constructing FAST URIs.
    default_query (dict): Default query type for the reconciliation service.
    refine_to_fast (list): List of mappings from OpenRefine query types to FAST 
        query indexes.
    query_types (list): List of query types without indexes for service metadata.
    metadata (dict): Basic service metadata for the reconciliation service.

See API documentation:
https://www.oclc.org/developer/api/oclc-apis/fast-api/assign-fast.en.html

This code is adapted from Michael Stephens:
https://github.com/mikejs/reconcile-demo
"""

from flask import Flask
from flask import request
from flask import jsonify

import json
from operator import itemgetter
import urllib.request, urllib.parse, urllib.error

#For scoring results
from thefuzz import fuzz
import requests
import requests_cache

#Create the Flask app
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

#Map the FAST query indexes to service types
default_query = {
    "id": "/fast/all",
    "name": "All FAST terms",
    "index": "suggestall"
}

refine_to_fast = [
    {
        "id": "/fast/geographic",
        "name": "Geographic Name",
        "index": "suggest51"
    },
    {
        "id": "/fast/corporate-name",
        "name": "Corporate Name",
        "index": "suggest10"
    },
    {
        "id": "/fast/personal-name",
        "name": "Personal Name",
        "index": "suggest00"
    },
    {
        "id": "/fast/event",
        "name": "Event",
        "index": "suggest11"
    },
    {
        "id": "/fast/title",
        "name": "Uniform Title",
        "index": "suggest30"
    },
    {
        "id": "/fast/topical",
        "name": "Topical",
        "index": "suggest50"
    },
    {
        "id": "/fast/form",
        "name": "Form",
        "index": "suggest55"
    }
]
refine_to_fast.append(default_query)


#Make a copy of the FAST mappings.
#Minus the index for
query_types = [{'id': item['id'], 'name': item['name']} for item in refine_to_fast]

# Basic service metadata. There are a number of other documented options
# but this is all we need for a simple service.
metadata = {
    "name": "Fast Reconciliation Service",
    "defaultTypes": query_types,
    "view": {
        "url": "{{id}}"
    }
}


def make_uri(fast_id):
    """
    Prepare a FAST url from the ID returned by the API.
    """
    if isinstance(fast_id, list):
    # Handle the case where fast_id is a list
        fast_id = fast_id[0]  # Example: take the first element of the list
    if not isinstance(fast_id, str):
        raise ValueError("fast_id must be a string or a list containing a string")
    
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


def search(raw_query, query_type='/fast/all'):
    """
    Hit the FAST API for names.
    """
    out = []
    unique_fast_ids = []
    query = text.normalize(raw_query).replace('the university of', 'university of').strip()
    query_type_meta = [i for i in refine_to_fast if i['id'] == query_type]
    if query_type_meta == []:
        query_type_meta = default_query
    query_index = query_type_meta[0]['index']
    try:
        #FAST api requires spaces to be encoded as %20 rather than +
        url = api_base_url + '?query=' + urllib.parse.quote(query)
        url += '&rows=20&queryReturn=suggestall%2Cidroot%2Cauth%2Cscore&suggest=autoSubject'
        url += '&queryIndex=' + query_index + '&wt=json'
        app.logger.debug("FAST API url is " + url)
        resp = requests.get(url)
        results = resp.json()
    except Exception as e:
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
            "type": query_type_meta
        }
        out.append(resource)
    #Sort this list by score
    sorted_out = sorted(out, key=itemgetter('score'), reverse=True)
    #Refine only will handle top three matches.
    return sorted_out[:6]


@app.route("/reconcile", methods=['POST', 'GET'])
def reconcile():
    #Single queries have been deprecated.  This can be removed.
    #Look first for form-param requests.
    query = request.form.get('query')
    if query is None:
        #Then normal get param.s
        query = request.args.get('query')
        query_type = request.args.get('type', '/fast/all')
    if query:
        # If the 'query' param starts with a "{" then it is a JSON object
        # with the search string as the 'query' member. Otherwise,
        # the 'query' param is the search string itself.
        if query.startswith("{"):
            query = json.loads(query)['query']
        results = search(query, query_type=query_type)
        return jsonpify({"result": results})
    # If a 'queries' parameter is supplied then it is a dictionary
    # of (key, query) pairs representing a batch of queries. We
    # should return a dictionary of (key, results) pairs.
    queries = request.form.get('queries')
    if queries:
        queries = json.loads(queries)
        results = {}
        for (key, query) in list(queries.items()):
            qtype = query.get('type')
            #If no type is specified this is likely to be the initial query
            #so lets return the service metadata so users can choose what
            #FAST index to use.
            if qtype is None:
                return jsonpify(metadata)
            data = search(query['query'], query_type=qtype)
            results[key] = {"result": data}
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
    app.run(host='127.0.0.1')
