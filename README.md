An OpenRefine reconciliation service for [FAST](http://www.oclc.org/research/activities/fast.html?urlm=159754).

>FAST is available as Linked Data, which is an approach to publishing data which enhances the utility of information on the web by making references to persons, places, things, etc. more consistent and linkable across domains.

The service queries the [FAST AutoSuggest API](http://www.oclc.org/developer/documentation/fast-linked-data-api/request-types) and provides normalized scores across queries for recoiling in Refine.

 * as of 8/13/13 only supports Corporate Name queries.  This will be expanded soon.

Run locally as:
~~~~
$ python reconcile.py python reconcile.py --debug
~~~~

Michael Stephens wrote a [demo reconcilliation service](https://github.com/mikejs/reconcile-demo) that this code is based on.
