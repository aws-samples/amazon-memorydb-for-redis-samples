resource "random_string" "random" {
  length  = 8
  lower   = true
  special = false
  upper   = false
}

locals {
  name   = "infra-semantic-cache"
  region = "us-east-1"

  vpc_cidr = "10.0.0.0/16"
  azs      = ["use1-az2", "use1-az4", "use1-az6"]
  tags = {
    environment = "development"
  }
  collection_name = "kb-collection-${random_string.random.result}"
}

################################################################################
# Providers
################################################################################

provider "aws" {
  region = local.region
}
provider "opensearch" {
  url         = aws_opensearchserverless_collection.knowledge_base.collection_endpoint
  healthcheck = false
  aws_region  = local.region
}



################################################################################
# Networking
################################################################################

data "aws_availability_zones" "available" {}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0" #

  name = local.name
  cidr = local.vpc_cidr #

  azs             = local.azs
  private_subnets = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 4, k)]
  public_subnets  = [for k, v in local.azs : cidrsubnet(local.vpc_cidr, 8, k + 48)] #

  enable_nat_gateway = true
  single_nat_gateway = true

  manage_default_network_acl    = true
  default_network_acl_tags      = { Name = "${local.name}-default" }
  manage_default_route_table    = true
  default_route_table_tags      = { Name = "${local.name}-default" }
  manage_default_security_group = true
  default_security_group_tags   = { Name = "${local.name}-default" } #

  tags = local.tags
}

################################################################################
# MemoryDB
################################################################################


resource "aws_security_group" "semantic_cache_sg" {
  name   = "semantic-cache-sg"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/8"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

}

resource "aws_memorydb_subnet_group" "semantic_cache_subnets" {
  name       = "semantic-cache-subnet-group"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_memorydb_cluster" "semantic_cache_cluster" {
  acl_name                 = "open-access"
  name                     = "semantic-cache-cluster"
  node_type                = "db.t4g.small"
  num_shards               = 1
  security_group_ids       = [aws_security_group.semantic_cache_sg.id]
  snapshot_retention_limit = 7
  subnet_group_name        = aws_memorydb_subnet_group.semantic_cache_subnets.id
  parameter_group_name     = "default.memorydb-redis7.search"
}

################################################################################
# Lambda
################################################################################

module "lambda" {
  source                = "terraform-aws-modules/lambda/aws"
  attach_tracing_policy = true
  tracing_mode          = "Active"
  environment_variables = {
    "KNOWLEDGE_BASE_ID" : aws_bedrockagent_knowledge_base.docs_small.id
    "PERISTENT_SEMANTIC_CACHE_ENDPOINT" : aws_memorydb_cluster.semantic_cache_cluster.cluster_endpoint[0].address
  }
  function_name = "answer-question-function-${random_string.random.result}"
  description   = "Example function to answer questions from a knowledge base"
  handler       = "app.lambda_handler"
  runtime       = "python3.11"
  layers        = ["arn:aws:lambda:us-east-1:336392948345:layer:AWSSDKPandas-Python311:12"]

  source_path = "./answerQuestionFunction"

  vpc_subnet_ids                     = module.vpc.private_subnets
  vpc_security_group_ids             = [aws_security_group.semantic_cache_sg.id]
  attach_network_policy              = true
  replace_security_groups_on_destroy = true
  replacement_security_group_ids     = [aws_security_group.semantic_cache_sg.id]
  timeout                            = 30
  attach_policy_json                 = true
  policy_json                        = <<-EOT
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:RetrieveAndGenerate",
                    "bedrock:Retrieve"
                ],
                "Resource": ["*"]
            }
        ]
    }
  EOT
}

################################################################################
# API Gateway
################################################################################

resource "aws_api_gateway_rest_api" "chat_api" {
  name        = "ChatAPI"
  description = "Semantic cache chat application example"
}

resource "aws_api_gateway_resource" "answer" {
  rest_api_id = aws_api_gateway_rest_api.chat_api.id
  parent_id   = aws_api_gateway_rest_api.chat_api.root_resource_id
  path_part   = "answer"
}

