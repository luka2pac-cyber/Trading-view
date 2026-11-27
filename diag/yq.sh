date -u
python3 - <<'P'
import yfinance as yf, json
for s in ["SPY","AAPL"]:
    try:
        i=yf.Ticker(s).info
        print(s, {k:i.get(k) for k in ["marketState","preMarketPrice","preMarketTime","preMarketChangePercent","postMarketPrice","postMarketTime","regularMarketPrice"]})
    except Exception as e: print(s,"info err",e)
d=yf.download("SPY",period="1d",interval="1m",prepost=True,progress=False,auto_adjust=False); print("1m SPY", len(d)); print(d.tail(3).to_string())
P
for s in SPY AAPL; do echo "== nasdaq $s"; curl -s -m 15 -A "Mozilla/5.0" -H "Accept: application/json" "https://api.nasdaq.com/api/quote/$s/info?assetclass=$([ $s = SPY ] && echo etf || echo stocks)" | head -c 900; echo; done
echo "== nasdaq extended"; curl -s -m 15 -A "Mozilla/5.0" -H "Accept: application/json" "https://api.nasdaq.com/api/quote/SPY/extended-trading?assetclass=etf&markettype=pre" | head -c 900; echo
