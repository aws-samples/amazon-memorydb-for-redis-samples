################################################################################
# Opensearch
################################################################################


output "opensearch_collection" {
  description = "OS Collection endpoint"
  value       = aws_opensearchserverless_collection.knowledge_base.collection_endpoint
}

output "s3_bucket" {
  description = "S3 bucket for knowledge_base"
  value       = aws_s3_bucket.knowledge_base.id
}

output "data_source_id" {
  description = "Knowledge base data source ID"
  value       = aws_bedrockagent_data_source.s3.id
}

output "knowledge_base_id" {
  description = "knowledge base ID"
  value       = aws_bedrockagent_knowledge_base.docs_small.id
}

output "api_id" {
  description = "Chat API ID"
  value       = aws_api_gateway_rest_api.chat_api.id
}

output "resource_random_id" {
  description = "ID appended to resources"
  value       = random_string.random.result
}

output "memory_db_cluster_endpoint" {
  description = "MemoryDB cluster connection endpoint"
  value       = try("${aws_memorydb_cluster.semantic_cache_cluster.cluster_endpoint[0].address}:${aws_memorydb_cluster.semantic_cache_cluster.cluster_endpoint[0].port}", "")
}

output "api_key_id" {
  description = "Chat API key ID"
  value       = aws_api_gateway_api_key.access_key.id
}
