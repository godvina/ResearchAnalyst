import boto3
ec2 = boto3.client('ec2', region_name='us-east-1')
ud = open('scripts/ec2_batch_userdata.sh', 'r').read()
r = ec2.run_instances(
    ImageId='ami-0c02fb55956c7d316',
    InstanceType='t3.small',
    IamInstanceProfile={'Name': 'NikityLoaderEC2Profile'},
    UserData=ud,
    TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Name', 'Value': 'bedrock-batch-nova-v3'}]}],
    MinCount=1, MaxCount=1,
)
print('Launched:', r['Instances'][0]['InstanceId'])
