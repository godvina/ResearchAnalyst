import boto3
e = boto3.client('ec2', region_name='us-east-1')
r = e.get_console_output(InstanceId='i-052568e97c7b26874', Latest=True)
o = r.get('Output', '')
lines = o.split('\n')
# Find script-related lines
relevant = [l for l in lines if 'Neptune' in l or 'sync' in l.lower() or '===' in l 
            or 'Error' in l or 'Traceback' in l or 'Running' in l or 'Current' in l
            or 'FAILED' in l or 'created' in l.lower() or 'Progress' in l]
if relevant:
    for l in relevant[-8:]:
        print(l.strip()[-120:])
else:
    # Show last cloud-init lines
    ci = [l for l in lines if 'cloud-init' in l]
    for l in ci[-3:]:
        print(l.strip()[-120:])
    if not ci:
        print("No output yet")
