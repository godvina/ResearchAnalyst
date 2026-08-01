import http.server
import os

os.chdir(os.path.join(os.path.dirname(__file__), "src", "frontend"))
print(f"Serving from: {os.getcwd()}")
print(f"URL: http://localhost:8080/investigator.html")
server = http.server.HTTPServer(("0.0.0.0", 8080), http.server.SimpleHTTPRequestHandler)
server.serve_forever()
