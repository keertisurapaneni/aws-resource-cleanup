from libs.write_output import write_output
from libs.get_client import get_aws_client
import click
import boto3
from datetime import datetime, timedelta, timezone
import re

@click.group()
def cli():
    pass

# ---------------- TERMINATE STOPPED EC2 INSTANCES ----------------------------
@cli.command()
@click.option('-r', '--region', default='us-east-1', help='AWS region')
@click.option('-a', '--age', type=int, default=365, help='The age in days you want to keep i.e: --age 7 will delete unattached volumes older than 7 days old')
@click.option('--dry-run', is_flag=True, help='Show a list of all stopped EC2 instances that are to be deleted, but do not delete them')
@click.option('-d', '--delete', is_flag=True, default=False, help='Delete EC2 instances stopped for more than the specified age')
@click.option('-f', '--file', help='Custom file name to write output to')
def ec2_instances(region, age, dry_run, delete, file):
    """Terminate stopped EC2 instaces last stopped before a specified age"""

    if not any([dry_run, delete]):
        click.echo('Please specify either --dry-run or --delete option.')
        exit()

    # Set up AWS client
    ec2, account, account_id = get_aws_client('ec2', region)

    # List existing EC2 instances
    try:
        reservations = ec2.describe_instances()['Reservations']
    except Exception as e:
        click.echo(f"Error occurred while listing EC2 instances: {e}")
        return

    # Filter stopped EC2 instances by age
    instances_to_delete = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=age)
    for reservation in reservations:
        for instance in reservation['Instances']:
            status = instance['State']['Name']
            if status == 'stopped':
                stopped_reason = instance['StateTransitionReason']
                # Stopped reasons can look like below
                    # User initiated (2023-03-25 01:01:07 GMT)
                    # User initiated
                # We want to ignore anything that doesn't have the stopped time
                stopped_time = re.search('\((.*)\)', stopped_reason)
                if stopped_time:
                    stopped_time = stopped_time.group(1)
                    utc = timezone.utc
                    try:
                        stopped_time = datetime.strptime(stopped_time, '%Y-%m-%d %H:%M:%S %Z').replace(tzinfo=utc)
                        # click.echo(stopped_time)
                    except ValueError:
                        # Handle any errors raised by strptime
                        continue
                    if age > 0 and stopped_time < cutoff_time:
                        stopped_date = datetime.strftime(stopped_time, '%Y-%m-%d')
                        # Get the value of the "Name" tag, if it exists
                        name_tag = next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), None)
                        instances_to_delete.append((account, account_id, region, instance['InstanceId'], name_tag, instance['InstanceType'], stopped_date))
                        headers=["Account", "Account ID", "Region", "EC2 Instance ID", "Instance name", "Instance type", "Stopped Date"]

    output = []
    # List stopped EC2 instances
    if dry_run and instances_to_delete:
        click.echo(f"\n{account} - {region}: EC2 instances stopped for more than {age} days: {len(instances_to_delete)}")
        for instance in instances_to_delete:
            output.append(instance[:len(instance)])
        write_output(output, headers, filename=file)
        # write_output(output, headers, filename=file, message=f"EC2 instances stopped for more than {age} days: {len(instances_to_delete)}")
    # Terminate stopped EC2 snapshots
    elif delete and instances_to_delete:
        resources_deleted = 0
        for instance in instances_to_delete:
            try:
                ec2.terminate_instances(InstanceIds=[instance[3]])
            except Exception as e:
                click.echo(f"{account} - {region}: Error deleting EC2 instance {instance[3]}: {e}")
            else:
                # click.echo(f"Terminated EC2 instance {instance[0]}")
                output.append(instance)
                resources_deleted += 1
        click.echo(f"\n{account} - {region}: Deleted {resources_deleted} EC2 instances")
        write_output(output, headers, filename=file)
    # No stopped EC2 instances
    else:
        click.echo(f"{account} - {region}: No stopped EC2 instances found exceeding the specified age")
