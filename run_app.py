"""Launch the Research Analyst Streamlit app with correct paths."""
import os
import sys

# Add frontend directory to Python path so imports work
frontend_dir = os.path.join(os.path.dirname(__file__), "src", "frontend")
sys.path.insert(0, frontend_dir)

# Set API URL
os.environ.setdefault(
    "API_BASE_URL",
    "https://edb025my3i.execute-api.us-east-1.amazonaws.com/v1",
)

# Run streamlit
from streamlit.web.cli import main
sys.argv = ["streamlit", "run", os.path.join(frontend_dir, "app.py")]
main()
