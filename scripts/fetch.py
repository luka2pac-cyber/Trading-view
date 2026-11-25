"""Pobere OHLCV z Yahoo Finance za watchlist.json in zapiše data/<id>_<interval>.json + data/meta.json."""
import json, math, os, re, time
import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data")
os.makedirs(OUT, exist_ok=True)
INTERVALS = {"1d": "10y", "1h": "730d", "15m": "60d"}


def rnd(x):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return float(f"{x:.6g}")


def fname(sid):
    return re.sub(r"[^A-Za-z0-9._-]", "_", sid)


def download(tickers, interval):
    """Vrne {ticker: DataFrame} (samo neprazne)."""
    out = {}
    for chunk in [tickers[i:i + 25] for i in range(0, len(tickers), 25)]:
        for attempt in range(3):
            try:
                df = yf.download(chunk, period=INTERVALS[interval], interval=interval, group_by="ticker",
                                 auto_adjust=False, actions=False, progress=False, threads=False)
                break
            except Exception as e:  # noqa
                print(f"  ! download {interval} poskus {attempt + 1}: {e}")
                time.sleep(5 * (attempt + 1))
        else:
            continue
        if df is None or df.empty:
            continue
        lvl0 = set(df.columns.get_level_values(0)) if isinstance(df.columns, pd.MultiIndex) else set()
        for t in chunk:
            d = df[t] if t in lvl0 else (df if not lvl0 and len(chunk) == 1 else None)
            if d is None:
                continue
            d = d.dropna(subset=["Open", "High", "Low", "Close"])
            if not d.empty:
                out[t] = d
        time.sleep(1)
    return out


def to_json(df):
    vol = df["Volume"] if "Volume" in df else pd.Series(0, index=df.index)
    return {
        "t": [int(pd.Timestamp(ts).timestamp() * 1000) for ts in df.index],
        "o": [rnd(v) for v in df["Open"]], "h": [rnd(v) for v in df["High"]],
        "l": [rnd(v) for v in df["Low"]], "c": [rnd(v) for v in df["Close"]],
        "v": [int(v) if v == v else 0 for v in vol],
    }


def ratio(a, b):
    j = a[["Open", "High", "Low", "Close"]].join(b[["Open", "High", "Low", "Close"]], lsuffix="_a", rsuffix="_b", how="inner")
    r = pd.DataFrame(index=j.index)
    r["Open"] = j.Open_a / j.Open_b
    r["Close"] = j.Close_a / j.Close_b
    r["High"] = r[["Open", "Close"]].max(axis=1)
    r["Low"] = r[["Open", "Close"]].min(axis=1)
    r["Volume"] = 0
    return r



# ---------- Ljubljanska borza (ljse.si) ----------
import datetime as _dt
import requests as _rq

_UA = {"User-Agent": "Mozilla/5.0 (luka-charts robot)", "X-Requested-With": "XMLHttpRequest"}


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return float(str(v).replace(".", "").replace(",", "."))


