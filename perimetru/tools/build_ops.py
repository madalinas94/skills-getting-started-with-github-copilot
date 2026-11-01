#!/usr/bin/env python3
"""Build db_write op files (50 ops each) from /tmp/perimetru_wd/billionaires.json."""
import json, re, unicodedata, glob, os
TODAY = "2026-11-01"
SRC = "/tmp/perimetru_wd/billionaires.json"
OUT = "/tmp/perimetru_wd/ops"
EXISTING_UH = {  # existing uhnwi docs matched by normalised name: id -> (version, existing sources)
}
# existing orgs matched by normalised name or website (id)
EXISTING_ORG = {
 "ahs properties":"org-ahs-properties-ae","airbnb":"org-airbnb-us","apple":"org-apple-us",
 "berkshire hathaway":"org-berkshire-hathaway-us","binance":"org-binance-ae","broadcom":"org-broadcom-us",
 "carlyle group":"org-carlyle-us","cisco":"org-cisco-us","cloudflare":"org-cloudflare-us",
 "coinbase":"org-coinbase-us","coreweave":"org-coreweave-us","crowdstrike":"org-crowdstrike-us",
 "gemini":"org-gemini-us","goldman sachs":"org-goldman-sachs-us","ibm":"org-ibm-us",
 "microsoft":"org-microsoft-us","netflix":"org-netflix-us","nvidia":"org-nvidia-us",
 "oracle":"org-oracle-us","palantir technologies":"org-palantir-us","procter gamble":"org-procter-gamble-us",
 "robinhood":"org-robinhood-us","rocket companies":"org-rocket-companies-us","salesforce":"org-salesforce-us",
 "strategy":"org-strategy-inc-us","home depot":"org-home-depot-us","tpg":"org-tpg-us","zoom":"org-zoom-us",
}
BAD = re.compile(r"universit|institut|foundation|fund\b|academy|museum|campaign|school|college|pledge|philanthrop|^the broad|^time$|bell labs|mckinsey|drexel|^skat$|dharavi|benefits supervisor|^eclipse$|^amadea$|bain & company|laboratories|hospital|church|endowment|center for|association of|alliance for|national entrepreneurship|winery|steakhouse|ranch", re.I)

def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"&", " ", s)
    s = re.sub(r"\b(inc|corp|corporation|plc|ltd|limited|llc|l\.p|lp|sa|ag|gmbh|group|communications|holdings|the)\b\.?", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")

# existing uhnwi (normalised name) -> (id, version, sources) for the matches found in the collection
EXIST = {
 "abbas sajwani": ("uh-abbas-sajwani", 1, [
   {"label":"Forbes Middle East: Richest Residents in the UAE 2026","url":"https://www.forbesmiddleeast.com/lists/richest-residents-in-the-uae-2026/"},
   {"label":"Fonte cifră","url":"https://countly.net/richest-people-in-united-arab-emirates-2026-billionaires-net-worth"}]),
 "changpeng zhao": ("uh-changpeng-zhao", 1, [
   {"label":"Forbes Middle East: Richest Residents in the UAE 2026","url":"https://www.forbesmiddleeast.com/lists/richest-residents-in-the-uae-2026/"},
   {"label":"Fonte cifră","url":"https://www.forbesmiddleeast.com/lists/richest-residents-in-the-uae-2026/"}]),
}

def main():
    data = json.load(open(SRC)); P = data["people"]
    st = {"no_cc":0,"bad_date":0,"dup_name":0,"new_uh":0,"upd_uh":0,"new_org":0,"linked_org":0}
    orgs = {}; uh_ops = []; seen = set(); linked = set()
    for p in P:
        if not p["cc"]: st["no_cc"] += 1; continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p["date"] or ""): st["bad_date"] += 1; continue
        nn = norm(p["name"])
        if nn in seen: st["dup_name"] += 1; continue
        seen.add(nn)
        wd = "https://www.wikidata.org/wiki/" + p["qid"]
        srcs = [{"label": "Wikidata", "url": wd}]
        if p.get("wikipedia"): srcs.append({"label": "Wikipedia", "url": p["wikipedia"]})
        if nn in EXIST:
            i, ver, old = EXIST[nn]
            uh_ops.append({"op":"update","path":"uhnwi/"+i,"ifVersion":ver,
                           "data":{"wikidataId":p["qid"],"sources":old+srcs}})
            st["upd_uh"] += 1; continue
        routes = []; names = []
        for c in p["companies"]:
            if BAD.search(c["name"]) or not c["cc"]: continue
            key = norm(c["name"])
            if key in EXISTING_ORG: oid = EXISTING_ORG[key]; linked.add(oid)
            else:
                oid = f"org-{slug(c['name'])}-{c['cc'].lower()}"
                if oid not in orgs:
                    orgs[oid] = {"op":"set","path":"orgs/"+oid,"data":{
                        "type":"holding","name":c["name"],"cc":c["cc"],"website":c["website"] or "",
                        "address":"","phone":"","email":"",
                        "why":"Companie asociată unui miliardar din lista publică Wikidata; rută oficială de business (birou de presă / relații corporative).",
                        "score":60,"sources":[{"label":"Wikidata","url":"https://www.wikidata.org/wiki/"+c["qid"]}],
                        "status":"nou","dnc":False,"verified":TODAY}}
            if oid not in routes: routes.append(oid); names.append(c["name"])
        doc = {"name":p["name"],"cc":p["cc"],"netWorthBn":round(p["amount"]/1e9,1),
               "netWorthSource":{"label":f"Wikidata (P2218), {p['date']}","url":wd,"date":p["date"]},
               "wealthSource":", ".join(names),"company":names[0] if names else "","routes":routes,
               "wikidataId":p["qid"],"sources":srcs,"verified":TODAY,"by":"wikidata-import",
               "status":"de verificat","confidence":"wikidata"}
        uh_ops.append({"op":"set","path":"uhnwi/uh-"+slug(p["name"]),"data":doc}); st["new_uh"] += 1
    # unique uhnwi ids
    ids = set(); final = []
    for o in uh_ops:
        if o["path"] in ids: continue
        ids.add(o["path"]); final.append(o)
    st["new_uh"] = sum(1 for o in final if o["op"]=="set")
    st["new_org"] = len(orgs); st["linked_org"] = len(linked)
    ops = list(orgs.values()) + final
    for f in glob.glob(OUT + "/*.json"): os.remove(f)
    for n in range(0, len(ops), 50):
        json.dump(ops[n:n+50], open(f"{OUT}/batch_{n//50+1:02d}.json","w"), ensure_ascii=False, separators=(",",":"))
    json.dump(st, open(OUT + "/stats.json","w"))
    print(st, len(ops), "ops in", (len(ops)+49)//50, "files")
main()