resource "aws_api_gateway_method" "method_post" {
  rest_api_id      = aws_api_gateway_rest_api.chat_api.id
  resource_id      = aws_api_gateway_resource.answer.id
  http_method      = "POST"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id = aws_api_gateway_rest_api.chat_api.id
  resource_id = aws_api_gateway_method.method_post.resource_id
  http_method = aws_api_gateway_method.method_post.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = module.lambda.lambda_function_invoke_arn
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda.lambda_function_name
  principal     = "apigateway.amazonaws.com"

  # The /*/* portion grants access from any method on any resource
  # within the API Gateway "REST API".
  source_arn = "${aws_api_gateway_rest_api.chat_api.execution_arn}/*"
}

resource "aws_api_gateway_deployment" "chat_api_dev" {
  depends_on = [
    aws_api_gateway_integration.lambda
  ]

  rest_api_id = aws_api_gateway_rest_api.chat_api.id
  stage_name  = "dev"
}

resource "aws_api_gateway_api_key" "access_key" {
  name = "chat_api_access_key"
}

resource "aws_api_gateway_usage_plan" "chat_api_usage_plan" {
  name         = "chat-api-usage-plan"
  description  = "Default usage plan"
  product_code = "CHAT"

  api_stages {
    api_id = aws_api_gateway_rest_api.chat_api.id
    stage  = aws_api_gateway_deployment.chat_api_dev.stage_name
  }
}

resource "aws_api_gateway_usage_plan_key" "main" {
  key_id        = aws_api_gateway_api_key.access_key.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.chat_api_usage_plan.id
}

################################################################################
# Opensearch collection
################################################################################



# Creates an encryption security policy
resource "aws_opensearchserverless_security_policy" "encryption_policy" {
  name        = "encryption-policy-${random_string.random.result}"
  type        = "encryption"
  description = "encryption policy for ${local.collection_name}"
  policy = jsonencode({
    Rules = [
      {
        Resource = [
          "collection/${local.collection_name}"
        ],
        ResourceType = "collection"
      }
    ],
    AWSOwnedKey = true
  })
}

# Creates a network security policy
resource "aws_opensearchserverless_security_policy" "network_policy" {
  name        = "network-policy-${random_string.random.result}"
  type        = "network"
  description = "public access for dashboard, public access for collection endpoint"
  policy = jsonencode([
    {
      Description = "Public access for endpoint",
      Rules = [
        {
          ResourceType = "collection",
          Resource = [
            "collection/${local.collection_name}"
          ]
        },
        {
          ResourceType = "dashboard"
          Resource = [
            "collection/${local.collection_name}"
          ]
        }
      ],
      AllowFromPublic = true
    }
  ])
}

# Gets access to the effective Account ID in which Terraform is authorized
data "aws_caller_identity" "current" {}

# Creates a data access policy
resource "aws_opensearchserverless_access_policy" "admin_data_access_policy" {
  name        = "access-policy-${random_string.random.result}"
  type        = "data"
  description = "allow index and collection access by creator"
  policy = jsonencode([
    {
      Rules = [
        {
          ResourceType = "index",
          Resource = [
            "index/${local.collection_name}/*"
          ],
          Permission = [
            "aoss:*"
          ]
        },
        {
          ResourceType = "collection",
          Resource = [
            "collection/${local.collection_name}"
          ],
          Permission = [
            "aoss:*"
          ]
        }
      ],
      Principal = [
        data.aws_caller_identity.current.arn,
        aws_iam_role.knowledge_base_role.arn
      ]
    }
  ])

  # It might take a several seconds for the access policy to propagate after is created, which causes a race conditions with the index creation
  # If terraform attempts to create an index before the propagation is completed, a 403 error is returned. 
  # Sleeping 120 seconds for the policy to propagate
  provisioner "local-exec" {
    command = "echo 'Sleeping 2 minutes for the policy to propagate' && sleep 120"
  }
}

# Creates a collection
resource "aws_opensearchserverless_collection" "knowledge_base" {
  name = local.collection_name
  type = "VECTORSEARCH"
  depends_on = [
    aws_opensearchserverless_security_policy.encryption_policy,
    aws_opensearchserverless_security_policy.network_policy
  ]
}


################################################################################
# Bedrock knowledge bases
################################################################################

resource "aws_s3_bucket" "knowledge_base" {
  bucket        = "knowledge-base-${random_string.random.result}"
  force_destroy = true
}

