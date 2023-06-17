from libs.write_output import write_output
from libs.get_client import get_aws_client
import click
import boto3
from datetime import datetime, timedelta, timezone

@click.group()
def cli():
    pass

# ---------------- DELETE INACTIVE VPN CONNECTIONS ----------------------------
@cli.command()
@click.option('-r', '--region', default='us-east-1', help='AWS region')
@click.option('-a', '--age', type=int, default=365, help='The age in days you want to keep i.e: --age 7 will delete VPN connections older than 7 days old')
@click.option('--dry-run', is_flag=True, help='Show a list of all inactive VPN connections that are to be deleted, but do not delete them')
@click.option('-d', '--delete', is_flag=True, default=False, help='Delete VPN connections that have been inactive for more than the specified age')
@click.option('-f', '--file', help='Custom file name to write output to')
def vpn_connections(region, age, dry_run, delete, file):
    """Delete inactive VPN connections that have been inactive for more than the specified age"""

    if not any([dry_run, delete]):
        click.echo('Please specify either --dry-run or --delete option.')
        exit()

    # Set up AWS client
    ec2, account, account_id = get_aws_client('ec2', region)

    # Get a list of existing VPN connections
    try:
        vpn_connections = ec2.describe_vpn_connections()['VpnConnections']
    except Exception as e:
        click.echo(f"Error occurred while listing VPN connections: {e}")
        return

    # Filter inactive VPN connections by age
    inactive_vpns = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=age)
    for vpn in vpn_connections:
        # click.echo(vpn)
        # click.echo(f"{account}: {account_id} - {vpn['VpnConnectionId']}")

        # Check if the VPN has telemetry data (won't exist if it just got deleted)
        if 'VgwTelemetry' not in vpn:
            continue
        # Get last status change for VPN tunnels
        last_status_change = max(item['LastStatusChange'] for item in vpn['VgwTelemetry'])
        # click.echo(f"Last status change: {last_status_change}")
        # click.echo(f"Cut off time: {cutoff_time}")
        latest_telemetry = next(telemetry for telemetry in vpn['VgwTelemetry'] if telemetry['LastStatusChange'] == last_status_change)
        status = latest_telemetry['Status']
        status_message = latest_telemetry['StatusMessage']
        if age > 0 and last_status_change < cutoff_time and status != 'UP':
            vgw_id = vpn['VpnGatewayId']
            cgw_id = vpn['CustomerGatewayId']
            vpn_id = vpn['VpnConnectionId']
            vpn_name = next((tag['Value'] for tag in vpn.get('Tags', []) if tag['Key'] == 'Name'), None)
            inactive_vpns.append((account, account_id, region, vpn_id, vpn_name, vgw_id, cgw_id, last_status_change, status, status_message))
            headers = ["Account", "Account ID", "Region", "VPN Connection ID", "VPN Name", "VGW ID", "CGW ID", "Last Activity", "Status", "Status message"]

    output = []
    # List inactive VPN connections
    if dry_run and inactive_vpns:
        click.echo(f"\n{account} - {region}: VPN connections inactive for more than {age} days: {len(inactive_vpns)}")
        for vpn in inactive_vpns:
            output.append(vpn[:len(vpn)])
        write_output(output, headers, filename=file)
    # Delete inactive VPN connections
    elif delete and inactive_vpns:
        resources_deleted = 0
        for vpn in inactive_vpns:
            try:
                ec2.delete_vpn_connection(VpnConnectionId=vpn[3])
            except Exception as e:
                click.echo(f"{account} - {region}: Error deleting VPN connection {vpn[3]}: {e}")
            else:
                # click.echo(f"{account} - {region}: Deleted VPN connection {vpn[3]}")
                output.append(vpn)
                resources_deleted += 1
        click.echo(f"\n{account} - {region}: Deleted {resources_deleted} VPN connections")
        write_output(output, headers, filename=file)
    # No inactive VPN connections
    else:
        click.echo(f"{account} - {region}: No inactive VPN connections found exceeding the specified age")
