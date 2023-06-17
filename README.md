# AWS Resource Cleanup Tool

The AWS Resource Cleanup Tool is a simple command line tool that can help you manage your AWS resources and keep your account clean. With just a few commands, you can easily terminate stopped EC2 instances, delete unattached EBS volumes and associated snapshots, unused AMIs and associated snapshots, orphaned EC2 snapshots and RDS snapshots older than a specified age.

## Pre-requisites

- Python 3.x
- Clone the repo


## Installing locally

#### Setup a virtual environment via `virtualenv`

```
virtualenv -p $(which python3) .cleanup
```

#### Activate virtual environment via `source`

```
source .cleanup/bin/activate
```

#### Install required packages via `pip`

```
pip install .
```


#### Deactivate your virtual environment via `deactivate` after you finish running the tool

```
deactivate
```

## Usage

### Commands

The tool has the following commands: 

- `ec2-instances`: Terminates EC2 instances stopped for a specified age.
- `ebs-volumes`: Deletes unattached EBS volumes and associated snapshots older than a specified age.
- `ami`: Deletes unused AMIs and the associated snapshots older than a specified age.
- `ec2-snapshots`: Deletes orphaned EC2 snapshots (not linked to an EBS volume or an AMI) older than a specified age.
- `rds-snapshots`: Deletes RDS snapshots (both instance and cluster snapshots) older than a specified age.
- `vpn-connections`: Deletes VPN connections that have been inactive for more than the specified age (Recommended age: 1 since the observed behavior is VPN tunnel's status keeps changing for some odd reason even if VPN is inactive.)


### Options

Each command has the following options:

- `-r, --region`: AWS region, default is us-east-1
- `-a, --age`: Get resources that were created before the age in days, default is 365
- `--dry-run`: Show a list of all resources that are to be deleted, but do not delete them
- `-d, --delete`: Delete all resources older than the specified age
- `-f, --file`: Pass a custom csv file to save the output of dry-run to
- `--snapshots`: Display/delete associated snapshots along with the resources (Default: `yes`. Set to `no` to disable it. Available only for `ebs-volumes` and `ami` commands.)


### Usage

You need to run the script with either of the two requisite options: `dry-run` or `delete`. Just replace `--dry-run` with `--delete` when you are ready to delete resources.

- Single account, single resource

  ```bash
  aws-vault exec <aws-profile> -- aws-resource-cleanup <command> --age <age> --dry-run
  ```

  Usage example:

  ```bash
  aws-vault exec bankrate-qa -- aws-resource-cleanup ebs-volumes --age 150 --dry-run
  ```


- Single account, multiple resources

  ```bash
  for resource in ec2-instances ebs-volumes ami ec2-snapshots rds-snapshots; do aws-vault exec bankrate-qa -- aws-resource-cleanup $resource  --dry-run --region us-east-1; done
  ```

- Multiple accounts, multiple resources, single region:


  The following example shows how you can run the script against multiple profiles by using a file (accounts.txt) that contains a list of profile names (they should match the names in ~/.aws/config).     

  ```bash
  cat ~/Git-RV/accounts.txt | while read profile ; do for resource in ec2-instances ebs-volumes ami ec2-snapshots rds-snapshots;  do aws-vault exec $profile -- aws-resource-cleanup $resource  --dry-run --file dry-run.csv; done; done
  ```


- Multiple accounts, multiple resources, multiple regions:

  To go through all resources for each account one by one:


  ```bash
  cat ~/Git-RV/accounts.txt | while read profile ; do for resource in ec2-instances ebs-volumes ami ec2-snapshots rds-snapshots;  do for region in us-east-1 us-west-2; do  aws-vault exec $profile -- aws-resource-cleanup $resource  --dry-run --file final-dry-run.csv --region $region; done; done; done
  ```

  To go through all accounts for each resource one by one:


  ```bash
  for resource in ec2-instances ebs-volumes ami ec2-snapshots rds-snapshots; do cat ~/Git-RV/accounts.txt | while read profile;  do for region in us-east-1 us-west-2; do  aws-vault exec $profile -- aws-resource-cleanup $resource  --dry-run --file final-dry-run.csv --region $region; done; done; done
  ```


### Output

The tool writes output to both console and CSV file for both `--dry-run` and `--delete`. 

By default, The CSV file is named in the format `<AWS-account-name>-yyyy-mm-dd.csv` (ex: bankrate-qa-2023-03-26.csv)

You can pass a custom CSV file by using the `--file` flag. (ex: test.csv)

> **_NOTE:_** If the output file already exists, it will not overwrite the file. It will only append to the file.


