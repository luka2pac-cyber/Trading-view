for u in "https://www.deribit.com/api/v2/public/test" "https://www.deribit.com/api/v2/public/get_index_price?index_name=btc_usd" "https://test.deribit.com/api/v2/public/test" "https://deribit.com/api/v2/public/test" "https://www.deribit.com/"; do echo "== $u"; curl -s -m 15 -D - "$u" | head -c 900; echo; done
curl -s -m 10 https://ipinfo.io/json | head -c 300; echo
curl -s -m 10 https://status.deribit.com/api/v2/summary.json | head -c 1500; echo
