"""Cenovni alarmi prek Telegrama.

- Bere ukaze, ki jih Luka pošlje botu (/alarm, /alarmi, /brisi, /start <koda iz aplikacije>).
- Preveri aktivne alarme proti zadnjim cenam (Yahoo/LJSE datoteke iz fetch.py, Bitstamp, Deribit).
- Sproženi alarm pošlje v Telegram in ga označi kot sprožen.
Stanje je v alerts.json (robot ga commita, ko se kaj spremeni).
"""
import base64
import json
import os
import re
import time

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
ALERTS = os.path.join(ROOT, "alerts.json")
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}"
APP_URL = "https://luka2pac-cyber.github.io/Trading-view/"


def load():
    try:
        return json.load(open(ALERTS, encoding="utf-8"))
    except Exception:  # noqa
        return {"chat_id": None, "tg_offset": 0, "alerts": []}


def tg(method, **params):
    if not TOKEN:
        return None
    try:
        return requests.post(f"{API}/{method}", json=params, timeout=20).json()
    except Exception as e:  # noqa
        print("  ! telegram:", e)
        return None


def send(st, text):
    if st.get("chat_id"):
        tg("sendMessage", chat_id=st["chat_id"], text=text, parse_mode="HTML", disable_web_page_preview=True)


def fname(sid):
    return re.sub(r"[^A-Za-z0-9._-]", "_", sid)


def watchlist():
    groups = json.load(open(os.path.join(ROOT, "watchlist.json"), encoding="utf-8"))
    return {it["id"].upper(): it for g in groups for it in g["items"]}


# ---------- cene: zadnja cena + najvišja/najnižja od danega trenutka ----------
def bars_since(sid, it, since_ms):
    """Vrne (zadnja_cena, max_high, min_low) za sveče po since_ms (vključno s tekočo)."""
    src = it.get("src", "yahoo")
    rows = []
    if src == "bitstamp":
        j = requests.get(f"https://www.bitstamp.net/api/v2/ohlc/{it.get('pair', 'btcusd')}/?step=300&limit=300", timeout=20).json()
        rows = [(int(o["timestamp"]) * 1000, float(o["high"]), float(o["low"]), float(o["close"])) for o in j["data"]["ohlc"]]
        step = 300_000
    elif src == "deribit":
        end = int(time.time() * 1000)
        inst = it["inst"]
        if inst.startswith("DVOL:"):
            j = requests.get("https://www.deribit.com/api/v2/public/get_volatility_index_data",
                             params={"currency": inst[5:], "start_timestamp": end - 86_400_000, "end_timestamp": end, "resolution": "60"}, timeout=20).json()
            rows = [(d[0], d[2], d[3], d[4]) for d in j["result"]["data"]]
        else:
            j = requests.get("https://www.deribit.com/api/v2/public/get_tradingview_chart_data",
                             params={"instrument_name": inst, "start_timestamp": end - 86_400_000, "end_timestamp": end, "resolution": "5"}, timeout=20).json()
            r = j["result"]
            rows = list(zip(r["ticks"], r["high"], r["low"], r["close"]))
        step = 300_000
    else:
        for iv, st in (("15m", 900_000), ("1d", 86_400_000)):
            p = os.path.join(DATA, f"{fname(it['id'])}_{iv}.json")
            if os.path.exists(p):
                d = json.load(open(p))
                rows = list(zip(d["t"], d["h"], d["l"], d["c"]))
                step = st
                break
    if not rows:
        return None
    rows.sort()
    last = rows[-1][3]
    recent = [r for r in rows if r[0] + step > since_ms]
    if not recent:
        return last, last, last
    return last, max(r[1] for r in recent), min(r[2] for r in recent)


def fmt(v):
    return f"{v:,.2f}".replace(",", " ") if abs(v) >= 1 else f"{v:.5g}"


# ---------- ukazi iz Telegrama ----------
def add_alert(st, wl, sym, price, note, reply=True):
    sym = sym.upper()
    if sym not in wl:
        send(st, f"❓ Simbola <b>{sym}</b> ni v watchlistu.")
        return
    try:
        cur = bars_since(sym, wl[sym], int(time.time() * 1000))
        cur = cur[0] if cur else None
    except Exception:  # noqa
        cur = None
    op = "above" if cur is None or price >= cur else "below"
    aid = base64.b32encode(os.urandom(4)).decode().rstrip("=")[:6]
    st["alerts"].append({"id": aid, "sym": sym, "price": price, "op": op, "note": note, "status": "active",
                         "created": int(time.time() * 1000), "ref": cur})
    if reply:
        arrow = "⬆️ nad" if op == "above" else "⬇️ pod"
        send(st, f"✅ Alarm <b>{sym}</b> {arrow} <b>{fmt(price)}</b>" + (f" (zdaj {fmt(cur)})" if cur else "") +
             (f"\n📝 {note}" if note else "") + f"\nID: <code>{aid}</code> · brisanje: /brisi {aid}")


def list_alerts(st):
    act = [a for a in st["alerts"] if a["status"] == "active"]
    if not act:
        send(st, "Ni aktivnih alarmov.\nNovega nastaviš z: <code>/alarm BTCUSD 60000 opomba</code>")
        return
    lines = [f"• <b>{a['sym']}</b> {'⬆️' if a['op'] == 'above' else '⬇️'} {fmt(a['price'])}" + (f" – {a['note']}" if a.get("note") else "") +
             f"  <code>{a['id']}</code>" for a in act]
    send(st, "🔔 Aktivni alarmi:\n" + "\n".join(lines) + "\n\nBrisanje: /brisi ID")


