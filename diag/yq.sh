start=$(date +%s); python scripts/fetch.py > fetch.log 2>&1; echo "exit $? trajanje $(( $(date +%s)-start ))s"
grep -i "pre/post\|quote\|Traceback\|Error:" fetch.log | cut -c1-1500 | head -20
python3 -c "import json;m=json.load(open('data/meta.json'));print({k:m['symbols'][k].get('ext') for k in ['SPY','AAPL','NVDA']})"
