import boto3
import logging
import argparse
from botocore.exceptions import ClientError


def cli_args():
    """
    Setting up the cli arguments and help messages.
    :return: parsed arguments
    :rtype: Dict
    """

    parser = argparse.ArgumentParser(description="Dump List of ELB's in JSON / CSV")
    parser.add_argument("-listelbs", help="List All Glacier", action="store_true")
    parser.add_argument("-listelbvsinstance", help="List With Instance Details", action="store_true")
    parser.add_argument("-json", help="Provide Vault Name", action="store")
    parser.add_argument("-csv", help="Delete All items", action="store_true")
    parser.add_argument("-region", help="List All Glacier", required=True, action="store")
    parser.add_argument("-profile", help="AWS Profile for credentails", action="store")

    return parser.parse_args()


class LoadBalancer():

    def __init__(self, **kwargs):
        self.update_params(**kwargs)

    def update_params(self, **kwargs):
        self.__dict__.update(**kwargs)

    def to_json(self):
        for key in self.__dict__:
            print(key)

    def to_csv(self):
        pass

    def to_screen(self):
        objo_data = self.__dict__
        print_string = "{:15}  | ELB -> {:30}|{:2} Instances | DNS -> {} ".format(objo_data["type"],
                                                                                   objo_data["elbname"],
                                                                                   len(objo_data["instances"]),
                                                                                   objo_data["dnsname"])
        logging.info(print_string)

def search_target_groups(clientelbv2):
    tgs_data = dict()
    data_target_groups = clientelbv2.describe_target_groups()

    for target_group in data_target_groups["TargetGroups"]:
        tg_arn = target_group["TargetGroupArn"]
        if target_group["LoadBalancerArns"]:
            for lb_arn in target_group["LoadBalancerArns"]:
                tg_health_response = clientelbv2.describe_target_health(TargetGroupArn=tg_arn)
                tgs_data[lb_arn] = list()
                for health_response in tg_health_response["TargetHealthDescriptions"]:
                    tgs_data[lb_arn].append(health_response["Target"]["Id"])

    return tgs_data


def search_elbv1_lbs(elbv1_client, instance_listing=False):
    load_balancer_list = list()

    response = elbv1_client.describe_load_balancers()
    if response["LoadBalancerDescriptions"]:
        for lb in response["LoadBalancerDescriptions"]:
            lbo = LoadBalancer()
            arn = "NA"
            name = lb["LoadBalancerName"]
            sgs = lb["SecurityGroups"]
            createdon = lb["CreatedTime"]
            dnsname = lb["DNSName"]
            type = lb["Scheme"]
            app_nw = "Classic"

            instance_list = list()
            if instance_listing:
                instance = lb["Instances"]

                if instance:
                    for inst in instance:
                        instance_list.append(inst["InstanceId"])

            lbo = LoadBalancer(arn=arn, elbname=name, dnsname=dnsname,
                               type=type, app_or_nw=app_nw, securitygroups=sgs,
                               created=createdon, instances=instance_list)
            load_balancer_list.append(lbo)

    return load_balancer_list


def search_elbv2_lbs(elbv2_client, instance_listing=False):
    load_balancer_list = list()
    response = elbv2_client.describe_load_balancers()

    if instance_listing:
        target_group_data = search_target_groups(elbv2_client)

    if response["LoadBalancers"]:
        for lb in response["LoadBalancers"]:
            arn = lb["LoadBalancerArn"]
            name = lb["LoadBalancerName"]
            dnsname = lb["DNSName"]
            type = lb["Scheme"]
            app_nw = lb["Type"]
            if "SecurityGroups" in lb:
                sgs = lb["SecurityGroups"]
            else:
                sgs = "NA"
            createdon = lb["CreatedTime"]
            instance_list = list()
            if instance_listing:
                if arn in target_group_data:
                    instance_list = target_group_data[arn]

            lbo = LoadBalancer(arn=arn, elbname=name, dnsname=dnsname,
                               type=type, app_or_nw=app_nw, securitygroups=sgs, created=createdon,
                               instances=instance_list)
            load_balancer_list.append(lbo)

    return load_balancer_list


def generate(list_lb_v1, list_lb_v2, type):
    if type == "listing":
        for elbo in list_lb_v1:
            elbo.to_screen()

        for elbo in list_lb_v2:
            elbo.to_screen()

    if type == "json":
        for elbo in list_lb_v1:
            elbo.to_json()

        for elbo in list_lb_v2:
            elbo.to_json()

    if type == "csv":
        for elbo in list_lb_v1:
            elbo.to_csv()

        for elbo in list_lb_v2:
            elbo.to_csv()


if __name__ == '__main__':
    logging.basicConfig(format='%(message)s', level=logging.INFO, datefmt='%H:%M:%S')
    args = cli_args()
    region = args.region

    if args.profile:
        boto3.setup_default_session(profile_name=args.profile)
        logging.info("Using profile .. {}".format(args.profile))

    try:
        logging.info("Region --> {}".format(region))
        logging.info("Connecting to AWS.. in region {}".format(region))
        if args.listelbs:
            logging.info("Listing ELB'S...")
            lb_v1_client = boto3.client("elb", region_name=args.region)
            lb_v2_client = boto3.client("elbv2", region_name=args.region)
            list_lb_v2 = search_elbv2_lbs(lb_v2_client, args.listelbvsinstance)
            list_lb_v1 = search_elbv1_lbs(lb_v1_client, args.listelbvsinstance)
            generate(list_lb_v1, list_lb_v2, "listing")
        elif args.listelbvsinstance:
            logging.info("Listing ELB'S with Instance Data...")
            lb_v1_client = boto3.client("elb", region_name=args.region)
            lb_v2_client = boto3.client("elbv2", region_name=args.region)
            list_lb_v2 = search_elbv2_lbs(lb_v2_client, args.listelbvsinstance)
            list_lb_v1 = search_elbv1_lbs(lb_v1_client, args.listelbvsinstance)
            generate(list_lb_v1, list_lb_v2, "listing")
        else:
            logging.info("Invalid command.. Kindly use help")
            exit(-1)

        if args.json:
            generate(list_lb_v1, list_lb_v2, "json")

        if args.csv:
            generate(list_lb_v1, list_lb_v2, "csv")

    except ClientError as e:
        logging.exception(e)
