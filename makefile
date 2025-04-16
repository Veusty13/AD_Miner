run-audit : 
	export PYTHONPATH=. 
	python ad_miner/__main__.py -cf Audit -b bolt://localhost:10001 -u neo4j -p neo5j

