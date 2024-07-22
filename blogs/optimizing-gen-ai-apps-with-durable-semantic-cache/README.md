# Persistent semantic cache example application

This solution automates the provisioning of an application that uses persistent semantic cache powered by Amazon MemoryDB. The application implements an API service to answer questions related to the AWS well architected framework. Once a question has been answered, it is saved to the persistent semantic cache, improving latency and compute cost for the subsequent semantically similar questions.

## Solution components

* Amazon MemoryDB: OSS Redis compatible, durable, in-memory database service that delivers ultra-fast performance. 
* Amazon API gateway: a fully managed service that makes it easy for developers to create, publish, maintain, monitor, and secure APIs at any scale
* Amazon Lambda: a serverless compute service for running code without having to provision or manage servers.
* Amazon Bedrock: a fully managed service that offers a choice of high-performing foundation models (FMs) from leading AI companies
* Amazon S3: an object storage service offering industry-leading scalability, data availability, security, and performance. Amazon S3 will be used to store the documents that will be ingested into Knowledge Bases for Amazon Bedrock
* Amazon OpenSearch Serverless: run petabyte-scale workloads without configuring, managing, and scaling OpenSearch clusters. 
* Knowledge Bases for Amazon Bedrock: provides foundation models contextual information from data sources, such as OpenSearch clusters, using Retrieval-Augmented Generation (RAG)

## Pre-requisites  

* AWS Command Line Interface (AWS CLI)
* Terraform
* Amazon Bedrock model access enabled for Anthropic Claude 3 Sonnet and Amazon Titan Embeddings G1 in us-east-1
* jq and git
* curl and time commands (installed by default in Mac and Linux systems)
* Python3.11 with pip. The Python runtime can be changed to other versions in the lambda module definition within the main.tf file. _python3.11 -m ensurepip_ can be used to install pip for Python3.11 

## Installation

1. Clone repo
```
git clone https://github.com/aws-samples/amazon-memorydb-for-redis-samples.git
```

2. Init terraform and apply plan. This will create the infrastructure for the components of the solution. Note that a role with permission to create the resources outlined in the main.tf plan (for example, one with the _administrator_ policy), is required.

```
cd amazon-memorydb-for-redis-samples/blogs/optimizing-gen-ai-apps-with-durable-semantic-cache/terraform
terraform init
terraform apply --auto-approve
```

3. Setup knowledge base

The knowledge base is created as part of the terraform plan, but files need to be uploaded to S3 and the ingestion job started

Get the terraform outputs
```
export DATA_SOURCE_ID=$(terraform output -raw data_source_id | cut -d, -f1)
echo "DATA_SOURCE_ID: $DATA_SOURCE_ID"
export KNOWLEDGE_BASE_ID=$(terraform output -raw knowledge_base_id)
echo "KNOWLEDGE_BASE_ID: $KNOWLEDGE_BASE_ID"
export S3_BUCKET_NAME=$(terraform output -raw s3_bucket)
echo "Bucket: $S3_BUCKET_NAME"

```

Upload docs and start the ingestion job. If the commands return an error related to not enough permissions, make sure that you are using the correct role with _aws sts get-caller-identity_
```
aws s3 cp ../knowledgeBaseContent/ s3://$S3_BUCKET_NAME --recursive
export INGESTION_JOB_ID=$(aws bedrock-agent start-ingestion-job --data-source-id $DATA_SOURCE_ID --knowledge-base-id $KNOWLEDGE_BASE_ID --region us-east-1 | jq .ingestionJob.ingestionJobId -r)

```

Query the ingestion job. It might take several minutes until it shows COMPLETE status

```
aws bedrock-agent get-ingestion-job \
--data-source-id $DATA_SOURCE_ID --knowledge-base-id \
$KNOWLEDGE_BASE_ID --ingestion-job-id $INGESTION_JOB_ID \
--region us-east-1 | jq .ingestionJob.status
```

Example output once it is completed

```
"COMPLETE"
```

## Usage

When the ingestion job is done, execute calls to the API to test the persistent semantic cache

1. Get the API ID and access key
```
export API_ID=$(terraform output -raw api_id)
export API_KEY_ID=$(terraform output -raw api_key_id)
export API_KEY_VALUE=$(aws apigateway get-api-key --api-key $API_KEY_ID \
--include-value | jq -r .value)
```

2. Execute API call. The _time_ command provides metrics on how much the API request takes to be served

Customize time format output
```
export TIMEFMT='                   
%*E seconds total'
```

Execute the API call

```
time curl --request POST \
  --url https://$API_ID.execute-api.us-east-1.amazonaws.com/dev/answer \
  --header 'Content-Type: application/json' --header "x-api-key: ${API_KEY_VALUE}" \
  --data '{"question":"What is the operational excellence pillar?"}'
```

It can take several seconds the first time it is executed. However, the second and subsequent times takes less time (milliseconds) since it is stored in the persistent cache after the first answer. For example:

First time executed latency: 9.561 seconds
```
time curl --request POST \    
  --url https://$API_ID.execute-api.us-east-1.amazonaws.com/dev/answer \
  --header 'Content-Type: application/json' --header "x-api-key: ${API_KEY_VALUE}" \
  --data '{"question":"What is the operational excellence pillar?"}'
```

Output:

```
{"answer": "The Operational Excellence pillar (...)"}
9.561 seconds total
```

Second time executed latency: 0.610 seconds
```
 % time curl --request POST \
  --url https://$API_ID.execute-api.us-east-1.amazonaws.com/dev/answer \
  --header 'Content-Type: application/json' --header "x-api-key: ${API_KEY_VALUE}" \
  --data '{"question":"What is the operational excellence pillar?"}'
```

Output
```
{"answer": "The Operational Excellence pillar (...)"}
0.610 seconds total
```

Since it is a persistent semantic cache, queries that are semantically similar to a previous one are also found in the cache. For example, the answer to the question "Tell me more about the operational excellence pillar" is found in the cache if "What is the operational excellence pillar?" has been asked before

```
% time curl --request POST \
  --url https://$API_ID.execute-api.us-east-1.amazonaws.com/dev/answer \
  --header 'Content-Type: application/json' --header "x-api-key: ${API_KEY_VALUE}" \
  --data '{"question":"Tell me more about the operational excellence pillar"}' 
```

output

```
{"answer": "The Operational Excellence pillar (...)"}
0.339 seconds total
```


## Clean up

To avoid incurring additional charges while the solution is not being used, delete the infrastructure

```
terraform destroy --auto-approve
```