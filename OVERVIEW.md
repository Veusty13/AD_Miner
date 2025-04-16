exécution via ___main__.py

prépare un dossier avec tous les assets front : css, js et html

lance la fonction pre_request, fonction du module neo4j_class : 
    - récupère a date de dernière connexion parmi tous les objets du graphe, si  pas trouvé renvoie la date d'aujourd'hui
    - récupère le nombre total de noeuds et de liens
    - regarde s'il y a des données azure et la version de neo4j utilisée

fais un peu de cleaning sur le nom des labels

créer un objet de la classe Neo4j qui sera utilisé pour faire des requêtes : 
    - lors de l'init déclare la config du serveur/ cluster
    - liste toutes les propriétés
    - charge toutes les requêtes qui sont dans sources/modules/requests.json
    - modifie la valeur associée à output_type de façon à ce que ce soit l'un des types python : Graph (custom), List ou dict
    - remplace les champs qui contiennent les strings de postprocessing en vrai méthodes post processing qui sont des méthodes de la classe Neo4j dont la valeur associée à la clef devient un objet python 
    - charge les edge ratings (exploitabilité des relations, plus c'est petit, plus c'est exploitable)


Chaque requête est en fait un dictionnaire qui suit l'objet template déclaré au sein même du dictionnaire.
Un exemple avec l'élément objects_to_domain_admin : 
    "name": "Objects with path to DA",
    "is_a_gds_request": "true",
    "create_gds_graph": "CALL gds.graph.project.cypher('graph_objects_to_domain_admin', 'MATCH (n) RETURN id(n) AS id', 'MATCH (n)-[r:$properties$]->(m) RETURN id(m) as source, id(n) AS target, r.cost as cost', {validateRelationships: false})",
    "drop_gds_graph": "CALL gds.graph.drop('graph_objects_to_domain_admin', false) YIELD graphName",
    "request": "MATCH (m{path_candidate:true}) WHERE NOT m.name IS NULL WITH m ORDER BY ID(m) SKIP PARAM1 LIMIT PARAM2 MATCH p = shortestPath((m)-[r:$properties$*1..$recursive_level$]->(g:Group{is_dag:true})) WHERE m<>g SET m.has_path_to_da=true RETURN DISTINCT(p) as p",
    "gds_request" : "MATCH (target:Group {is_dag: true}) CALL gds.allShortestPaths.dijkstra.stream('graph_objects_to_domain_admin', {sourceNode: target, relatieonshipWeightProperty: 'cost', logProgress: false}) YIELD path WITH nodes(path)[-1] AS starting_node, path WHERE starting_node.path_candidate = TRUE SET starting_node.has_path_to_da=true RETURN path as p",
    "output_type": "Graph",
    "scope_query": "MATCH (m{path_candidate:true}) WHERE NOT m.name IS NULL RETURN count(m)",
    "reverse_path": true,
    "is_a_write_request": "true"

Lance la commande populate_data_and_cache qui exécute toutes les requêtes ou bien charge le cache en se basant sur le fichier config.json qui contient les points de contrôle à vérifier et lance la méthode classe de Neo4J process_request() qui se charge de load ou d'exécuter la requête
Si la requête est exécutée, la classe peut lancer une requête graph data science pour aller plus vite en faisant des projections de graphe entre autres auquel cas le graph projeté est d'abord créé.
Une scope query est lancée pour voir le périmètre sur lequel doit s'appliquer la requêté , permet de fragmenter les requpêtes en n parties pour profiter du parallèlisme
La partie post processing est ensuite exécutée sur le résultat
la sortie de la fonction populate_data_and_cache est le dictionnaire requests_results

Analyse primaire : utilise le module common_analysis de modules pour faire le listings des instances AD CS serveurs, utilisateurs, domaines, etc ...
prends en entrée le requests_results

Analyse secondaire (plus dans le détails) en lien avec les points de contrôle
prends en entrée le requests_results qui va piocher dans le dossier modules > controls, exemple graph_path_objects_to_da.py
