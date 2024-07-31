import boto3
import json
import logging
import sys
import traceback
from redis.cluster import RedisCluster
from redis.commands.search.field import TagField, VectorField, TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
import numpy as np
import sys
import os
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

# Setup logging
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(stdout_handler)

patch_all()

redis_client = RedisCluster(host=os.getenv("PERISTENT_SEMANTIC_CACHE_ENDPOINT"), 
                            port=6379,
                            ssl=True)
redis_client.ping()
logger.info("Connection to Amazon MemoryDB successful")

INDEX_NAME = "bedrock"                              # Vector Index Name
DOC_PREFIX = "doc:"                               # RediSearch Key Prefix for the Index
knowledge_base_id = os.getenv("KNOWLEDGE_BASE_ID")
model_id = 'anthropic.claude-3-sonnet-20240229-v1:0'

# Bedrock Runtime client used to invoke and question the models
bedrock_client = boto3.client('bedrock-runtime',region_name="us-east-1")
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime',region_name="us-east-1")

def setup_index():
    """
    Creates the index if it doesn't exist
    """
    global redis_client
    global INDEX_NAME
    global DOC_PREFIX
    logger.info(f"Creating index {INDEX_NAME}")
    try:
        # check to see if index exists
        redis_client.ft(INDEX_NAME).info()
        logger.info("Index already exists!")
    except:
        # schema
        schema = (
            TextField("answer"),
            TagField("tag"),                       # Tag Field Name
            VectorField("vector",                  # Vector Field Name
                "HNSW", {                          # Vector Index Type: FLAT or HNSW
                    "TYPE": "FLOAT32",             # FLOAT32 or FLOAT64
                    "DIM": 1536,      # Number of Vector Dimensions
                    "DISTANCE_METRIC": "COSINE",   # Vector Search Distance Metric
                }
            ),
        )
        # index Definition
        definition = IndexDefinition(prefix=[DOC_PREFIX], index_type=IndexType.HASH)
        # create Index
        redis_client.ft(INDEX_NAME).create_index(fields=schema, definition=definition)


setup_index()

def lookup_cache_range(user_question_embedding):
    """
    Looks up the cache for similar questions based on the provided embedding.
    :param user_question_embedding: The embedding vector for the user's question.
    :return: A list of dictionaries containing the closest matching questions and their embeddings.
    """
    global redis_client
    global INDEX_NAME
    logger.info(f"Looking for question in cache using index: {INDEX_NAME}")
    
    question_embedding = np.array(user_question_embedding,dtype=np.float32).tobytes()
    q = Query('@vector:[VECTOR_RANGE $radius $vec]=>{$YIELD_DISTANCE_AS: score}').paging(0, 1).dialect(2).return_fields("answer","tag", "score")
    query_params = {
        "radius": 0.4,
        "vec": question_embedding
    }
    xray_recorder.begin_subsegment('cache_query')
    response = redis_client.ft(INDEX_NAME).search(q, query_params).docs
    xray_recorder.end_subsegment()
    return response

def add_to_cache(user_question,user_question_embedding, answer):
    question_embedding = np.array(user_question_embedding,dtype=np.float32).tobytes()
    key = f'doc:{hash(user_question) % 2**sys.hash_info.width}'
    xray_recorder.begin_subsegment('add_to_cache')
    redis_client.hset(key, mapping = {
        "vector": question_embedding,
        "answer": answer,
        "tag": "amazon.titan-embed-text-v1"
    })
    xray_recorder.end_subsegment()
    

def get_embedding(text_content):
    """
    Generates embeddings for a given piece of text using the Bedrock service.
    :param text_content: The text content for which to generate embeddings.
    :return: Embedding vector or None if an error occurs.
    """
    try:
        body_content = json.dumps({"inputText": text_content})
        response = bedrock_client.invoke_model(
            body=body_content,
            contentType="application/json",
            accept="*/*",
            modelId="amazon.titan-embed-text-v1"
        )
        # Assuming the response content is in JSON format
        response_body = json.loads(response.get('body').read())
        embedding = response_body.get('embedding')  # Adjust based on your actual response structure
        return embedding
    except Exception as e:
        logger.info(f"Error generating embedding: {e}")
        logger.info(traceback.format_exc())
        raise e


def answer_question_with_model(user_question):
    """
    Answers the user's question using a foundation model.
    :param user_question: The question asked by the user.
    :return: The answer provided by the model.
    """
    global bedrock_agent_runtime
    response = bedrock_agent_runtime.retrieve_and_generate(
        input= {
            'text': user_question
        },
        retrieveAndGenerateConfiguration={
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": knowledge_base_id,
                "modelArn": model_id,
                "retrievalConfiguration":{
                    'vectorSearchConfiguration': {
                        'numberOfResults': 5,
                        'overrideSearchType':'HYBRID'
                    }
                }
            },
            "type": "KNOWLEDGE_BASE"
        }
    )

    answer = response['output']['text']
    return answer

def lambda_handler(event, context):
    logger.info("Recieved new request")
    #logger.info(f"Event: {json.dumps(event['requestContext'])}")
    response_lambda = {
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': '*',
            'Access-Control-Allow-Headers': '*'
        }
    }
    body = event.get("body")
    
    body = json.loads(body)
    user_question = body['question']

    answer = None
    logger.info("Getting embedding")
    xray_recorder.begin_subsegment('get_user_question_embedding')
    user_question_embedding = get_embedding(user_question)
    xray_recorder.end_subsegment()
    cache_hits = lookup_cache_range(user_question_embedding)
    if len(cache_hits) > 0:
        if cache_hits[0]['answer'] is not None:
            logger.info("Using a cached answer")
            answer = cache_hits[0]['answer']

    if answer is None:
        xray_recorder.begin_subsegment('answer_question_with_model')
        answer = answer_question_with_model(user_question)
        xray_recorder.end_subsegment()
        logger.info("Adding response to cache")
        add_to_cache(user_question,user_question_embedding,answer)
        
    response_lambda['statusCode'] = 200
    response_lambda['body'] = json.dumps({"answer":answer})    
    return response_lambda


