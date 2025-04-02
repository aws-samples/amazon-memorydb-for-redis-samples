import numpy as np
import pandas as pd
import json
import time
import os
import logging
from sentence_transformers import SentenceTransformer
import redis


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
INDEX_NAME = 'idx:pqa_vss'
ITEM_KEYWORD_EMBEDDING_FIELD = 'question_vector'
TEXT_EMBEDDING_DIMENSION = 768
NUMBER_PRODUCTS = 1000
MEMORYDB_CLUSTER = os.environ.get("MEMORYDB_CLUSTER")

# Initialize model
model = SentenceTransformer('sentence-transformers/all-distilroberta-v1')

def initialize_redis():
    try:
        logging.info(f"Attempting to connect to MemoryDB at {MEMORYDB_CLUSTER}")
        client = redis.Redis(
            host=MEMORYDB_CLUSTER,
            port=6379,
            decode_responses=False,
            ssl=True,
            ssl_cert_reqs="none"
        )
        client.ping()
        logging.info("Connection to MemoryDB successful")
        return client
    except Exception as e:
        logging.error(f"An error occurred while connecting to Redis: {e}")
        return None

def loadVectorStore(client, file_name='amazon-pqa/amazon_pqa_headsets.json', number_rows=1000):
    def load_pqa(file_name, number_rows):
        logging.info(f"Loading PQA data from {file_name}")
        df = pd.DataFrame(columns=('question', 'answer'))
        with open(file_name) as f:
            for i, line in enumerate(f):
                if i == number_rows:
                    break
                data = json.loads(line)
                df.loc[i] = [data['question_text'], data['answers'][0]['answer_text']]
        logging.info(f"Loaded {len(df)} rows of PQA data")
        return df

    def create_embeddings(qa_list):
        logging.info("Creating embeddings for questions")
        item_keywords = [qa['question'] for qa in qa_list.to_dict(orient='index').values()]
        return [model.encode(sentence) for sentence in item_keywords]

    def load_vectors(client, qa_list, vector_dict):
        logging.info("Loading vectors into Redis")
        for index, qa in qa_list.iterrows():
            key = f'product:{index}'
            item_keywords_vector = vector_dict[index].astype(np.float32).tobytes()
            client.hset(key, ITEM_KEYWORD_EMBEDDING_FIELD, item_keywords_vector)
            client.hset(key, 'question', qa['question'].encode('utf-8'))
            client.hset(key, 'answer', qa['answer'].encode('utf-8'))
        logging.info(f"Loaded {len(qa_list)} vectors into Redis")

    qa_list = load_pqa(file_name, number_rows)
    item_keywords_vectors = create_embeddings(qa_list)
    start_time = time.time()
    load_vectors(client, qa_list, item_keywords_vectors)
    end_time = time.time()

    logging.info(f'Loading {NUMBER_PRODUCTS} products completed in {end_time - start_time:.2f} seconds')

def check_index_existence(client):
    keys = client.keys(b'product:*')
    result = {'exists': len(keys) > 0, 'num_docs': len(keys)}
    logging.info(f"Index check result: {result}")
    return result

def process_question(client, query):
    logging.info(f"Processing question: {query}")
    query_vector = model.encode(query).astype(np.float32)
    
    results = []
    for key in client.keys(b'product:*'):
        product_data = client.hgetall(key)
        if ITEM_KEYWORD_EMBEDDING_FIELD.encode('utf-8') in product_data:
            product_vector = np.frombuffer(product_data[ITEM_KEYWORD_EMBEDDING_FIELD.encode('utf-8')], dtype=np.float32)
            similarity = np.dot(query_vector, product_vector) / (np.linalg.norm(query_vector) * np.linalg.norm(product_vector))
            question = product_data[b'question'].decode('utf-8')
            answer = product_data[b'answer'].decode('utf-8')
            results.append((key, similarity, question, answer))
    
    results.sort(key=lambda x: x[1], reverse=True)
    top_results = results[:5]  # Get top 5 results
    
    data = [{'Hash Key': key.decode('utf-8'), 'Similarity': sim, 'Question': q, 'Answer': a} for key, sim, q, a in top_results]
    logging.info(f"Found {len(results)} results for the query")
    return pd.DataFrame(data)