def ljse_fetch(it):
    isin, kind = it["isin"], it.get("kind", "stock")
    to = _dt.date.today()
    frm = to - _dt.timedelta(days=5 * 365 - 5)   # borza vrne največ ~5 let
    if kind == "index":
        url = f"https://ljse.si/json/indexHistory/{isin}/{frm}/{to}/si"
    else:
        url = f"https://ljse.si/json/securityHistory/{isin}/{frm}/{to}/si?trading_model_id=ALL"
    j = _rq.get(url, headers=_UA, timeout=30).json()
    if j.get("error"):
        raise RuntimeError(j["error"])
    bars = {}
    for r in j.get("rows", []):
        d = r.get("date_yyyy_MM_dd") or _dt.datetime.strptime(r["date"], "%d.%m.%Y").strftime("%Y-%m-%d")
        if kind == "index":
            o, h, l, c, v = (_num(r.get(k)) for k in ("open_value", "high_value", "low_value", "last_value", "turnover"))
        else:
            if d in bars and r.get("trading_model_id") != "CT":
                continue
            o, h, l, c, v = (r.get(k) for k in ("open_price_n", "high_price_n", "low_price_n", "last_price_n", "volume_n"))
        if c is None:
            continue
        o = o if o is not None else c
        bars[d] = (o, h if h is not None else max(o, c), l if l is not None else min(o, c), c, v or 0)
    # današnja (še nezaključena) sveča iz današnjih poslov
    today = to.strftime("%Y-%m-%d")
    try:
        probe = isin if kind != "index" else it.get("probe_isin", "SI0031102120")
        pj = _rq.get(f"https://ljse.si/si/papir/310?isin={probe}&range=1m", headers=_UA, timeout=30).json()
        if kind == "index":
            dates, vals = pj["moves"]["date"], pj["moves"]["index"]
            if dates and dates[-1][:10] == today and today not in bars and vals[-1]:
                c = float(vals[-1])
                prev = list(bars.values())[-1][3] if bars else c
                bars[today] = (prev, max(prev, c), min(prev, c), c, 0)
        else:
            rows = (pj.get("Trades") or {}).get("rows") or []
            if rows and today not in bars:
                px = [_num(r["price"]) for r in sorted(rows, key=lambda r: int(r["seqno"]))]
                qty = sum(_num(r["quantity"]) for r in rows)
                bars[today] = (px[0], max(px), min(px), px[-1], qty)
    except Exception as e:  # noqa
        print(f"  ! {it['id']} današnji posli: {e}")
    keys = sorted(bars)
    tz = _dt.timezone.utc
    out = {"t": [], "o": [], "h": [], "l": [], "c": [], "v": []}
    for d in keys:
        o, h, l, c, v = bars[d]
        out["t"].append(int(_dt.datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=tz).timestamp() * 1000))
        for k, x in zip("ohlc", (o, h, l, c)):
            out[k].append(rnd(x))
        out["v"].append(int(v or 0))
    return out


US_RE = re.compile(r"^[A-Z]{1,5}(-[A-Z])?$")


def extended(tickers):
    """Pre/post-market zadnja cena za ameriške delnice/ETF (Yahoo 5m prepost)."""
    out = {}
    for chunk in [tickers[i:i + 25] for i in range(0, len(tickers), 25)]:
        try:
            df = yf.download(chunk, period="5d", interval="5m", prepost=True, group_by="ticker",
                             auto_adjust=False, actions=False, progress=False, threads=False)
        except Exception as e:  # noqa
            print("  ! prepost:", e)
            continue
        if df is None or df.empty:
            continue
        lvl0 = set(df.columns.get_level_values(0)) if isinstance(df.columns, pd.MultiIndex) else set()
        for t in chunk:
            d = df[t] if t in lvl0 else (df if not lvl0 and len(chunk) == 1 else None)
            if d is None:
                continue
            d = d.dropna(subset=["Close"])
            if d.empty:
                continue
            idx = d.index.tz_convert("America/New_York") if d.index.tz is not None else d.index.tz_localize("UTC").tz_convert("America/New_York")
            mins = idx.hour * 60 + idx.minute
            reg = (mins >= 570) & (mins < 960) & (idx.dayofweek < 5)
            if not reg.any():
                continue
            last_reg_i = max(i for i, r in enumerate(reg) if r)
            reg_close = float(d["Close"].iloc[last_reg_i])
            if last_reg_i == len(d) - 1:
                continue  # zadnja sveča je v rednem trgovanju → ni pre/post
            p = float(d["Close"].iloc[-1]); ts = idx[-1]
            sess = "post" if ts.date() == idx[last_reg_i].date() and ts.hour * 60 + ts.minute >= 960 else "pre"
            out[t] = {"s": sess, "p": rnd(p), "chg": rnd((p / reg_close - 1) * 100), "base": rnd(reg_close),
                      "t": int(ts.timestamp() * 1000)}
        time.sleep(1)
    return out


