from libs.write_output import write_output
from libs.get_client import get_aws_client
import click
import boto3
from datetime import datetime, timedelta, timezone

@click.group()
def cli():
    pass

# ---------------- DELETE RDS SNAPSHOTS ----------------------------
@cli.command()
@click.option('-r', '--region', default='us-east-1', help='AWS region')
@click.option('-a', '--age', type=int, default=365, help='The age in days you want to keep i.e: --age 7 will delete snapshots older than 7 days old')
@click.option('--dry-run', is_flag=True, help='Show a list of all RDS snapshots that are to be deleted, but do not delete them')
@click.option('-d', '--delete', is_flag=True, default=False, help='Delete all RDS snapshots that are older than the specified age')
@click.option('-f', '--file', help='Custom file name to write output to')
def rds_snapshots(region, age, dry_run, delete, file):
    """Deletes RDS snapshots that are older than a specified age"""

    if not any([dry_run, delete]):
        click.echo('Please specify either --dry-run or --delete option.')
        exit()

    # Set up AWS client
    rds, account, account_id = get_aws_client('rds', region)

    # Get all RDS snapshots
    try:
        snapshots = []
        snapshots += rds.describe_db_snapshots(SnapshotType='manual')['DBSnapshots']
        snapshots += rds.describe_db_cluster_snapshots(SnapshotType='manual')['DBClusterSnapshots']
    except Exception as e:
        click.echo(f"Error: {e}")
        return None

    # Filter snapshots by age
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=age)
    snapshots_to_delete = []
    for snapshot in snapshots:
        try:
            if snapshot['Status'] == 'available':
                # click.echo(snapshot)
                start_time = snapshot['SnapshotCreateTime']
                if age > 0 and start_time < cutoff_time:
                    if 'DBSnapshotIdentifier' in snapshot:
                        snapshot_type = "Instance"
                        snapshot_id = snapshot['DBSnapshotIdentifier']
                    elif 'DBClusterSnapshotIdentifier' in snapshot:
                        snapshot_type = "Cluster"
                        snapshot_id = snapshot['DBClusterSnapshotIdentifier']
                    start_date = datetime.strftime(start_time, '%Y-%m-%d')
                    snapshots_to_delete.append((account, account_id, region, snapshot_id, snapshot_type, snapshot['AllocatedStorage'], start_date))
                    headers=["Account", "Account ID", "Region", "RDS Snapshot name", "Snapshot type", "Snapshot Size (GiB)",  "Creation Date"]
        except Exception as e:
            click.echo(f"Error: {e}")


    output = []
    # List RDS snapshots
    if dry_run and snapshots_to_delete:
        click.echo(f"\n{account} - {region}: RDS snapshots older than {age} days: {len(snapshots_to_delete)}")
        for snapshot in snapshots_to_delete:
            output.append(snapshot[:len(snapshot)])
        write_output(output, headers, filename=file)
    # Delete RDS snapshots
    elif delete and snapshots_to_delete:
        resources_deleted = 0
        for snapshot in snapshots_to_delete:
            try:
                if snapshot[4] == "Instance":
                    rds.delete_db_snapshot(DBSnapshotIdentifier=snapshot[3])
                elif snapshot[4] == "Cluster":
                    rds.delete_db_cluster_snapshot(DBClusterSnapshotIdentifier=snapshot[3])
            except Exception as e:
                click.echo(f"{account} - {region}: Error deleting RDS snapshot {snapshot[3]}: {e}")
            else:
                # click.echo(f"Deleted RDS snapshot {snapshot_id}")
                output.append(snapshot)
                resources_deleted += 1
        click.echo(f"\n{account} - {region}: Deleted {resources_deleted} RDS snapshots")
        write_output(output, headers, filename=file)
    # No RDS snapshots
    else:
        click.echo(f"{account} - {region}: No RDS snapshots found exceeding the specified age")

