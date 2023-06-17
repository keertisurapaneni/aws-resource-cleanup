from libs.write_output import write_output
from libs.get_client import get_aws_client
import click
import boto3
import botocore
from datetime import datetime, timedelta, timezone

@click.group()
def cli():
    pass

# ---------------- DELETE UNATTACHED VOLUMES ----------------------------
@cli.command()
@click.option('-r', '--region', default='us-east-1', help='AWS region')
@click.option('-a', '--age', type=int, default=365, help='The age in days you want to keep i.e: --age 7 will delete unattached volumes older than 7 days old')
@click.option('--dry-run', is_flag=True, help='Show a list of all unattached volumes (and associated snapshots) that are to be deleted, but do not delete them')
@click.option('-d', '--delete', is_flag=True, default=False, help='Delete all unattached volumes (and associated snapshots) that are older than the specified age')
@click.option('--snapshots', default='yes', type=click.Choice(['yes', 'no']), required=False, is_eager=True, help='Display/delete associated snapshots along with the AMI. Set to "no" to disable. Only available with --dry-run or --delete.')
@click.option('-f', '--file', help='Custom file name to write output to')
def ebs_volumes(region, age, dry_run, delete, file, snapshots):
    """Delete unattached and unused EBS volumes and associated snapshots older than a specified age"""

    if not any([dry_run, delete]):
        click.echo('Please specify either --dry-run or --delete option.')
        exit()

    # Evaluating user value to a boolean
    delete_snap_bool = snapshots == 'yes'

    # Set up AWS client
    ec2, account, account_id = get_aws_client('ec2', region)

    # List existing volumes
    try:
        volume_response = ec2.describe_volumes()
    except Exception as e:
        click.echo(f"Error occurred while listing volumes: {e}")
        return

    # Filter unattached volumes by age
    if volume_response['ResponseMetadata']['HTTPStatusCode'] != 200:
        click.echo(f"Failed to list volumes with status code {volume_response['ResponseMetadata']['HTTPStatusCode']}")
        return
    volumes_to_delete = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=age)
    for volume in volume_response['Volumes']:
        try:
            if volume['State'] == 'available':
                start_time = volume['CreateTime']
                if len(volume.get('Attachments', [])) == 0 and age > 0 and start_time < cutoff_time:
                    # click.echo(volume)
                    start_date = datetime.strftime(start_time, '%Y-%m-%d')
                    # Get the value of the "Name" tag, if it exists
                    name_tag = next((tag['Value'] for tag in volume.get('Tags', []) if tag['Key'] == 'Name'), None)
                    # Add snapshot info if delete_snap_bool is True
                    if delete_snap_bool:
                        volumes_to_delete.append((account, account_id, region, volume['VolumeId'], name_tag, volume['Size'], volume['VolumeType'], volume.get('Iops'), start_date, volume.get('SnapshotId')))
                        headers=["Account", "Account ID", "Region", "EBS Volume ID", "Volume name", "Volume size (GiB)", "Volume type", "Iops", "Creation Date", "Snapshot ID"]
                    else:
                        volumes_to_delete.append((account, account_id, region, volume['VolumeId'], name_tag, volume['Size'], volume['VolumeType'], volume.get('Iops'), start_date))
                        headers=["Account", "Account ID", "Region", "EBS Volume ID", "Volume name", "Volume size (GiB)", "Volume type", "Iops", "Creation Date"]
        except Exception as e:
            click.echo(f"Error filtering volume {volume['VolumeId']}: {e}")
      

    output = []  
    # List unattached volumes
    if dry_run and volumes_to_delete:
        click.echo(f"\n{account} - {region}: Unattached EBS volumes older than {age} days: {len(volumes_to_delete)}")
        for volume in volumes_to_delete:
            output.append(volume[:len(volume)])
        write_output(output, headers, filename=file)
  
    # Delete unattached volumes
    elif delete and volumes_to_delete:
        resources_deleted = 0
        snapshots_deleted = 0
        for volume in volumes_to_delete:
            try:
                ec2.delete_volume(VolumeId=volume[3])
                if delete_snap_bool and volume[9]:
                    try:
                        ec2.delete_snapshot(SnapshotId=volume[9])
                    except Exception as e:
                        click.echo(f"{account} - {region}: Error deleting snapshot {volume[9]}: {e}")
                    else:
                        # click.echo(f"Deleted snapshot {volume[9]}")
                        snapshots_deleted += 1
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'InvalidSnapshot.NotFound':
                    click.echo(f"Skipping deletion since {volume[9]} was already deleted")
                    pass
                else:
                    click.echo(f"{account} - {region}: Error deleting volume {volume[3]}: {e}")
            except Exception as e:
                click.echo(f"{account} - {region}: Error deleting volume {volume[3]}: {e}")
            else:
                # click.echo(f"Deleted volume {volume[3]}")
                output.append(volume)
                resources_deleted += 1
        if delete_snap_bool:
            click.echo(f"\n{account} - {region}: Deleted {resources_deleted} volumes and {snapshots_deleted} snapshots")
        else:
            click.echo(f"\n{account} - {region}: Deleted {resources_deleted} volumes")
        write_output(output, headers, filename=file)
    # No unattached volumes found
    else:
        click.echo(f"{account} - {region}: No unattached volumes found exceeding the specified age")
