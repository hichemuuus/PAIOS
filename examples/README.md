# Examples

This directory contains example workflows, API usage, and task configurations for Veyron.

## API Examples

### Submit a task
```python
import requests

response = requests.post(
    "http://localhost:8000/api/agent",
    json={"goal": "Check my system memory usage"}
)
print(response.json())
```

### Check task status
```python
import requests

task_id = "abc-123"
response = requests.get(f"http://localhost:8000/api/tasks/{task_id}")
print(response.json())
```

### List available tools
```python
import requests

response = requests.get("http://localhost:8000/api/tools")
print(response.json())
```

## Workflow Examples

(Workflow YAML/JSON examples will be added as the workflow system matures)

## Plugin Examples

See the example plugin at `backend/plugins/example_tool_plugin.py`
