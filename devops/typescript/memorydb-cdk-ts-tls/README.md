# Amazon MemoryDB using CDK for TypeScript

This is an [Amazon MemoryDB](https://aws.amazon.com/memorydb/) project for CDK development with TypeScript.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

## Prerequisites
You need to have the following on your laptop:

- An [AWS account](https://console.aws.amazon.com/console/home?nc2=h_ct&src=header-signin).
- The [AWS Command Line Interface](http://aws.amazon.com/cli) (AWS CLI) [installed](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).
- The AWS CDK [installed](https://github.com/aws/aws-cdk). For instructions, refer to [Configure the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-configure.html). 
- [Node.js 16.14.0 or later](https://nodejs.org/en).

## Deployment

### AWS CDK
```bash
# 1.	Enter the following command in a terminal:
npm install -g aws-cdk
# 2.	Validate the installation with the following command:
cdk --version
```

### MemoryDB with CDK
```bash
# Clone this repo
git clone git@github.com:aws-samples/amazon-memorydb-for-redis-samples.git
# Go to CDK folder
cd amazon-memorydb-for-redis-samples/devops/aws-cdk/typescript/memorydb-cdk-ts-tls
# Install the NPM packages
npm install
# Prepare the environment in the configured AWS region
cdk bootstrap
# Create the AWS CloudFormation template by running the following command
cdk synth
# Create the VPC by entering the following command. The --require-approval option bypasses the prompt for approval
cdk deploy --require-approval never
```

## Useful commands

* `npm run build`   compile typescript to js
* `npm run watch`   watch for changes and compile
* `npm run test`    perform the jest unit tests
* `npx cdk deploy`  deploy this stack to your default AWS account/region
* `npx cdk diff`    compare deployed stack with current state
* `npx cdk synth`   emits the synthesized CloudFormation template
