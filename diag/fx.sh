set -e
python scripts/fetch.py > fetch.log 2>&1 || { tail -50 fetch.log; exit 1; }
grep -i "pre/post\|prenešeno\|AAPL\|SPY \|NVDA\|Brez podatkov\|manjkajo\|!" fetch.log | cut -c1-300 | head -30
python - <<'P'
import json, datetime as dt, zoneinfo
ny=zoneinfo.ZoneInfo("America/New_York")
m=json.load(open("data/meta.json"))
for s in ["AAPL","SPY","NVDA"]:
    print(s, json.dumps(m["symbols"].get(s))[:400])
    for iv in ["15m","1h","1d"]:
        d=json.load(open(f"data/{s}_{iv}.json")); ts=d["t"]
        mins=[dt.datetime.fromtimestamp(t/1000,ny) for t in ts]; pre=sum(1 for x in mins if x.hour*60+x.minute<570); post=sum(1 for x in mins if x.hour*60+x.minute>=960)
        print(" ", iv, len(ts), "pre", pre, "post", post, "zadnja", mins[-1], d["c"][-1])
P
echo "B64START"; tar czf - data/AAPL_15m.json data/AAPL_1h.json data/AAPL_1d.json data/meta.json | base64 -w0; echo; echo "B64END"
