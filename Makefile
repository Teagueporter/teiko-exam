.PHONY: setup pipeline dashboard clean

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -r requirements.txt

pipeline:
	.venv/bin/python load_data.py
	.venv/bin/python analysis.py

dashboard:
	STREAMLIT_BROWSER_GATHER_USAGE_STATS=false .venv/bin/streamlit run dashboard.py --server.headless true

clean:
	rm -f teiko.db
	rm -rf outputs
