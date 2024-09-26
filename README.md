
An OpenRefine reconciliation service for [FAST](https://www.oclc.org/research/areas/data-science/fast.html) that works with **Python 3**.

>FAST is available as Linked Data, which is an approach to publishing data which enhances the utility of information on the web by making references to persons, places, things, etc. more consistent and linkable across domains.

The service queries the [FAST AutoSuggest API](https://www.oclc.org/developer/api/oclc-apis/fast-api/assign-fast.en.html)
and provides normalized scores across queries for reconciling in Refine.

Run locally as:

```python
python reconcile.py --debug
```

The URL (endpoint) of the reconciliation service is <http://127.0.0.1:5000/reconcile>

Michael Stephens wrote a [demo reconcilliation service](https://github.com/mikejs/reconcile-demo) that this code is based on.
