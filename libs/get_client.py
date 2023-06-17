import click
import boto3
from botocore.exceptions import ClientError, EndpointConnectionError



# ---------------- GET AWS CLIENT ----------------------------
def get_aws_client(service_name, region, *args):
    """Returns the AWS client for the specified service and region"""
    try:
        session = boto3.Session(region_name=region)
        client = session.client(service_name, *args)
        account = boto3.client('iam').list_account_aliases()['AccountAliases'][0]
        account_id = str(boto3.client('sts').get_caller_identity().get('Account'))
        return client, account, account_id
    except (ClientError, EndpointConnectionError) as e:
        click.echo(f"Failed to create AWS client for {service_name} in {region}: {e}")
        return None