def main():
    groups = json.load(open(os.path.join(ROOT, "watchlist.json"), encoding="utf-8"))
    items = [it for g in groups for it in g["items"] if it.get("src", "yahoo") == "yahoo"]
    # vsi kandidati + tickerji za razmerja
    want = sorted({c for it in items for c in it.get("y", [])} | {c for it in items for c in it.get("ratio", [])})
    data = {iv: download(want, iv) for iv in INTERVALS}
    print("Prenešeno:", {iv: len(d) for iv, d in data.items()}, "od", len(want))

    try:
        ext = extended([t for t in want if US_RE.match(t)])
        print("Pre/post:", {k: (v["s"], v["p"]) for k, v in ext.items()})
    except Exception as e:  # noqa
        print("  ! pre/post napaka:", e); ext = {}
    meta = {"updated": int(time.time() * 1000), "symbols": {}}
    for it in items:
        sid, info = it["id"], {"ok": False}
        frames = {}
        if "ratio" in it:
            a, b = it["ratio"]
            for iv in INTERVALS:
                if a in data[iv] and b in data[iv]:
                    frames[iv] = ratio(data[iv][a], data[iv][b])
            used = f"{a}/{b}"
        else:
            used = next((c for c in it.get("y", []) if c in data["1d"]), None)
            if used:
                frames = {iv: data[iv][used] for iv in INTERVALS if used in data[iv]}
        if "1d" in frames and not frames["1d"].empty:
            for iv, df in frames.items():
                json.dump(to_json(df), open(os.path.join(OUT, f"{fname(sid)}_{iv}.json"), "w"), separators=(",", ":"))
            d = frames["1d"]
            latest = frames.get("15m", d)
            last = float(latest["Close"].iloc[-1])
            last_day = pd.Timestamp(latest.index[-1]).date()
            prev_rows = d[[pd.Timestamp(x).date() < last_day for x in d.index]]
            prev = float(prev_rows["Close"].iloc[-1]) if len(prev_rows) else float(d["Close"].iloc[0])
            info = {"ok": True, "yahoo": used, "last": rnd(last), "prev": rnd(prev),
                    "chg": rnd((last / prev - 1) * 100) if prev else None,
                    "lastBar": int(pd.Timestamp(latest.index[-1]).timestamp() * 1000)}
            if used in ext:
                info["ext"] = ext[used]
            print(f"  + {sid:8} {used:10} {info['last']} ({info['chg']}%)")
        else:
            print(f"  - {sid:8} ni podatkov (kandidati: {it.get('y') or it.get('ratio') or 'brez'})")
        meta["symbols"][sid] = info
    for g in groups:
        for it in g["items"]:
            if it.get("src") != "ljse":
                continue
            sid = it["id"]
            try:
                d = ljse_fetch(it)
                if not d["t"]:
                    raise RuntimeError("ni vrstic")
                json.dump(d, open(os.path.join(OUT, f"{fname(sid)}_1d.json"), "w"), separators=(",", ":"))
                c = d["c"]
                meta["symbols"][sid] = {"ok": True, "yahoo": "LJSE " + it.get("isin", ""), "source": "Ljubljanska borza",
                                        "last": c[-1], "prev": c[-2] if len(c) > 1 else c[-1],
                                        "chg": rnd((c[-1] / c[-2] - 1) * 100) if len(c) > 1 and c[-2] else None,
                                        "lastBar": d["t"][-1]}
                print(f"  + {sid:8} LJSE       {c[-1]} ({meta['symbols'][sid]['chg']}%) {len(c)} dni")
            except Exception as e:  # noqa
                meta["symbols"][sid] = {"ok": False}
                print(f"  - {sid:8} LJSE napaka: {e}")
    json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), separators=(",", ":"))
    print("Brez podatkov:", [k for k, v in meta["symbols"].items() if not v["ok"]] or "nič")


if __name__ == "__main__":
    main()
