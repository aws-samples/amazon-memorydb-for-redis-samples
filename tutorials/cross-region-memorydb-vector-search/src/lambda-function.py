import os
import redis
from redis.commands.search.field import VectorField, TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.cluster import RedisCluster
from redis.exceptions import ResponseError
from typing import Dict, Tuple, Union, List
from urllib.parse import ParseResult, urlencode, urlunparse
import botocore.session
from botocore.model import ServiceId
from botocore.signers import RequestSigner
import logging
import random
import struct
import json
import uuid
import time

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class MemoryDBIAMProvider(redis.CredentialProvider):
    def __init__(self, user, cluster_name, region):
        self.user = user
        self.cluster_name = cluster_name
        self.region = region

        self.session = botocore.session.get_session()
        self.credentials = self.session.get_credentials()
        self.request_signer = RequestSigner(
            ServiceId("memorydb"),
            self.region,
            "memorydb",
            "v4",
            self.credentials,
            self.session.get_component("event_emitter"),
        )
        logger.info(f"Initialized MemoryDBIAMProvider for user: {user}, cluster: {cluster_name}, region: {region}")

    def get_credentials(self) -> Union[Tuple[str], Tuple[str, str]]:
        query_params = {"Action": "connect", "User": self.user}
        url = urlunparse(
            ParseResult(
                scheme="https",
                netloc=self.cluster_name,
                path="/",
                query=urlencode(query_params),
                params="",
                fragment="",
            )
        )
        logger.info(f"Generated URL for credentials: {url}")
        
        try:
            signed_url = self.request_signer.generate_presigned_url(
                {"method": "GET", "url": url, "body": {}, "headers": {}, "context": {}},
                operation_name="connect",
                expires_in=900,
                region_name=self.region,
            )
            logger.info("Successfully generated presigned URL")
            return (self.user, signed_url.removeprefix("https://"))
        except Exception as e:
            logger.error(f"Error generating presigned URL: {str(e)}")
            raise

def generate_random_vector(dimensions: int) -> List[float]:
    """Generate a random vector with specified dimensions."""
    return [random.random() for _ in range(dimensions)]

def create_index_if_not_exists(r: RedisCluster, index_name: str, vector_dimensions: int) -> None:
    """Create a Redis search index if it doesn't exist."""
    try:
        # Check if index exists
        r.ft(index_name).info()
        logger.info(f"Index {index_name} already exists")
    except ResponseError:
        # Index doesn't exist, create it
        schema = (
            VectorField("content_vector", "FLOAT32", vector_dimensions, "FLAT", {
                "TYPE": "FLOAT32",
                "DIM": vector_dimensions,
                "DISTANCE_METRIC": "COSINE"
            }),
            TextField("metadata")
        )
        definition = IndexDefinition(prefix=[b"vector:"], index_type=IndexType.HASH)
        r.ft(index_name).create_index(schema, definition=definition)
        logger.info(f"Created index {index_name}")

