#!/usr/bin/env python
# coding: utf-8

from sentence_transformers import SentenceTransformer
import numpy as np
import pandas as pd
import redis
import json
import time
from redis.commands.search.query import Query
from redis.commands.search.field import VectorField
from redis.commands.search.field import TextField
from redis.commands.search.field import TagField
from redis.commands.search.result import Result

# Constants
INDEX_NAME = 'idx:pqa_vss'
ITEM_KEYWORD_EMBEDDING_FIELD = 'question_vector'
TEXT_EMBEDDING_DIMENSION = 768
NUMBER_PRODUCTS = 1000

# Initialize model
model = SentenceTransformer('sentence-transformers/all-distilroberta-v1')

# Initialize Redis client
def initialize_redis():
    client = redis.Redis(
        host='memoryd-rag-0001-001.memoryd-rag.ghlaqp.memorydb.us-east-1.amazonaws.com',
        port=6379, decode_responses=True, ssl=True, ssl_cert_reqs="none")
    try:
        client.ping()
        print("Connection to MemoryDB successful")
        return client
    except Exception as e:
        print("An error occurred while connecting to Redis:", e)
        return None

def loadVectorStore(client, file_name='amazon-pqa/amazon_pqa_headsets.json', number_rows=1000):
    # Load PQA data
    def load_pqa(file_name, number_rows):
        df = pd.DataFrame(columns=('question', 'answer'))
        with open(file_name) as f:
            for i, line in enumerate(f):
                if i == number_rows:
                    break
                data = json.loads(line)
                df.loc[i] = [data['question_text'], data['answers'][0]['answer_text']]
        return df

    # Create vector embeddings for questions
    def create_embeddings(qa_list):
        item_keywords = [qa['question'] for qa in qa_list.to_dict(orient='index').values()]
        return [model.encode(sentence) for sentence in item_keywords]

    # Load vectors into Redis
    def load_vectors(client, qa_list, vector_dict):
        for index, qa in qa_list.iterrows():
            key = f'product:{index}'
            item_keywords_vector = vector_dict[index].astype(np.float32).tobytes()
            qa[ITEM_KEYWORD_EMBEDDING_FIELD] = item_keywords_vector
            client.hset(key, mapping=qa.to_dict())

    # Start timing for vector loading
   # start_time = time.time()
    qa_list = load_pqa(file_name, number_rows)
    product_metadata = qa_list.head(NUMBER_PRODUCTS).to_dict(orient='index')
    item_keywords_vectors = create_embeddings(qa_list)
    start_time = time.time()
    load_vectors(client, qa_list, item_keywords_vectors)
    end_time = time.time()

    print(f'Loading and Indexing {NUMBER_PRODUCTS} products completed in {end_time - start_time:.2f} seconds')

    # Start timing for index creation
    start_time = time.time()
    create_index_command = "FT.CREATE idx:pqa_vss SCHEMA question_vector VECTOR HNSW 10 TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE INITIAL_CAP 1000 M 40 question TEXT answer TEXT"
    try:
        response = client.execute_command(create_index_command)
        end_time = time.time()
        print("Index created successfully in {:.2f} seconds:".format(end_time - start_time), response)
    except Exception as e:
        print("An error occurred while creating the index:", e)

def check_index_existence(client):
    try:
        info = client.ft(INDEX_NAME).info()
        num_docs = info.get('num_docs', 'N/A')
        space_usage = info.get('space_usage', 'N/A')
        num_indexed_vectors = info.get('num_indexed_vectors', 'N/A')
        vector_space_usage = info.get('vector_space_usage', 'N/A')
        index_details = {
            'num_docs': num_docs,
            'space_usage': space_usage,
            'num_indexed_vectors': num_indexed_vectors,
            'vector_space_usage': vector_space_usage,
            'exists': True
        }
        return index_details
    except Exception:
        return {'exists': False}

# Function to process a question
def process_question(client, query):
    topK = 5  # Number of top results to retrieve
    query_vector = model.encode(query).astype(np.float32).tobytes()
    q = Query(f'*=>[KNN {topK} @{ITEM_KEYWORD_EMBEDDING_FIELD} $vec_param AS vector_score]').paging(0, topK).return_fields('question', 'answer')
    params_dict = {"vec_param": query_vector}
    results = client.ft(INDEX_NAME).search(q, query_params=params_dict)
    data = [{'Hash Key': doc.id, 'Question': doc.question, 'Answer': doc.answer} for doc in results.docs]
    return pd.DataFrame(data)


