# Cross-Region Vector Search with MemoryDB for Redis and Lambda

This tutorial demonstrates how to securely connect a Lambda function to Amazon MemoryDB for Redis across regions using IAM authentication.

## Prerequisites

* AWS Account with appropriate permissions
* Two VPCs (one in each region) connected via Transit Gateway
* Python 3.9 or later
* AWS CLI configured with appropriate credentials

## Package Management and Deployment

1. Create a new directory for your project:
```bash
mkdir vector-search-project
cd vector-search-project
```

2. Create virtual environment:
```bash 
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Create requirements.txt with the following content:
```bash 
redis==5.0.1
redis-cluster==2.1.3
boto3==1.34.0
botocore==1.34.0
urllib3==1.26.18
hiredis==2.2.3
```

4. Install dependencies and create deployment package:
```bash
# Install requirements
pip install -r requirements.txt

# Create deployment package
mkdir package
pip install --target ./package -r requirements.txt
cd package
zip -r ../deployment-package.zip .
cd ..
zip deployment-package.zip lambda_function.py
```

5. Deploy the package to Lambda:
```bash
aws lambda update-function-code \
    --function-name vector-search-function \
    --zip-file fileb://deployment-package.zip \
    --region us-west-1

```

## Step 1: Create MemoryDB ACL

```bash
aws memorydb create-acl \
    --acl-name "lambda-acl" \
    --user-names "lambda-user" \
      --region us-east-1
```

## Step 2: Create MemoryDB User

```bash
aws memorydb create-user \
    --user-name "lambda-user" \
    --authentication-mode "IAM" \
    --access-string "on ~* &* +@all" \
    --region us-east-1
```

## Step 3: Create MemoryDB Cluster
```bash
aws memorydb create-cluster \
    --cluster-name vector-search-cluster \
    --acl-name "lambda-acl" \
    --node-type db.t4g.small \
    --num-shards 2 \
    --num-replicas-per-shard 1 \
    --tls-enabled \
    --region us-east-1 \
    --subnet-group your-subnet-group
```

## Step 4: Create IAM Role for Lambda
Create a role with the following policies:

	AWSLambdaVPCAccessExecutionRole
	Custom policy for MemoryDB:

```bash
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "memorydb:Connect"
            ],
            "Resource": [
                "arn:aws:memorydb:us-east-1:YOUR_ACCOUNT_ID:cluster/vector-search-cluster",
                "arn:aws:memorydb:us-east-1:YOUR_ACCOUNT_ID:user/lambda-user"
            ]
        }
    ]
}
```

## Step 5: Configure Network

1. Transit Gateway Setup

```bash
# Create Transit Gateway in us-east-1
aws ec2 create-transit-gateway \
    --description "Cross-region TG" \
    --region us-east-1

# Create Transit Gateway in us-west-1
aws ec2 create-transit-gateway \
    --description "Cross-region TG" \
    --region us-west-1

# Create peering attachment
aws ec2 create-transit-gateway-peering-attachment \
    --transit-gateway-id tgw-xxxxx \
    --peer-transit-gateway-id tgw-yyyyy \
    --peer-region us-west-1
```

2. Update route tables for both VPCs

## Step 6: Deploy Lambda Function
1. Create a Lambda function in us-west-1
2. Configure VPC settings
3. Set environment variables:

```bash 
REDIS_HOST=<your-memorydb-endpoint>
REDIS_PORT=6379
REDIS_USERNAME=lambda-user
REDIS_CLUSTER_NAME=vector-search-cluster
REDIS_REGION=us-east-1
REDIS_INDEX_NAME=vector-index
REDIS_INDEX_DIMENSIONS=384
```

## Step 7: Security Group Configuration

1. MemoryDB Security Group:
```bash 
aws ec2 create-security-group \
    --group-name memorydb-sg \
    --description "MemoryDB Security Group" \
    --vpc-id vpc-xxxxx \
    --region us-east-1

aws ec2 authorize-security-group-ingress \
    --group-id sg-xxxxx \
    --protocol tcp \
    --port 6379 \
    --source-group sg-yyyyy
```

2. Lambda Security Group:
```bash 
aws ec2 create-security-group \
    --group-name lambda-sg \
    --description "Lambda Security Group" \
    --vpc-id vpc-yyyyy \
    --region us-west-1

aws ec2 authorize-security-group-egress \
    --group-id sg-yyyyy \
    --protocol tcp \
    --port 6379 \
    --destination-group sg-xxxxx
```

Testing
1. Test Lambda function:

```bash 
aws lambda invoke \
    --function-name vector-search-function \
    --payload '{"test": "vector-search"}' \
    --region us-west-1 \
    response.json
```

2. Monitor CloudWatch Logs:
```bash 
aws logs get-log-events \
    --log-group-name /aws/lambda/vector-search-function \
    --log-stream-name <latest-stream>
```

Troubleshooting
1. Connection Issues:
	Verify Transit Gateway routes
	Check security group rules
	Validate IAM permissions
	
2. Authentication Issues:

	Verify IAM role configuration
	Check user permissions in MemoryDB ACL
	Validate environment variables
	
3. Common CloudWatch Error Messages and Solutions:

	Connection timeout: Check network configuration
	Authentication failed: Verify IAM permissions
	Cannot resolve host: Check DNS settings


## Cleanup

# Delete Lambda function
```bash 
aws lambda delete-function \
    --function-name vector-search-function \
    --region us-west-1
```
# Delete MemoryDB cluster
```bash 
aws memorydb delete-cluster \
    --cluster-name vector-search-cluster \
    --region us-east-1
```

# Delete ACL
```bash 
aws memorydb delete-acl \
    --acl-name lambda-acl \
    --region us-east-1
```

# Delete Transit Gateway setup
```bash 
aws ec2 delete-transit-gateway-peering-attachment \
    --transit-gateway-attachment-id tgw-attach-xxxxx
```

# Delete security groups
```bash 
aws ec2 delete-security-group \
    --group-id sg-xxxxx \
    --region us-east-1

aws ec2 delete-security-group \
    --group-id sg-yyyyy \
    --region us-west-1
```
