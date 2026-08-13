# Personal Fitness AI Assistant

## Local Python Environment

This project uses a local virtual environment for the Streamlit application dependencies. Langflow is intentionally not installed into `.venv` by default because this architecture can run Langflow separately, either in its own environment or in the cloud.

Commands used for this milestone:

```bash
/opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install -r requirements-dev.txt
```

Activation command:

```bash
source .venv/bin/activate
```
