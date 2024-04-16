# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from flask import Flask, request
from flask_restful import Resource, Api, abort
from rediscluster import RedisCluster
import certifi
import logging
import os
import uuid

host = os.environ['HOST']
port = os.environ['PORT']
db_host = os.environ['DB_HOST']
db_port = os.environ['DB_PORT']
db_username = os.environ['DB_USERNAME']
db_password = os.environ['DB_PASSWORD']

logging.basicConfig(level=logging.INFO)

redis = RedisCluster(startup_nodes=[{
            "host": db_host, 
            "port": db_port
        }],
        decode_responses=True, 
        skip_full_coverage_check=True,
        ssl=True, 
        ssl_ca_certs=certifi.where(),
        username=db_username, 
        password=db_password
)

if redis.ping():
    logging.info("Connected to Redis")

app = Flask(__name__)
api = Api(app)


class Customers(Resource):

    def get(self):
        key_mask = "customer:*"
        customers = []
        for key in redis.scan_iter(key_mask):
            customer_id = key.split(':')[1]
            customer = redis.hgetall(key)
            customer['id'] = customer_id
            customers.append(customer)
        return customers

    def post(self):
        print(request.json)
        customer_id = str(uuid.uuid4())
        key = "customer:" + customer_id
        redis.hset(key, mapping=request.json)
        customer = request.json
        customer['id'] = customer_id
        return customer, 201


class Customers_ID(Resource):

    def get(self, customer_id):
        key = "customer:" + customer_id
        customer = redis.hgetall(key)
        print(customer)
        if customer:
            customer['id'] = customer_id
            return customer
        else:
            abort(404)

    def put(self, customer_id):
        print(request.json)
        key = "customer:" + customer_id
        redis.hset(key, mapping=request.json)
        return '', 204

    def delete(self, customer_id):
        key = "customer:" + customer_id
        redis.delete(key)
        return '', 204


api.add_resource(Customers, '/customers')
api.add_resource(Customers_ID, '/customers/<customer_id>')


if __name__ == '__main__':
    app.run(host=host, port=port)
