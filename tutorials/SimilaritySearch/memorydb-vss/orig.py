#!/usr/bin/env python
# coding: utf-8

from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/all-distilroberta-v1')

import random
import numpy as np
import pandas as pd
import time
import redis
from redis.commands.search.field import VectorField
from redis.commands.search.field import TextField
from redis.commands.search.field import TagField
from redis.commands.search.query import Query
from redis.commands.search.result import Result
import json
from tqdm.contrib.concurrent import process_map
from multiprocessing import cpu_count
import redis


# ## Check connection to MemoryMind  and cleanup data if needed (Only sample dont run FLUSHALL in production) 

# Execute a function or print statement from the custom script here
# For example, if there's a function named `initial_message` in PQA-semanticsearch.py

client_devo = redis.Redis(host = 'my-vss1-0001-001.my-vss1.4hme9t.memorydb-devo.us-east-1.amazonaws.com', port=6379, 
                     decode_responses=True, ssl=True, ssl_cert_reqs="none"
                      )
response1=client_devo.ping()
try:
    response1 = client_devo.ping()
    print("Connection to MemoryMind  successfull:", response1)
except Exception as e:
    print("An error occurred while creating the index:", e)

#client_devo.flushall()


#  ##  Copy the data set locally.
# Before we can run any queries, we need to download the Amazon Product Question and Answer data from : https://registry.opendata.aws/amazon-pqa/
# #### Let's start by having a look at all the files in the dataset. Uncomment the below line to list all options 

#!aws s3 ls --no-sign-request s3://amazon-pqa/


# There are a lot of files here, so for the purposes of this demo, we focus on just the headset data. Let's download the amazon_pqa_headsets.json data locally.


# ### Prepare Headset PQA data

def load_pqa(file_name,number_rows=1000):
    qa_list = []
    df = pd.DataFrame(columns=('question', 'answer'))
    with open(file_name) as f:
        i=0
        for line in f:
            data = json.loads(line)
            df.loc[i] = [data['question_text'],data['answers'][0]['answer_text']]
            i+=1
            if(i == number_rows):
                break
    return df


qa_list = load_pqa('amazon-pqa/amazon_pqa_headsets.json',number_rows=1000)

NUMBER_PRODUCTS=1000
product_metadata = qa_list.head(NUMBER_PRODUCTS).to_dict(orient='index')


### Create vector embeddings for questions 

import time
start_time = time.time() # Start timer
item_keywords =  [product_metadata[i]['question']  for i in product_metadata.keys()]
item_keywords_vectors = [model.encode(sentence) for sentence in item_keywords]

from redis.client import Redis


ITEM_KEYWORD_EMBEDDING_FIELD='question_vector'


# ## Function to load the question, answer data with vector embeddings

def load_vectors(client: Redis, qa_list, vector_dict, vector_field_name):
    for index in product_metadata.keys():    
        # Hash key
        key = 'product:' + str(index)
        
        # Hash values
        item_metadata = product_metadata[index]
        item_keywords_vector = vector_dict[index].astype(np.float32).tobytes()
        item_metadata[vector_field_name] = item_keywords_vector
        
        # HSET
        client.hset(key, mapping=item_metadata)


# ### The below function is to create the Vector index. 
#  However redis-py does not allow index creation because of unsupported fields in preview. so run this with MONITOR if you want a sample command for FT.CREATE

# def create_hnsw_index (redis_conn,vector_field_name,number_of_vectors, vector_dimensions=512, distance_metric='L2',M=40,EF=200):
#     redis_conn.ft(INDEX_NAME).create_index([
#         VectorField(vector_field_name, "HNSW", {"TYPE": "FLOAT32", "DIM": vector_dimensions, "DISTANCE_METRIC": distance_metric, "INITIAL_CAP": number_of_vectors, "M": M, }),
#         TagField("question_vector"),
#         TextField("question"),        
#         TextField("answer"),
#           
#     ])    
# 

## Run the below code to actually load the hashes in 

INDEX_NAME='idx:pqa_vss'
ITEM_KEYWORD_EMBEDDING_FIELD='question_vector'
TEXT_EMBEDDING_DIMENSION=768
NUMBER_PRODUCTS=1000

print ('Loading and Indexing + ' +  str(NUMBER_PRODUCTS) + ' products')

#flush all data
load_vectors(client_devo,product_metadata,item_keywords_vectors,ITEM_KEYWORD_EMBEDDING_FIELD)


# 
# ## Create index manually using below command with redis-cli 
# 
# ``` bash
# FT.CREATE idx:pqa_vss SCHEMA question_vector VECTOR HNSW 10 TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE INITIAL_CAP 1000 M 40 question TEXT answer TEXT
# 
# ```
#  

# In[37]:


INDEX_NAME='idx:pqa_vss'
# Command to create the index
create_index_command = "FT.CREATE idx:pqa_vss SCHEMA question_vector VECTOR HNSW 10 TYPE FLOAT32 DIM 768 DISTANCE_METRIC COSINE INITIAL_CAP 1000 M 40 question TEXT answer TEXT"

# Execute the command
try:
    response = client_devo.execute_command(create_index_command)
    print("Index created successfully:", response)
except Exception as e:
    print("An error occurred while creating the index:", e)

# ### Run FT.INFO to inspect the index 

info = client_devo.ft(INDEX_NAME).info()
num_docs = info['num_docs']
space_usage = info['space_usage']
num_indexed_vectors = info['num_indexed_vectors']
vector_space_usage = (info['vector_space_usage'])

print(f"{num_docs} documents ({space_usage} space used vectors indexed {num_indexed_vectors} vector space usage in {vector_space_usage}")


# ### Performing Semantic search.. broken down into multiple cells to capture execution time effectively can all be run from 1 cell as well 
import time

def process_question(product_query):
    # Assuming `model`, `Query`, `client_devo`, `ITEM_KEYWORD_EMBEDDING_FIELD`, and `INDEX_NAME` are already defined and imported

    topK = 5  # Number of top results to retrieve

    # Vectorize the query
    query_vector = model.encode(product_query).astype(np.float32).tobytes()

    # Start timer to measure execution time
    start_time = time.time()

    # Prepare the query
    q = Query(f'*=>[KNN {topK} @{ITEM_KEYWORD_EMBEDDING_FIELD} $vec_param AS vector_score]').paging(0, topK).return_fields('question', 'answer')
    params_dict = {"vec_param": query_vector}

    # Execute the query
    results = client_devo.ft(INDEX_NAME).search(q, query_params=params_dict)

    # Calculate execution time
    execution_time = (time.time() - start_time) * 1000  # Convert time difference to milliseconds
    print(f"Execution time for search query : {execution_time:.2f} milliseconds")

    data = []
    for product in results.docs:
        data.append({
            'Hash Key': product.id,
            'Question': product.question,
            'Answer': product.answer
        })
    results_df = pd.DataFrame(data)

    return results_df
    # Process and return results
    # Depending on the format of 'results', you may need to format them before returning
   # return results





