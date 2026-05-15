Neo4j
docker run -d --name neo4j-local `
  -p 7474:7474 -p 7687:7687 `
  -e NEO4J_AUTH=neo4j/raganything123 `
  neo4j:5-community
