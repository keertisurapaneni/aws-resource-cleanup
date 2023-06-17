from setuptools import setup, find_packages

setup(
    name="aws-resource-cleanup",
    version='0.1.0',
    packages=find_packages(include=['libs', 'scripts', 'scripts.commands']),
    include_package_data=True,
    install_requires=[
        'click==8.1.3',
        'boto3==1.26.103',
    ],
    entry_points='''
        [console_scripts]
        aws-resource-cleanup=scripts.init:cli
    ''',
)
