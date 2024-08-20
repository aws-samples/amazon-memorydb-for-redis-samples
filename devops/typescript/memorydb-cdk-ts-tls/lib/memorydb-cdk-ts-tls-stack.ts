import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as EC2 from "aws-cdk-lib/aws-ec2";
import * as MemoryDB from "aws-cdk-lib/aws-memorydb";
import { SecurityGroup, Peer, Port } from "aws-cdk-lib/aws-ec2";

export class MemorydbCdkTsTlsStack extends cdk.Stack {
    private vpc: EC2.Vpc;
    constructor(scope: Construct, id: string, props?: cdk.StackProps) {
        super(scope, id, props);
        const memoryDBVpc = "memorydb-vpc";
        const memorydbSubnetGroupName = "memorydb-subnet-group";
        const memorydbSecurityGroupName = "memorydb-security-group";
        const memoryDBClusterName = "memorydb-cluster";
        this.vpc = new EC2.Vpc(this, memoryDBVpc, {
            vpcName: memoryDBVpc,
            ipAddresses: EC2.IpAddresses.cidr("192.168.0.0/24"),
            maxAzs: 2,
            natGateways: 1
        });
        const privateSubnetIds = this.vpc.privateSubnets.map(subnet => subnet.subnetId);
        const memorydbSubnetGroup = new MemoryDB.CfnSubnetGroup(this, memorydbSubnetGroupName, {
            subnetGroupName: memorydbSubnetGroupName,
            subnetIds: privateSubnetIds,
            description: "MemoryDB Subnet Group"
        });
        const memorydbSecurityGroup = new SecurityGroup(this, memorydbSecurityGroupName, {
            vpc: this.vpc,
            allowAllOutbound: true,
            description: "MemoryDB Security Group",
            securityGroupName: memorydbSecurityGroupName
        });
        memorydbSecurityGroup.addIngressRule(Peer.anyIpv4(), Port.tcp(6379), "MemoryDB port");
        const memorydbCluster = new MemoryDB.CfnCluster(
          this,
          memoryDBClusterName,
          {
            aclName: "open-access",
            clusterName: memoryDBClusterName,
            nodeType: "db.t4g.small",
            numShards: 1,
            numReplicasPerShard: 1,
            subnetGroupName: memorydbSubnetGroup.subnetGroupName,
            securityGroupIds: [memorydbSecurityGroup.securityGroupId],
            tlsEnabled: true
          }
        );
        memorydbCluster.addDependency(memorydbSubnetGroup);
    }
}
