import asyncio, json, time, websockets
async def run(origin):
    print("=== origin", origin)
    hdr = {"Origin": origin} if origin else {}
    async with websockets.connect("wss://www.deribit.com/ws/api/v2", additional_headers=hdr) as ws:
        now = int(time.time()*1000); i = 0
        reqs = [("public/set_heartbeat", {"interval": 30}),
                ("public/subscribe", {"channels": ["ticker.BTC-PERPETUAL.100ms"]}),
                ("public/subscribe", {"channels": ["deribit_volatility_index.btc_usd"]}),
                ("public/subscribe", {"channels": ["chart.trades.BTC-PERPETUAL.1D"]}),
                ("public/subscribe", {"channels": ["ticker.BTC-PERPETUAL.100ms", "deribit_volatility_index.btc_usd", "chart.trades.BTC-PERPETUAL.1D"]}),
                ("public/get_tradingview_chart_data", {"instrument_name": "BTC-PERPETUAL", "start_timestamp": now-1000*864e5, "end_timestamp": now, "resolution": "1D"}),
                ("public/get_volatility_index_data", {"currency": "BTC", "start_timestamp": now-1000*3600e3, "end_timestamp": now, "resolution": "3600"}),
                ("public/get_volatility_index_data", {"currency": "BTC", "start_timestamp": now-3*864e5, "end_timestamp": now, "resolution": "1D"})]
        for m, p in reqs:
            i += 1; await ws.send(json.dumps({"jsonrpc": "2.0", "id": i, "method": m, "params": p}))
        t0 = time.time(); n = {}
        while time.time()-t0 < 8:
            try: r = json.loads(await asyncio.wait_for(ws.recv(), 2))
            except asyncio.TimeoutError: continue
            if "id" in r:
                print("RESP", r["id"], json.dumps(r.get("error") or r.get("result"))[:400])
            else:
                ch = r.get("params", {}).get("channel"); n[ch] = n.get(ch, 0)+1
                if n[ch] == 1: print("NOTIF", json.dumps(r)[:300])
        print("notif counts", n)
for o in [None, "https://luka2pac-cyber.github.io"]:
    try: asyncio.run(run(o))
    except Exception as e: print("EXC", repr(e))
