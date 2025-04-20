run-audit : 
	python ad_miner/__main__.py -cf Audit -b bolt://localhost:10001 -u neo4j -p neo5j

build-knowledge-data : 
	python agent/get_llm_assets.py