
# Observability Module

The Observability Module in AiCore provides a comprehensive solution for tracking, analyzing, and visualizing LLM operations. It automatically collects detailed metrics—including request parameters, responses, token usage, latency, and error logs—and supports both file-based and SQL-based persistence for robust data management.

## Overview

- **Data Collection:** Automatically captures detailed information about each LLM operation.
- **Storage Options:** Persist operation records as JSON files or in SQL databases.
- **Interactive Dashboard:** Utilize a Dash and Plotly based dashboard for visualizing metrics in real-time.

## Observability Collector

The collector, implemented in `aicore/observability/collector.py`, is responsible for aggregating and persisting observability data. Its key features include:

- **LlmOperationRecord:** A Pydantic model representing a single LLM operation. It typically includes:
  - `session_id`: Unique identifier for the session.
  - `provider`: The LLM provider used (e.g., OpenAI, Mistral).
  - `completion_args`: Parameters used to generate the completion.
  - `response`: The generated output from the LLM.
  - `latency_ms`: The time taken to process the request.
  - Additional computed properties such as total token count and success status.
  
- **LlmOperationCollector:** This class is tasked with:
  - **Aggregation:** Temporarily storing records in memory.
  - **File-Based Storage:** Saving records to a JSON file (with default location/settings controlled by the `OBSERVABILITY_DIR` and `OBSERVABILITY_FILE` environment variables).
  - **SQL Persistence:** Inserting records into a SQL database using SQLAlchemy. To enable this feature, configure the `CONNECTION_STRING` and `ASYNC_CONNECTION_STRING` environment variables appropriately.

## Dashboard

The interactive dashboard, defined in `aicore/observability/dashboard.py`, leverages modern visualization tools to provide actionable insights into LLM operations. Its main components include:

- **Dash & Plotly:** For building interactive web-based visualizations such as:
  - Latency histograms.
  - Token usage charts.
  - Daily request volume graphs.
  - Cost breakdown overviews.
  
- **Polars:** Utilized for fast data manipulation to efficiently transform stored records for visualization.

### Launching the Dashboard

To start the dashboard, you can use the following Python snippet:

```python
from aicore.observability import ObservabilityDashboard

dashboard = ObservabilityDashboard(storage_path="path/to/llm_operations.json")
dashboard.run_server(debug=True, port=8050)
```

This command will launch a web server displaying various visualizations based on your observability data.

## SQL Session Integration

For scenarios where persistent storage in a SQL database is desirable, AiCore supports direct SQL session integration. To enable this feature:

1. **Configuration:**
   - Set the `CONNECTION_STRING` environment variable (e.g., `postgresql://user:password@localhost/dbname`) for synchronous operations.
   - Set the `ASYNC_CONNECTION_STRING` environment variable (e.g., `postgresql+asyncpg://user:password@localhost/dbname`) for asynchronous operations.

2. **Automatic Table Creation:**
   - The collector automatically creates necessary tables (`Session`, `Message`, and `Metric`) to store all operational data when a valid SQL connection is provided.
   
This setup ensures that all LLM operations can be persisted reliably and queried later for detailed analysis.

## Example Usage

AiCore includes an example in `examples/observability_dashboard.py` which illustrates:
1. **Dashboard Launch:** Initiating the interactive dashboard with a sample set of LLM operations.
2. **Data Population:** Automatically generating and persisting sample data when the collector’s data source is empty.

Using the dashboard alongside SQL integration empowers users to gain deep insights into system performance and usage patterns.

## Further Information

For more implementation details and advanced configuration options, refer to the following:
- **Source Code:** Explore [`aicore/observability/collector.py`](../aicore/observability/collector.py) and [`aicore/observability/dashboard.py`](../aicore/observability/dashboard.py) for underlying details.
- **Environment and YAML Configuration:** Customize settings via environment variables and YAML files as needed.

---

*This documentation provides an initial overview of the Observability Module. Future updates will expand on advanced configurations, additional metrics, and enhanced visualizations based on user feedback and evolving project requirements.*