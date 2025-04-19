
# Observability

The Observability system in AiCore provides comprehensive tools for monitoring, analyzing, and optimizing LLM and embedding operations in real-time.

## Key Features

- **Real-time Metrics**: Track performance, latency, and usage patterns
- **Request Tracing**: Full visibility into request/response cycles
- **Usage Analytics**: Monitor token consumption and API costs
- **Performance Monitoring**: Identify bottlenecks and optimize operations
- **Custom Dashboards**: Visualize metrics with interactive charts

## Core Components

1. **[Collector](./collector.md)** - Centralized metrics collection system
   - Tracks all LLM/embedding operations
   - Stores historical performance data
   - Supports custom metric definitions

2. **[Dashboard](./dashboard.md)** - Interactive visualization interface
   - Real-time monitoring
   - Customizable views
   - Performance trend analysis

3. **[SQL Analytics](./sql.md)** - Powerful query capabilities
   - Standard SQL interface
   - Ad-hoc analysis
   - Integration with existing BI tools

4. **[Polars Integration](./polars.md)** - High-performance data analysis
   - Fast DataFrame operations
   - Large-scale data processing
   - Python-native interface

5. **[Logging System](../../aicore/logger.py)** - Unified logging infrastructure
   - Structured logging
   - Correlation IDs
   - Multiple output formats
   - See [Logger implementation](../../aicore/logger.py) for details

## Getting Started

To enable observability in your project:

1. Configure the collector in your settings
2. Import the dashboard components
3. Start tracking operations with minimal code changes

For detailed implementation, see our [example dashboard](../../examples/observability_dashboard.py).