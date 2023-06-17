from libs.write_output import write_output
from libs.get_client import get_aws_client
import click
import boto3
from datetime import datetime, timedelta
import re

@click.group()
def cli():
    pass

# ---------------- DEREGISTER AMIS ----------------------------
@cli.command()
@click.option('-r', '--region', default='us-east-1', help='AWS region')
@click.option('-a', '--age', type=int, default=365, help='The age in days you want to keep i.e: --age 7 will delete unattached volumes older than 7 days old')
@click.option('--dry-run', is_flag=True, help='Show a list of all unused AMIs (and associated snapshots) that are to be deleted, but do not delete them')
@click.option('-d', '--delete', is_flag=True, default=False, help='Delete all unused AMIs (and associated snapshots) that are older than the specified age')
@click.option('--snapshots', default='yes', type=click.Choice(['yes', 'no']), required=False, is_eager=True, help='Display/delete associated snapshots along with the AMI. Set to "no" to disable. Only available with --dry-run or --delete.')
@click.option('-f', '--file', help='Custom file name to write output to')
def ami(region, age, dry_run, delete, file, snapshots):
    """Deregister unused AMIs and delete associated snapshots older than a specified age"""

    if not any([dry_run, delete]):
        click.echo('Please specify either --dry-run or --delete option.')
        exit()

    # Evaluating user value to a boolean
    delete_snap_bool = snapshots == 'yes'

    # Set up AWS client
    ec2, account, account_id = get_aws_client('ec2', region)
    asg, account, account_id = get_aws_client('autoscaling', region)

    # https://oxiehorlock.com/2022/01/29/clean-em-getting-rid-of-unused-amis-using-python-lambda/

    # Get AMIs for all EC2 instances
    try:
        reservations = ec2.describe_instances()['Reservations']
    except Exception as e:
        click.echo(f"Error occurred while listing instances: {e}")
        return

    instance_amis = []
    for reservation in reservations:
        for instance in reservation['Instances']:
            try:
                # click.echo(f"{instance['InstanceId']} {instance['ImageId']}")
                instance_amis.append(instance['ImageId'])
            except:
                click.echo(f"Error occurred while listing instance image: {e}")
                return None

    # Get AMIs for all ASGs in use
    asg_amis = []
    try:
        paginator = asg.get_paginator('describe_auto_scaling_groups')
        # Search for instances in the "InService" state and get their InstanceId, LaunchTemplateId, and LaunchTemplateVersion
        filtered_asgs = paginator.paginate().search("AutoScalingGroups[*].[Instances[?LifecycleState == 'InService'].[InstanceId, LaunchTemplate.LaunchTemplateId,LaunchTemplate.Version]]")
    except Exception as e:
        click.echo(f"An error occurred while getting Auto Scaling groups in region {region}: {str(e)}")

        # Iterate through the Auto Scaling groups and get the AMI ID of each instance
        for key_data in filtered_asgs:
            try:
                matches = re.findall(r"'(.+?)'",str(key_data))
                if len(matches) < 3:
                    # Handle the error here (e.g. click.echo a message, skip this iteration of the loop, etc.)
                    continue
                instance_id, template, version = matches[:3]
                launch_template_versions = ec2.describe_launch_template_versions(LaunchTemplateId=template, Versions=[version]);  
                used_ami_id = launch_template_versions["LaunchTemplateVersions"][0]["LaunchTemplateData"]["ImageId"]
                if not used_ami_id:
                    click.echo(f"Failed to find AMI for launch template {template} version {version}")
                    continue
                asg_amis.append(used_ami_id)
            except Exception as e:
                click.echo(f"An error occurred while processing an Auto Scaling group: {str(e)}")
                continue

    # Get complete list of AMIs in use
    amis_in_use = []
    amis_in_use = list(set(asg_amis + instance_amis))
    # click.echo(amis_in_use)

    # List existing AMIs
    try:
        amis = ec2.describe_images(Owners=['self'])['Images']
    except Exception as e:
        click.echo(f"Error occurred while listing AMIs: {e}")
        return
    
    # Filter unused AMIs  by age
    amis_to_deregister = []
    for ami in amis:
        try:
            # Check if 'CreationDate' is present in the ami dictionary and not empty
            if ami.get('CreationDate'):
                start_time = datetime.strptime(ami['CreationDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                cutoff_time = datetime.utcnow() - timedelta(days=age)
                if ami['ImageId'] not in amis_in_use and age > 0 and start_time < cutoff_time:
                    start_date = start_time.strftime('%Y-%m-%d')
                    # Get the value of AMI Name, if it exists
                    ami_name = ami_name = ami.get('Name', '')

                    # Get snapshot IDs associated with the AMI
                    snapshot_ids = []
                    for ebs in ami['BlockDeviceMappings']:
                        if 'Ebs' in ebs and 'SnapshotId' in ebs['Ebs']:
                            snapshot_id = ebs['Ebs']['SnapshotId']
                            snapshot_ids.append((snapshot_id, ebs['Ebs']['VolumeSize'], ebs['Ebs']['VolumeType']))

                    # Append the AMI ID and snapshot IDs to the list
                    if delete_snap_bool:
                        amis_to_deregister.append((account, account_id, region, ami['ImageId'], ami_name, start_date, snapshot_ids if snapshot_ids else ['']))
                        # click.echo(amis_to_deregister)
                        headers=["Account", "Account ID", "Region", "AMI ID", "AMI name", "Creation Date", "Snapshots"]
                    else:
                        amis_to_deregister.append((account, account_id, region, ami['ImageId'], ami_name, start_date))
                        headers=["Account", "Account ID", "Region", "AMI ID", "AMI name", "Creation Date"]
        except Exception as e:
            click.echo(f"Error filtering unused AMIs {ami['ImageId']}: {e}")
     
    output = [] 
    # List unused AMIs and associated snapshots
    if dry_run and amis_to_deregister:
        click.echo(f"\n{account} - {region}: Unused AMIs older than {age} days: {len(amis_to_deregister)}")
        for ami in amis_to_deregister:
            # click.echo(ami)
            output.append(ami[:len(ami)])
        write_output(output, headers, filename=file)

    # Deregister unused AMIs and associated snapshots
    elif delete and amis_to_deregister:
        resources_deleted = 0
        snapshots_deleted = 0
        for ami in amis_to_deregister:
            try:
                ec2.deregister_image(ImageId=ami[3])
                if delete_snap_bool and ami[6]:
                    try:
                        for snapshot in ami[6]:
                            ec2.delete_snapshot(SnapshotId=snapshot[0])
                    except Exception as e:
                        click.echo(f"{account} - {region}: Error deleting snapshot {snapshot[0]}: {e}")
                    else:
                        # click.echo(f"Deleted snapshot {snapshot[0]}")
                        snapshots_deleted += 1
            except Exception as e:
                click.echo(f"{account} - {region}: Error deregistering AMI {ami[3]}: {e}")
            else:
                # click.echo(f"Deregistered AMI {ami[3]}")
                output.append(ami)
                resources_deleted += 1
        if delete_snap_bool:
            click.echo(f"\n{account} - {region}: Deleted {resources_deleted} AMIs and {snapshots_deleted} snapshots")
        else:
            click.echo(f"\n{account} - {region}: Deleted {resources_deleted} AMIs")
        write_output(output, headers, filename=file)
    # No unused AMIs found
    else:
        click.echo(f"{account} - {region}: No unused AMIs found exceeding the specified age")