def establish_redis_connection(conn_params: dict, max_retries: int = 3) -> RedisCluster:
    """Establish Redis connection with retry logic."""
    last_exception = None
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to Redis (attempt {attempt + 1}/{max_retries})")
            r = RedisCluster(**conn_params)
            if r.ping():
                logger.info("Connected to Redis successfully")
                return r
        except Exception as e:
            last_exception = e
            logger.warning(f"Connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)
    
    raise last_exception

def insert_vectors(r: RedisCluster, index_dimensions: int, num_vectors: int = 10) -> List[bytes]:
    """Insert random vectors into Redis."""
    created_vectors = []
    try:
        for i in range(num_vectors):
            vector_id = f"vector:{uuid.uuid4()}".encode('utf-8')
            vector_data = generate_random_vector(index_dimensions)
            
            # Pack vector data as binary
            packed_vector = struct.pack(f'{index_dimensions}f', *vector_data)
            
            # Create mapping with required fields
            mapping = {
                b"content_vector": packed_vector,
                b"metadata": f"Random vector {i+1}".encode('utf-8')
            }
            
            r.hset(vector_id, mapping=mapping)
            created_vectors.append(vector_id)
        return created_vectors
    except Exception as e:
        logger.error(f"Error inserting vectors: {str(e)}")
        raise

def perform_vector_search(r: RedisCluster, index_name: str, index_dimensions: int, k: int = 5) -> tuple:
    """Perform a test vector search."""
    try:
        test_vector = generate_random_vector(index_dimensions)
        query = f"*=>[KNN {k} @content_vector $vector AS score]"
        
        # Pack the vector data
        packed_vector = struct.pack(f'{index_dimensions}f', *test_vector)
        
        results = r.ft(index_name).search(
            query, 
            {'vector': packed_vector}
        )
        
        search_results = []
        for doc in results.docs:
            result = {
                "Doc ID": doc.id.decode('utf-8') if isinstance(doc.id, bytes) else doc.id,
                "Score": getattr(doc, 'score', 0.0),
                "Metadata": getattr(doc, 'metadata', '').decode('utf-8') if isinstance(getattr(doc, 'metadata', ''), bytes) else getattr(doc, 'metadata', 'N/A')
            }
            search_results.append(result)
        
        return results.total, search_results
    except Exception as e:
        logger.error(f"Error in vector search: {str(e)}")
        raise

def lambda_handler(event, context):
    r = None
    try:
        # Ensure environment variables are valid
        redis_host = os.environ.get('REDIS_HOST')
        redis_port = os.environ.get('REDIS_PORT')
        redis_username = os.environ.get('REDIS_USERNAME')
        redis_cluster_name = os.environ.get('REDIS_CLUSTER_NAME')
        redis_region = os.environ.get('REDIS_REGION')
        redis_index_name = os.environ.get('REDIS_INDEX_NAME')
        redis_index_dimensions = os.environ.get('REDIS_INDEX_DIMENSIONS')

        # Validate and handle missing/empty environment variables
        if not all([redis_host, redis_port, redis_username, redis_cluster_name, redis_region, redis_index_name, redis_index_dimensions]):
            raise ValueError("One or more required environment variables are missing or empty.")

        # Convert to integers with validation
        try:
            redis_port = int(redis_port)
            redis_index_dimensions = int(redis_index_dimensions)
        except ValueError as ve:
            raise ValueError(f"Invalid numerical values: {ve}")

        logger.info(f"Redis parameters: {redis_host}, {redis_port}, {redis_username}, {redis_cluster_name}, {redis_region}, {redis_index_name}, {redis_index_dimensions}")

        # Create a strong reference to MemoryDBIAMProvider
        creds_provider = MemoryDBIAMProvider(
            user=redis_username,
            cluster_name=redis_cluster_name,
            region=redis_region
        )

        redis_conn_params = {
            'host': redis_host,
            'port': redis_port,
            'ssl': True,
            'ssl_cert_reqs': "none",
            'decode_responses': False,
            'credential_provider': creds_provider
        }

        # Establish connection with retry logic
        r = establish_redis_connection(redis_conn_params)

        # Create index if it doesn't exist
        create_index_if_not_exists(r, redis_index_name, redis_index_dimensions)

        # Insert some test vectors
        created_vectors = insert_vectors(r, redis_index_dimensions)
        # Decode binary data for logging
        created_vectors_decoded = [v.decode('utf-8') if isinstance(v, bytes) else v for v in created_vectors]
        logger.info(f"Created and inserted vectors: {created_vectors_decoded}")

        # Perform a test search
        total_results, search_results = perform_vector_search(r, redis_index_name, redis_index_dimensions)
        logger.info(f"Search completed with {total_results} results")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Operations completed successfully',
                'created_vectors': created_vectors_decoded,
                'search_results': {
                    'total': total_results,
                    'results': search_results
                }
            })
        }

    except Exception as e:
        logger.error(f'Error: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'An error occurred',
                'error': str(e)
            })
        }
    finally:
        if r:
            try:
                r.close()
                logger.info("Redis connection closed successfully")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {str(e)}")
