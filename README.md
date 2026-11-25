# Luka Charts

Lastna chart aplikacija v stilu TradingView (KLineCharts).

- **BTC, DVOL in drugi Deribit instrumenti**: v živo prek Deribit WebSocket API.
- **Delnice, ETF-ji, forex, VIX, DXY, nafta**: Yahoo Finance; GitHub Action (`.github/workflows/update.yml`) jih med tednom pobere vsakih 30 min in objavi na GitHub Pages.
- Simbole urejaš v `watchlist.json` (`y` = seznam Yahoo tickerjev, prvi z rezultati zmaga; `ratio` = razmerje dveh tickerjev).
- Risbe, indikatorji in nastavitve se shranijo v brskalnik (localStorage).
