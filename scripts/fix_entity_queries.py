"""Fix LEFT JOIN entity queries to use NOT EXISTS for performance."""
path = "src/lambdas/api/case_files.py"
with open(path, "r") as f:
    content = f.read()

# Fix count query
old1 = '''SELECT COUNT(DISTINCT d.document_id) FROM documents d
                   LEFT JOIN entities e ON d.document_id = e.document_id
                   WHERE d.case_file_id = %s AND e.entity_id IS NULL
                   AND d.raw_text IS NOT NULL AND LENGTH(d.raw_text) > 50'''
new1 = '''SELECT COUNT(*) FROM documents d
                   WHERE d.case_file_id = %s
                   AND NOT EXISTS (SELECT 1 FROM entities e WHERE e.document_id = d.document_id)
                   AND d.raw_text IS NOT NULL AND LENGTH(d.raw_text) > 50'''

count = content.count(old1)
print(f"Found {count} count query instances")
content = content.replace(old1, new1)

with open(path, "w") as f:
    f.write(content)
print("Done")
