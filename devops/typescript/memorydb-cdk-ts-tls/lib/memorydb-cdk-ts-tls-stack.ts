import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as EC2 from "aws-cdk-lib/aws-ec2";

export class MemorydbCdkTsTlsStack extends cdk.Stack {
    private vpc: EC2.Vpc;
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);
        const memoryDBVpc = "memorydb-vpc";
        this.vpc = new EC2.Vpc(this, memoryDBVpc, {
            vpcName: memoryDBVpc,
            ipAddresses: EC2.IpAddresses.cidr("192.168.0.0/24"),
            maxAzs: 2,
            natGateways: 1
        });
    }
}
