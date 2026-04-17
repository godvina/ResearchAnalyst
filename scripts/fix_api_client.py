"""Fix the api_client.py timeout placement."""
import re

content = open('src/frontend/api_client.py').read()

# Remove all timeout=30 from _url() calls
content = re.sub(r'_url\(([^)]+),\s*timeout=30\)', r'_url(\1)', content)

# Now ensure all _session.get/post/delete/patch calls have timeout=30
# Match calls that DON'T already have timeout
def add_timeout(m):
    call = m.group(0)
    if 'timeout=' in call:
        return call
    # Insert timeout before the closing paren
    return call[:-1] + ', timeout=30)'

content = re.sub(r'_session\.\w+\([^)]+\)', add_timeout, content)

open('src/frontend/api_client.py', 'w').write(content)
print('Fixed api_client.py')
