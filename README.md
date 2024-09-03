# fast-reconcile

_September 2024_ 

This repository was created in 2023 as a quick example of how to develop a [reconciliation service](https://openrefine.org/docs/manual/reconciling) for [OpenRefine](https://openrefine.org/) that allows for resolving raw text strings [OCLC FAST](http://www.oclc.org/research/activities/fast.html?urlm=159754) identifiers. A lot has changed since the with Open Refine, FAST (I think) and Python. I've made minimal changes to update it to run with Python 3.12 but the code should serve as a reference more than a tool that can be used out of the box.

-----


An OpenRefine reconciliation service for [FAST](http://www.oclc.org/research/activities/fast.html?urlm=159754).

>FAST is available as Linked Data, which is an approach to publishing data which enhances the utility of information on the web by making references to persons, places, things, etc. more consistent and linkable across domains.

The service queries the [FAST AutoSuggest API](http://www.oclc.org/developer/documentation/fast-linked-data-api/request-types)
and provides normalized scores across queries for reconciling in Refine.

Run locally as:
~~~~
$ python reconcile.py --debug
~~~~

Michael Stephens wrote a [demo reconciliation service](https://github.com/mikejs/reconcile-demo) that this code is based on.
