import yfinance as yf
for iv, per in [("15m","5d"),("1h","5d")]:
    d = yf.download("AAPL", period=per, interval=iv, prepost=True, progress=False, auto_adjust=False)
    print(iv, len(d)); print(d.tail(12).to_string()[:3000])