# Make sure that the bucket has Public Access block
resource "aws_s3_bucket_public_access_block" "example" {
  bucket = aws_s3_bucket.knowledge_base.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_iam_role" "knowledge_base_role" {
  name = "AmazonBedrockExecutionRoleForKnowledgeBase_${random_string.random.result}"

  # Terraform's "jsonencode" function converts a
  # Terraform expression result to valid JSON syntax.
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = "AmazonBedrockKnowledgeBaseTrustPolicy"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        "Condition" : {
          "StringEquals" : {
            "aws:SourceAccount" : data.aws_caller_identity.current.account_id
          },
          "ArnLike" : {
            "aws:SourceArn" : "arn:aws:bedrock:${local.region}:${data.aws_caller_identity.current.account_id}:knowledge-base/*"
          }
        }
      },
    ]
  })

  inline_policy {
    name = "AmazonBedrockFoundationModelPolicyForKnowledgeBase"

    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Action   = ["bedrock:InvokeModel"]
          Effect   = "Allow"
          Resource = "arn:aws:bedrock:${local.region}::foundation-model/amazon.titan-embed-text-v1"
        },
        {
          Action   = ["bedrock:ListFoundationModels", "bedrock:ListCustomModels"]
          Effect   = "Allow"
          Resource = "arn:aws:bedrock:${local.region}::foundation-model/amazon.titan-embed-text-v1"
        }
      ]
    })
  }

  inline_policy {
    name = "AmazonBedrockOSSPolicyForKnowledgeBase"

    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Action   = ["aoss:APIAccessAll"]
          Effect   = "Allow"
          Resource = aws_opensearchserverless_collection.knowledge_base.arn
        },
      ]
    })
  }

  inline_policy {
    name = "S3ListBucketStatement"

    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Action   = ["s3:ListBucket"]
          Effect   = "Allow"
          Resource = aws_s3_bucket.knowledge_base.arn
        },
        {
          Action   = ["s3:GetObject"]
          Effect   = "Allow"
          Resource = "${aws_s3_bucket.knowledge_base.arn}/*"
        },
      ]
    })
  }
}

resource "aws_bedrockagent_knowledge_base" "docs_small" {
  name     = "docs-small-${random_string.random.result}"
  role_arn = aws_iam_role.knowledge_base_role.arn
  knowledge_base_configuration {
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${local.region}::foundation-model/amazon.titan-embed-text-v1"
    }
    type = "VECTOR"
  }
  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"
    opensearch_serverless_configuration {
      collection_arn    = aws_opensearchserverless_collection.knowledge_base.arn
      vector_index_name = "bedrock-knowledge-base-default-index"
      field_mapping {
        vector_field   = "bedrock-knowledge-base-default-vector"
        text_field     = "AMAZON_BEDROCK_TEXT_CHUNK"
        metadata_field = "AMAZON_BEDROCK_METADATA"
      }
    }
  }
  depends_on = [opensearch_index.bedrock_knowledge_base_default_index]
}

resource "aws_bedrockagent_data_source" "s3" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.docs_small.id
  name              = "s3-default"
  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn = aws_s3_bucket.knowledge_base.arn
    }
  }
}

# Create a index

resource "opensearch_index" "bedrock_knowledge_base_default_index" {
  name               = "bedrock-knowledge-base-default-index"
  number_of_shards   = "2"
  number_of_replicas = 0
  index_knn          = true
  force_destroy      = true
  depends_on = [
    aws_opensearchserverless_collection.knowledge_base,
    aws_opensearchserverless_access_policy.admin_data_access_policy
  ]
  lifecycle {
    ignore_changes = [mappings]
  }
  mappings = <<EOF
    {
      "properties": {
        "AMAZON_BEDROCK_METADATA": {
          "type": "text",
          "index": false
        },
        "AMAZON_BEDROCK_TEXT_CHUNK": {
          "type": "text"
        },
        "bedrock-knowledge-base-default-vector": {
          "type": "knn_vector",
          "dimension": 1536,
          "method": {
            "engine": "faiss",
            "space_type": "l2",
            "name": "hnsw",
            "parameters": {}
          }
        },
        "id": {
          "type": "text",
          "fields": {
            "keyword": {
              "type": "keyword",
              "ignore_above": 256
            }
          }
        },
        "x-amz-bedrock-kb-source-uri": {
          "type": "text",
          "fields": {
            "keyword": {
              "type": "keyword",
              "ignore_above": 256
            }
          }
        }
      }
    }
EOF

  provisioner "local-exec" {
    command = "echo 'Sleeping 30 seconds to allow index to be fully created before creating knowledge base' && sleep 30"
  }
}


