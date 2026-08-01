"""Poll Bedrock batch job, then launch EC2 to load results when done."""
import boto3
import time

JOB_ARN = 'arn:aws:bedrock:us-east-1:974220725866:model-invocation-job/ldhi23bwhsje'
REGION = 'us-east-1'

bedrock = boto3.client('bedrock', region_name=REGION)
ec2 = boto3.client('ec2', region_name=REGION)
s3 = boto3.client('s3', region_name=REGION)

print("Polling batch job...")
while True:
    j = bedrock.get_model_invocation_job(jobIdentifier=JOB_ARN)
    status = j['status']
    print(f"  {time.strftime('%H:%M:%S')} Status: {status}")
    
    if status == 'Completed':
        print("Job completed! Launching result loader EC2...")
        break
    elif status == 'Failed':
        print(f"Job FAILED: {j.get('message', 'unknown')}")
        exit(1)
    elif status in ('Stopping', 'Stopped'):
        print("Job stopped.")
        exit(1)
    
    time.sleep(60)

# Update the load script output prefix to match this job
load_script = s3.get_object(
    Bucket='research-analyst-data-lake-974220725866',
    Key='deploy/ec2_load_batch_results.py'
)['Body'].read().decode('utf-8')

# Replace the output prefix with the correct job ID
load_script = load_script.replace(
    'output/17uppsaiaf4c/',
    'output-v3/ldhi23bwhsje/'
)
s3.put_object(
    Bucket='research-analyst-data-lake-974220725866',
    Key='deploy/ec2_load_batch_results.py',
    Body=load_script.encode('utf-8')
)
print("Updated load script with correct output path")

# Launch EC2
userdata = open('scripts/ec2_load_results_userdata.sh', 'r').read()
r = ec2.run_instances(
    ImageId='ami-0c02fb55956c7d316',
    InstanceType='t3.small',
    IamInstanceProfile={'Name': 'NikityLoaderEC2Profile'},
    UserData=userdata,
    TagSpecifications=[{'ResourceType': 'instance', 'Tags': [{'Key': 'Name', 'Value': 'load-batch-results-v3'}]}],
    MinCount=1, MaxCount=1,
)
iid = r['Instances'][0]['InstanceId']
print(f"Launched EC2: {iid}")
print("It will load 75K entity extraction results into Aurora, then self-terminate.")