def handle_text(st, wl, text):
    t = text.strip()
    m = re.match(r"^/start\s+([AD])_([A-Za-z0-9_-]+)$", t)
    if m:  # povezava iz aplikacije
        raw = m.group(2) + "=" * (-len(m.group(2)) % 4)
        try:
            payload = base64.urlsafe_b64decode(raw).decode()
        except Exception:  # noqa
            send(st, "Povezava ni veljavna.")
            return
        if m.group(1) == "A":
            sym, price = payload.split("|")[:2]
            add_alert(st, wl, sym, float(price), "")
            return
        else:
            t = "/brisi " + payload
    if t.startswith("/start") and not m:
        send(st, "👋 Povezano z Luka Charts.\n\nUkazi:\n<code>/alarm BTCUSD 60000 opomba</code> – nov alarm\n/alarmi – seznam\n<code>/brisi ID</code> – izbriši alarm\n\n"
                 f"Alarme lahko nastaviš tudi v aplikaciji: {APP_URL}")
        return
    m = re.match(r"^/?alarm\s+(\S+)\s+([0-9][0-9.,]*)\s*(.*)$", t, re.I)
    if m:
        add_alert(st, wl, m.group(1), float(m.group(2).replace(",", ".")), m.group(3).strip())
        return
    if re.match(r"^/?alarmi\b", t, re.I):
        list_alerts(st)
        return
    m = re.match(r"^/?bri[sš]i\s+(\S+)", t, re.I)
    if m:
        aid = m.group(1).upper()
        if aid == "VSE":
            n = sum(1 for a in st["alerts"] if a["status"] == "active")
            st["alerts"] = [a for a in st["alerts"] if a["status"] != "active"]
            send(st, f"🗑️ Izbrisanih {n} alarmov.")
            return
        before = len(st["alerts"])
        st["alerts"] = [a for a in st["alerts"] if a["id"].upper() != aid]
        send(st, "🗑️ Izbrisano." if len(st["alerts"]) < before else f"Alarma {aid} ni.")
        return
    send(st, "Ne razumem. Primer: <code>/alarm BTCUSD 60000</code>, /alarmi, <code>/brisi ID</code>")


def poll_telegram(st, wl):
    if not TOKEN:
        print("  (TELEGRAM_TOKEN ni nastavljen – Telegram preskočen)")
        return
    me = tg("getMe")
    if me and me.get("ok"):
        st["bot"] = me["result"]["username"]
    r = tg("getUpdates", **({"offset": st["tg_offset"] + 1} if st.get("tg_offset") else {}), timeout=0)
    for u in (r or {}).get("result", []):
        st["tg_offset"] = u["update_id"]
        msg = u.get("message") or u.get("edited_message")
        if not msg or "text" not in msg:
            continue
        cid = msg["chat"]["id"]
        if not st.get("chat_id"):
            st["chat_id"] = cid  # prvi, ki piše botu, postane lastnik
        if cid != st["chat_id"]:
            continue
        print("  telegram:", msg["text"][:60])
        handle_text(st, wl, msg["text"])


LAST = {}


def check(st, wl):
    now = int(time.time() * 1000)
    for a in st["alerts"]:
        if a["status"] != "active":
            continue
        it = wl.get(a["sym"])
        if not it:
            continue
        try:
            res = bars_since(a["sym"], it, a["created"])
        except Exception as e:  # noqa
            print("  ! cena", a["sym"], e)
            continue
        if not res:
            continue
        last, hi, lo = res
        hit = (a["op"] == "above" and hi >= a["price"]) or (a["op"] == "below" and lo <= a["price"])
        LAST[a["id"]] = last
        if hit:
            a["status"] = "triggered"
            a["triggered"] = now
            arrow = "⬆️ nad" if a["op"] == "above" else "⬇️ pod"
            send(st, f"🔔 <b>{a['sym']}</b> je šel {arrow} <b>{fmt(a['price'])}</b>\nZdaj: {fmt(last)}" +
                 (f"\n📝 {a['note']}" if a.get("note") else "") + f"\n{APP_URL}")
            print("  🔔", a["sym"], a["price"])


def main():
    st = load()
    before = json.dumps(st, sort_keys=True)
    wl = watchlist()
    poll_telegram(st, wl)
    check(st, wl)
    # obdrži zadnjih 50 sproženih
    trig = [a for a in st["alerts"] if a["status"] != "active"][-50:]
    st["alerts"] = [a for a in st["alerts"] if a["status"] == "active"] + trig
    after = json.dumps(st, sort_keys=True)
    json.dump(st, open(ALERTS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # javna kopija za aplikacijo (brez chat_id)
    pub = {"bot": st.get("bot"), "connected": bool(st.get("chat_id")),
           "alerts": [{**{k: a.get(k) for k in ("id", "sym", "price", "op", "note", "status", "created", "triggered")}, "last": LAST.get(a["id"])} for a in st["alerts"]]}
    os.makedirs(DATA, exist_ok=True)
    json.dump(pub, open(os.path.join(DATA, "alerts.json"), "w", encoding="utf-8"), ensure_ascii=False)
    changed = before != after
    print("alerts changed:", changed, "| aktivnih:", sum(1 for a in st["alerts"] if a["status"] == "active"))
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
        f.write(f"changed={'true' if changed else 'false'}\n")


if __name__ == "__main__":
    main()
