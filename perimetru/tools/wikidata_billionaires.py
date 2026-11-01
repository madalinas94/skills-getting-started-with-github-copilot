#!/usr/bin/env python3
"""Fetch living billionaires (business data only) from Wikidata -> /tmp/perimetru_wd/billionaires.json"""
import json, os, re, time, urllib.request, urllib.parse

URL = "https://query.wikidata.org/sparql"
HEADERS = {"User-Agent": "PerimetruResearch/1.0 (Platinum Close Protection internal tool)",
           "Accept": "application/sparql-results+json"}
OUT = "/tmp/perimetru_wd/billionaires.json"

def sparql(q, tries=4):
    data = urllib.parse.urlencode({"query": q}).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(URL, data=data, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)["results"]["bindings"]
        except Exception as e:
            print("retry", i, e)
            time.sleep(5 * (i + 1))
    raise SystemExit("SPARQL failed")

def v(b, k):
    return b.get(k, {}).get("value")

def qid(u):
    return u.rsplit("/", 1)[-1] if u else None

# Query 1: people with latest net worth statement
Q1 = """
SELECT ?p ?pLabel ?amount ?date ?cc ?article WHERE {
  ?p wdt:P31 wd:Q5 .
  ?p p:P2218 ?st . ?st psv:P2218 ?val .
  ?val wikibase:quantityAmount ?amount ; wikibase:quantityUnit wd:Q4917 .
  FILTER(?amount >= 1000000000)
  OPTIONAL { ?st pq:P585 ?date }
  FILTER NOT EXISTS { ?p wdt:P570 ?d }
  FILTER NOT EXISTS { ?p p:P2218 ?st2 . ?st2 pq:P585 ?date2 . FILTER(!BOUND(?date) || ?date2 > ?date) }
  OPTIONAL { ?p wdt:P27 ?c . ?c wdt:P297 ?cc }
  OPTIONAL { ?article schema:about ?p ; schema:isPartOf <https://en.wikipedia.org/> }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""
# Query 2: companies (employer, owner of, founder)
Q2 = """
SELECT ?p ?co ?coLabel ?site ?ccc WHERE {
  { SELECT DISTINCT ?p WHERE { ?p wdt:P31 wd:Q5 ; p:P2218/psv:P2218 ?val .
      ?val wikibase:quantityAmount ?a ; wikibase:quantityUnit wd:Q4917 . FILTER(?a >= 1000000000)
      FILTER NOT EXISTS { ?p wdt:P570 ?d } } }
  { ?p wdt:P108 ?co } UNION { ?p wdt:P1830 ?co } UNION { ?co wdt:P112 ?p }
  OPTIONAL { ?co wdt:P856 ?site }
  OPTIONAL { ?co wdt:P17 ?c . ?c wdt:P297 ?ccc }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
"""

def main():
    people = {}
    for b in sparql(Q1):
        q = qid(v(b, "p"))
        d = v(b, "date") or ""
        amt = float(v(b, "amount"))
        cur = people.get(q)
        # keep most recent date (tie: highest amount)
        if cur and (cur["date"], cur["amount"]) >= (d[:10], amt):
            if not cur.get("cc") and v(b, "cc"): cur["cc"] = v(b, "cc")
            if not cur.get("wikipedia") and v(b, "article"): cur["wikipedia"] = v(b, "article")
            continue
        people[q] = {"qid": q, "name": v(b, "pLabel"), "cc": v(b, "cc") or (cur or {}).get("cc"),
                     "amount": amt, "date": d[:10],
                     "wikipedia": v(b, "article") or (cur or {}).get("wikipedia"),
                     "companies": []}
    people = {k: p for k, p in people.items() if p["name"] and not re.fullmatch(r"Q\d+", p["name"])}
    print("people", len(people))
    seen = {}
    for b in sparql(Q2):
        q = qid(v(b, "p"))
        if q not in people: continue
        name = v(b, "coLabel")
        if not name or re.fullmatch(r"Q\d+", name): continue
        co = seen.setdefault((q, qid(v(b, "co"))), {"qid": qid(v(b, "co")), "name": name, "website": None, "cc": None})
        co["website"] = co["website"] or v(b, "site")
        co["cc"] = co["cc"] or v(b, "ccc")
    for (q, _), co in seen.items():
        if len(people[q]["companies"]) < 3:
            people[q]["companies"].append(co)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out = sorted(people.values(), key=lambda p: -p["amount"])
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("wrote", len(out), "->", OUT)

if __name__ == "__main__":
    main()
