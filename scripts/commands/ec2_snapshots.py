from libs.write_output import write_output
from libs.get_client import get_aws_client
import click
import boto3
from datetime import datetime, timedelta, timezone

@click.group()
def cli():
    pass

# ---------------- DELETE ORPHANED EC2 SNAPSHOTS ----------------------------
@cli.command()
@click.option('-r', '--region', default='us-east-1', help='AWS region')
@click.option('-a', '--age', type=int, default=365, help='The age in days you want to keep i.e: --age 7 will delete snapshots older than 7 days old')
@click.option('--dry-run', is_flag=True, help='Show a list of all snapshots that are to be deleted, but do not delete them')
@click.option('-d', '--delete', is_flag=True, default=False, help='Delete all snapshots that are older than the specified age')
@click.option('-f', '--file', help='Custom file name to write output to')
def ec2_snapshots(region, age, dry_run, delete, file):
    """Deletes orphaned EC2 snapshots older than a specified age"""

    if not any([dry_run, delete]):
        click.echo('Please specify either --dry-run or --delete option.')
        exit()

    # Set up AWS client
    ec2, account, account_id = get_aws_client('ec2', region)
    
    # https://medium.com/@NickHystax/reduce-your-aws-bill-by-cleaning-orphaned-and-unused-disk-snapshots-c3142d6ab84
    # Get the list of existing volumes and their IDs
    volume_response = ec2.describe_volumes()
    volumes = [v['VolumeId'] for v in volume_response['Volumes']]

    # Get the list of AMIs and their associated snapshots
    # Useful to identify snapshots where volume has been deleted but snapshot is still linked to the AMI.
    image_response = ec2.describe_images(Owners=['self'])
    images = image_response['Images']
    ami_snapshots = {}
    for image in images:
        if image['State'] == 'available':
            for ebs in image['BlockDeviceMappings']:
                if 'Ebs' in ebs and 'SnapshotId' in ebs['Ebs']:
                    # Save Snapshot ID as key and AMI as value to ami_snapshots dictionary (it is easier to search later)
                    ami_snapshots[ebs['Ebs']['SnapshotId']] = image['ImageId']
    # click.echo(ami_snapshots)

    # Get the list of snapshots not linked to existing volumes or AMIs, and filter by age
    snapshots_to_delete = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=age)
    snapshots = ec2.describe_snapshots(OwnerIds=['self'])['Snapshots']
    for snapshot in snapshots:
        try:
            start_time = snapshot['StartTime']
            if age > 0 and start_time < cutoff_time:
                # Check if Snapshot ID is present in list of AMI snapshots (linked to AMI)
                # Example for AMI snapshot: Created by CreateImage(i-08788bfae7122628d) for ami-03af367a69f1d6aa5
                if snapshot['SnapshotId'] in ami_snapshots:
                    linked_ami = ami_snapshots[snapshot['SnapshotId']]
                    # click.echo(f"Skipping {snapshot['SnapshotId']} since it is linked to AMI {linked_ami}")
                    continue
                # Check non-AMI snapshots and skip snapshot if snapshot volume is present in the list of existing volumes (linked to volume) 
                # Example for non-AMI snapshots: EmeraldRanch - IP-0A6D16BD        
                if ('Created by CreateImage' not in snapshot['Description'] and snapshot['VolumeId'] in volumes):
                    # click.echo(f"Skipping {snapshot['SnapshotId']} since it is linked to volume {snapshot['VolumeId']}")
                    continue
                # Delete unattached snapshots
                start_date = datetime.strftime(start_time, '%Y-%m-%d')
                # Get the value of the "Name" tag, if it doesn't exist, get the snapshot description
                snapshot_name = next((tag['Value'] for tag in snapshot.get('Tags', []) if tag['Key'] == 'Name'), snapshot['Description'])
                snapshot_name = snapshot_name if snapshot_name else None
                snapshots_to_delete.append((account, account_id, region, snapshot['SnapshotId'], snapshot_name, snapshot['VolumeSize'], snapshot['StorageTier'], start_date))
                headers=["Account", "Account ID", "Region", "EC2 Snapshot ID", "Snapshot info", "Volume size (GiB)", "Storage tier", "Creation Date"]
        except Exception as e:
            click.echo(f"Error filtering snapshots {snapshot['SnapshotId']}: {e}")


    output = []
    # List orphaned EC2 snapshots
    if dry_run and snapshots_to_delete:
        click.echo(f"\n{account} - {region}: Orphaned EC2 snapshots older than {age} days: {len(snapshots_to_delete)}")
        for snapshot in snapshots_to_delete:
            output.append(snapshot[:len(snapshot)])
        write_output(output, headers, filename=file)
    # Delete orphaned EC2 snapshots
    elif delete and snapshots_to_delete:
        resources_deleted = 0
        for snapshot in snapshots_to_delete:
            try:
                ec2.delete_snapshot(SnapshotId=snapshot[3])
            except Exception as e:
                click.echo(f"{account} - {region}: Error deleting snapshot {snapshot[3]}: {e}")
            else:
                # click.echo(f"Deleted snapshot {snapshot[3]}")
                output.append(snapshot)
                resources_deleted += 1
        click.echo(f"\n{account} - {region}: Deleted {resources_deleted} EC2 snapshots") 
        write_output(output, headers, filename=file)
    # No orphaned EC2 snapshots
    else:
        click.echo(f"{account} - {region}: No orphaned EC2 snapshots found exceeding the specified age")
