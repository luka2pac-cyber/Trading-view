date -u
for s in AAPL NVDA SPY; do echo "== $s"; curl -s -m 20 -A "Mozilla/5.0" "https://query1.finance.yahoo.com/v8/finance/chart/$s?interval=5m&range=2d&includePrePost=true" | python3 -c "
import json,sys,datetime as dt,zoneinfo
ny=zoneinfo.ZoneInfo('America/New_York'); r=json.load(sys.stdin)['chart']['result'][0]; m=r['meta']
print('regularMarketTime', dt.datetime.fromtimestamp(m.get('regularMarketTime',0),ny), 'price', m.get('regularMarketPrice'))
print('currentTradingPeriod', json.dumps(m.get('currentTradingPeriod'))[:300])
q=r['indicators']['quote'][0]; ts=r['timestamp']
rows=[(dt.datetime.fromtimestamp(t,ny),c) for t,c in zip(ts,q['close']) if c is not None]
print('zadnje sveče:'); [print('  ',a,b) for a,b in rows[-6:]]
"; done
python3 -c "
import yfinance as yf
d=yf.download('AAPL',period='5d',interval='5m',prepost=True,progress=False,auto_adjust=False); print('yfinance AAPL 5m prepost zadnje:'); print(d.tail(4).to_string())"
