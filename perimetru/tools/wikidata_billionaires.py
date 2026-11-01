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

# Query 1: all qualifying net-worth statements (latest picked in Python by P585)
Q1 = """
SELECT ?p ?pLabel ?amount ?date ?cc ?article WHERE {
  ?p wdt:P31 wd:Q5 .
  ?p p:P2218 ?st . ?st psv:P2218 ?val .
  ?val wikibase:quantityAmount ?amount ; wikibase:quantityUnit wd:Q4917 .
  FILTER(?amount >= 1000000000)
  OPTIONAL { ?st pq:P585 ?date }
  FILTER NOT EXISTS { ?p wdt:P570 ?d }
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
# Query 3: sanction markers (P1344 participant in / P1344 value labelled sanction*, or sanctions-list membership)
Q3 = """
SELECT DISTINCT ?p WHERE {
  ?p wdt:P31 wd:Q5 ; p:P2218/psv:P2218 ?val .
  ?val wikibase:quantityAmount ?a ; wikibase:quantityUnit wd:Q4917 . FILTER(?a >= 1000000000)
  { ?p wdt:P1344 ?e } UNION { ?p wdt:P463 ?e } UNION { ?p wdt:P1535 ?e }
  ?e rdfs:label ?l . FILTER(LANG(?l)="en" && CONTAINS(LCASE(?l),"sanction"))
}
"""
HIGH_RISK = set("IQ LY MZ NG CD AF YE SD SS SO ML SY HT VE RU BY KP IR".split())

def main():
    stats = {"old_or_undated": 0, "sanctioned": 0, "unresolved_company": 0, "high_risk": 0}
    best = {}
    for b in sparql(Q1):
        q = qid(v(b, "p")); d = (v(b, "date") or "")[:10]; amt = float(v(b, "amount"))
        cur = best.get(q)
        if cur is None:
            best[q] = {"qid": q, "name": v(b, "pLabel"), "cc": v(b, "cc"), "amount": amt, "date": d,
                       "wikipedia": v(b, "article"), "companies": []}
            continue
        if not cur["cc"]: cur["cc"] = v(b, "cc")
        if not cur["wikipedia"]: cur["wikipedia"] = v(b, "article")
        if (d, amt) > (cur["date"], cur["amount"]):
            cur["date"], cur["amount"] = d, amt
    people = {k: p for k, p in best.items() if p["name"] and not re.fullmatch(r"Q\d+", p["name"])}
    print("people raw", len(people), flush=True)
    for k in [k for k, p in people.items() if p["date"] < "2023-01-01"]:
        del people[k]; stats["old_or_undated"] += 1
    sanc = {qid(v(b, "p")) for b in sparql(Q3)}
    for k in [k for k in people if k in sanc]:
        del people[k]; stats["sanctioned"] += 1
    seen = {}; unresolved = set()
    for b in sparql(Q2):
        q = qid(v(b, "p"))
        if q not in people: continue
        name = v(b, "coLabel")
        if not name or re.fullmatch(r"Q\d+", name):
            unresolved.add(q); continue
        co = seen.setdefault((q, qid(v(b, "co"))), {"qid": qid(v(b, "co")), "name": name, "website": None, "cc": None})
        co["website"] = co["website"] or v(b, "site")
        co["cc"] = co["cc"] or v(b, "ccc")
    for (q, _), co in seen.items():
        if len(people[q]["companies"]) < 3:
            people[q]["companies"].append(co)
    for q in unresolved:
        if q in people: del people[q]; stats["unresolved_company"] += 1
    for q in list(people):
        p = people[q]
        if (p["cc"] in HIGH_RISK) or any(c["cc"] in HIGH_RISK for c in p["companies"]):
            del people[q]; stats["high_risk"] += 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out = sorted(people.values(), key=lambda p: -p["amount"])
    json.dump({"stats": stats, "people": out}, open(OUT, "w"), ensure_ascii=False, indent=1)
    print("wrote", len(out), stats, "->", OUT, flush=True)

if __name__ == "__main__":
    main()
