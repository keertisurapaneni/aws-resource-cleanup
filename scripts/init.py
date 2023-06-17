#!/usr/bin/env python3

import click
import pkg_resources as pr
from .commands.ec2_instances import ec2_instances
from .commands.ebs_volumes import ebs_volumes
from .commands.ami import ami
from .commands.vpn_connections import vpn_connections
from .commands.ec2_snapshots import ec2_snapshots
from .commands.rds_snapshots import rds_snapshots

@click.group()
@click.version_option(pr.get_distribution('aws-resource-cleanup').version, '--version', '-v')
def cli():
    pass

cli.add_command(ec2_instances)
cli.add_command(ebs_volumes)
cli.add_command(ami)
cli.add_command(ec2_snapshots)
cli.add_command(rds_snapshots)
cli.add_command(vpn_connections)
