import click
import boto3
from datetime import date
import csv
import os


# ---------------- WRITE OUTPUT TO CONSOLE AND CSV ----------------------------
def write_output(output, headers=None, filename=None, message=None):
    """Writes the output to both console and CSV file"""

    # Write message to console and CSV file
    if message:
        account = boto3.client('iam').list_account_aliases()['AccountAliases'][0]
        message = f"{account}: {message}"  # add account name to message
        click.echo(message)
    
    # Write to console
    if isinstance(output, list):
        for row in output:
            if isinstance(row, list):
                click.echo('\t'.join(str(col) for col in row))
            elif isinstance(row, tuple):
                click.echo(' '.join(str(col) for col in row))
            else:
                click.echo(str(row))
    else:
        click.echo(output)

    
    # Write to CSV file
    #--------------------------------------------
    if filename is None:
        account = boto3.client('iam').list_account_aliases()['AccountAliases'][0]
        filename = f"{account}-"+ str(date.today()) + ".csv"

    # Check if file exists
    file_exists = os.path.isfile(filename)

    # Check if headers exist in file
    headers_exist = False
    if file_exists:
        with open(filename, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if row == headers:
                    headers_exist = True
                    break

    try:
        with open(filename, 'a', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            if message:
                writer.writerow([])
                writer.writerow([message])
            # Add header if it doesn't exist
            if not headers_exist:
                writer.writerow(headers)
            if isinstance(output, list):
                for row in output:
                    if isinstance(row, list):
                        writer.writerow(row)
                    elif isinstance(row, tuple):
                        writer.writerow(list(row))
                    else:
                        writer.writerow([row])
            elif isinstance(output, tuple):
                writer.writerow(list(output))
            else:
                writer.writerow([output])
        # click.echo(f"\nOutput written to {filename}")
    except IOError:
        click.echo(f"\nError: Could not write to {filename}")
