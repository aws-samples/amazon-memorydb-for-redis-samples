import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as EC2 from "aws-cdk-lib/aws-ec2";
import * as MemoryDB from "aws-cdk-lib/aws-memorydb";
import * as AWS from "aws-sdk";

export class MemorydbCdkTsTlsStack extends cdk.Stack {
  private vpc: EC2.Vpc;

  /**
   * Availability zones ids where MemoryDB is supported
   * https://docs.aws.amazon.com/memorydb/latest/devguide/subnetgroups.html
   *
   * @param region
   * @returns string[]
   */
  private getMemoryDBAvailabilityZonesPerRegion(region: string): string[] {
    switch (region) {
      case "us-east-2":
        return "use2-az1,use2-az2,use2-az3".split(",");
      case "us-east-1":
        return "use1-az2,use1-az4,use1-az6".split(",");
      case "us-west-1":
        return "usw1-az1,usw1-az2,usw1-az3".split(",");
      case "us-west-2":
        return "usw2-az1,usw2-az2,usw2-az3".split(",");
      case "ca-central-1":
        return "cac1-az1,cac1-az2,cac1-az3".split(",");
      case "ap-east-1":
        return "ape1-az1,ape1-az2,ape1-az3".split(",");
      case "ap-south-1":
        return "aps1-az1,aps1-az2,aps1-az3".split(",");
      case "ap-northeast-1":
        return "apne1-az1,apne1-az2,apne1-az4".split(",");
      case "ap-northeast-2":
        return "apne2-az1,apne2-az2,apne2-az3".split(",");
      case "ap-southeast-1":
        return "apse1-az1,apse1-az2,apse1-az3".split(",");
      case "ap-southeast-2":
        return "apse2-az1,apse2-az2,apse2-az3".split(",");
      case "eu-central-1":
        return "euc1-az1,euc1-az2,euc1-az3".split(",");
      case "eu-west-1":
        return "euw1-az1,euw1-az2,euw1-az3".split(",");
      case "eu-west-2":
        return "euw2-az1,euw2-az2,euw2-az3".split(",");
      case "eu-north-1":
        return "eun1-az1,eun1-az2,eun1-az3".split(",");
      case "sa-east-1":
        return "sae1-az1,sae1-az2,sae1-az3".split(",");
      case "cn-north-1":
        return "cnn1-az1,cnn1-az2".split(",");
      case "cn-northwest-1":
        return "cnw1-az1,cnw1-az2,cnw1-az3".split(",");
      default:
        return "use1-az2,use1-az4,use1-az6".split(",");
    }
  }

  /**
   * Get the availability zones names for the current account
   *
   * @param region
   * @param azIds
   * @returns string[]
   */
  private async getAvailabilityZones(
    region: string,
    azIds: string[]
  ): Promise<string[]> {
    const azNames: string[] = [];
    const ec2 = new AWS.EC2({ region: region });
    const response = await ec2.describeAvailabilityZones({}).promise();
    for (const az of response.AvailabilityZones!) {
      if (azIds.includes(az.ZoneId!)) {
        azNames.push(az.ZoneName!);
      }
    }
    return azNames;
  }

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    const memoryDBVpc = "memorydb-vpc";
    const memorydbSubnetGroupName = "memorydb-subnet-group";
    const memorydbSecurityGroupName = "memorydb-security-group";
    const memorydbClusterName = "memorydb-cluster";
    const tlsEnabled = true;
    super(scope, id, props);

    const currentRegion = cdk.Stack.of(this).region.toString();
    // console.log("Current Region:", currentRegion);

    const azIds = this.getMemoryDBAvailabilityZonesPerRegion(currentRegion);
    // console.log("Availability Zone IDs:", azIds);

    // Get the availability zones for the current region
    this.getAvailabilityZones(currentRegion, azIds)
      .then((availabilityZones) => {
        // console.log("Availability Zones:", availabilityZones);
        // 1. Create VPC
        this.vpc = new EC2.Vpc(this, "memorydb-vpc", {
          availabilityZones: availabilityZones,
        });
        // 2. Get private subnet IDs
        const privateSubnetIds = this.vpc.privateSubnets.map(
          (subnet) => subnet.subnetId
        );
        // 3. Create subnet group
        const subnetGroup = new MemoryDB.CfnSubnetGroup(
          this,
          memorydbSubnetGroupName,
          {
            subnetIds: privateSubnetIds,
            subnetGroupName: memorydbSubnetGroupName,
            description: "MemoryDB subnet group",
          }
        );
        // 4. Create security group
        const securityGroup = new EC2.SecurityGroup(
          this,
          memorydbSecurityGroupName,
          {
            vpc: this.vpc,
            allowAllOutbound: true,
            description: "MemoryDB security group",
            securityGroupName: memorydbSecurityGroupName,
          }
        );
        securityGroup.addIngressRule(
          EC2.Peer.anyIpv4(),
          EC2.Port.tcp(6379),
          "MemoryDB port"
        );
        // 5. Create MemoryDB cluster
        const memorydb_cluster = new MemoryDB.CfnCluster(
          this,
          memorydbClusterName,
          {
            clusterName: memorydbClusterName,
            nodeType: "db.t4g.small",
            aclName: "open-access",
            numShards: 1,
            securityGroupIds: [securityGroup.securityGroupId],
            subnetGroupName: memorydbSubnetGroupName,
            tlsEnabled: tlsEnabled,
          }
        );
        memorydb_cluster.addDependency(subnetGroup);
      })
      .catch((error) => {
        console.error("Error getting availability zones:", error);
      });
  }
}
