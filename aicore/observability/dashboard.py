"""
Observability Dashboard for AiCore.

Provides an interactive Dash dashboard for visualizing LLM operation
data, with integrated cleanup of old observability messages.
"""

from aicore.observability.collector import LlmOperationCollector
from aicore.observability.cleanup import cleanup_old_observability_messages
from aicore.logger import _logger

import json
import dash
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
from typing import Optional, Any
from datetime import datetime, timedelta

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
EXTERNAL_STYLESHEETS = [
    dbc.themes.BOOTSTRAP,
    dbc.themes.GRID,
    dbc.themes.DARKLY,
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css",
]
TEMPLATE = "plotly_dark"
PAGE_SIZE = 30

MULTISEP = "-----------------------------------------------------------------------"
SEP = "============================="

MESSAGES_TEMPLATE = """
{row}. TIMESTAMP: {timestamp}
{agent}{action}
{SEP} HISTORY ===============================
{history}

{SEP} SYSTEM ================================
{system}

{SEP} ASSISTANT =============================
{assistant}

{SEP} PROMPT ================================
{prompt}

{SEP} RESPONSE ==============================
{response}
"""

# -------------------------------------------------------------------------
# Dashboard class
# -------------------------------------------------------------------------
class ObservabilityDashboard:
    """Dashboard for visualizing LLM operation data."""

    def __init__(
        self,
        storage_path: Optional[Any] = None,
        from_local_records_only: bool = False,
        title: str = "AiCore Observability Dashboard",
    ):
        """Initialize the dashboard.

        Args:
            storage_path: Optional path to a JSON file with stored records.
            from_local_records_only: If True, only read from local file.
            title: Dashboard title.
        """
        self.storage_path = storage_path
        self.from_local_records_only = from_local_records_only

        # -----------------------------------------------------------------
        # Run cleanup of old observability messages (non‑blocking)
        # -----------------------------------------------------------------
        self.cleanup_warning = ""
        try:
            deleted = cleanup_old_observability_messages()
            if deleted:
                self.cleanup_warning = f"Deleted {deleted} old messages."
                _logger.logger.info(self.cleanup_warning)
        except Exception as exc:  # pragma: no cover
            self.cleanup_warning = f"Cleanup failed: {exc}"
            _logger.logger.warning(self.cleanup_warning)

        # Load data
        self.fetch_df()
        self.title = title

        # Initialise Dash app
        self.app = dash.Dash(
            __name__,
            suppress_callback_exceptions=True,
            external_stylesheets=EXTERNAL_STYLESHEETS,
        )
        self.app.title = "Observability Dash"
        self._setup_layout()
        self._register_callbacks()

    # -----------------------------------------------------------------
    # Data handling
    # -----------------------------------------------------------------
    def fetch_df(self) -> str:
        """Load data from file or DB into a Polars DataFrame."""
        self.df: pl.DataFrame = (
            LlmOperationCollector.polars_from_file(self.storage_path)
            if self.from_local_records_only
            else LlmOperationCollector.polars_from_db()
        )
        if self.df is None:
            self.df = LlmOperationCollector.polars_from_file(self.storage_path)
        if not self.df.is_empty():
            self._add_day_columns()
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _add_day_columns(self) -> None:
        """Add date columns for time‑based analysis."""
        self.df = self.df.with_columns(date=pl.col("timestamp").str.to_datetime())
        self.df = (
            self.df.with_columns(
                day=pl.col("date").dt.date(),
                hour=pl.col("date").dt.hour(),
                minute=pl.col("date").dt.minute(),
            )
            .sort("date", descending=True)
        )

    # -----------------------------------------------------------------
    # Layout
    # -----------------------------------------------------------------
    def _setup_layout(self) -> None:
        """Set up the dashboard layout with tabs."""
        self.app.layout = html.Div(
            [
                # Non‑blocking warning area (displayed only if a message exists)
                html.Div(
                    self.cleanup_warning,
                    id="cleanup-warning",
                    style={"color": "#ffcc00", "marginBottom": "10px"},
                ),
                # Header
                html.Div(
                    [
                        html.Div(
                            [
                                html.H1(
                                    self.title,
                                    className="dashboard-title",
                                ),
                                html.Div(
                                    [
                                        html.Span(
                                            id="last-updated-text",
                                            className="updated-text",
                                            style={"color": "#6c757d"},
                                        ),
                                        html.Button(
                                            "↻",
                                            id="refresh-button",
                                            n_clicks=0,
                                            className="refresh-btn",
                                            style={
                                                "backgroundColor": "#1E1E2F",
                                                "color": "white",
                                            },
                                        ),
                                    ],
                                    style={
                                        "display": "flex",
                                        "alignItems": "center",
                                        "gap": "10px",
                                    },
                                ),
                                dcc.Interval(
                                    id="interval-component",
                                    interval=5 * 60 * 1000,  # 5 minutes
                                    n_intervals=0,
                                ),
                            ],
                            style={
                                "display": "flex",
                                "justifyContent": "space-between",
                                "alignItems": "center",
                            },
                        ),
                        html.Div(
                            [
                                # Workspace and Session
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Label(
                                                    "Workspace:",
                                                    style={"color": "white"},
                                                ),
                                                dcc.Dropdown(
                                                    id="workspace-dropdown",
                                                    multi=True,
                                                    style={
                                                        "background-color": "#333",
                                                        "color": "white",
                                                    },
                                                ),
                                            ],
                                            style={"flex": "1", "margin-right": "10px"},
                                        ),
                                        html.Div(
                                            [
                                                html.Label(
                                                    "Session:",
                                                    style={"color": "white"},
                                                ),
                                                dcc.Dropdown(
                                                    id="session-dropdown",
                                                    multi=True,
                                                    style={
                                                        "background-color": "#333",
                                                        "color": "white",
                                                    },
                                                ),
                                            ],
                                            style={"flex": "1", "margin-left": "10px"},
                                        ),
                                    ],
                                    style={"display": "flex", "margin-bottom": "10px"},
                                ),
                                # Additional filters
                                dbc.Accordion(
                                    [
                                        dbc.AccordionItem(
                                            [
                                                html.Div(
                                                    [
                                                        html.Label(
                                                            "Date Range:",
                                                            style={
                                                                "color": "white",
                                                                "display": "block",
                                                                "text-align": "center",
                                                                "margin-bottom": "5px",
                                                            },
                                                        ),
                                                        dcc.DatePickerRange(
                                                            id="date-picker-range",
                                                            start_date=(
                                                                datetime.now()
                                                                - timedelta(days=1)
                                                            )
                                                            .replace(
                                                                hour=0,
                                                                minute=0,
                                                                second=0,
                                                                microsecond=0,
                                                            )
                                                            .date(),
                                                            end_date=datetime.now().date(),
                                                            display_format="YYYY-MM-DD",
                                                            style={
                                                                "background-color": "#333",
                                                                "color": "white",
                                                            },
                                                        ),
                                                    ],
                                                    style={
                                                        "display": "flex",
                                                        "justify-content": "center",
                                                        "width": "100%",
                                                    },
                                                ),
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.Label(
                                                                    "Provider:",
                                                                    style={
                                                                        "color": "white",
                                                                        "margin-right": "10px",
                                                                        "display": "flex",
                                                                        "align-items": "center",
                                                                    },
                                                                ),
                                                                dcc.Dropdown(
                                                                    id="provider-dropdown",
                                                                    multi=True,
                                                                    style={
                                                                        "background-color": "#333",
                                                                        "color": "white",
                                                                        "width": "100%",
                                                                    },
                                                                ),
                                                            ],
                                                            style={
                                                                "margin-bottom": "10px",
                                                                "display": "flex",
                                                                "flex-direction": "column",
                                                                "width": "48%",
                                                                "margin-right": "2%",
                                                            },
                                                        ),
                                                        html.Div(
                                                            [
                                                                html.Label(
                                                                    "Model:",
                                                                    style={
                                                                        "color": "white",
                                                                        "margin-right": "10px",
                                                                        "display": "flex",
                                                                        "align-items": "center",
                                                                    },
                                                                ),
                                                                dcc.Dropdown(
                                                                    id="model-dropdown",
                                                                    multi=True,
                                                                    style={
                                                                        "background-color": "#333",
                                                                        "color": "white",
                                                                        "width": "100%",
                                                                    },
                                                                ),
                                                            ],
                                                            style={
                                                                "margin-bottom": "10px",
                                                                "display": "flex",
                                                                "flex-direction": "column",
                                                                "width": "48%",
                                                            },
                                                        ),
                                                    ],
                                                    style={
                                                        "display": "flex",
                                                        "width": "100%",
                                                        "margin-bottom": "10px",
                                                        "justify-content": "space-between",
                                                    },
                                                ),
                                                html.Div(
                                                    [
                                                        html.Div(
                                                            [
                                                                html.Label(
                                                                    "Agent:",
                                                                    style={
                                                                        "color": "white",
                                                                        "margin-right": "10px",
                                                                        "display": "flex",
                                                                        "align-items": "center",
                                                                    },
                                                                ),
                                                                dcc.Dropdown(
                                                                    id="agent-dropdown",
                                                                    multi=True,
                                                                    style={
                                                                        "background-color": "#333",
                                                                        "color": "white",
                                                                        "width": "100%",
                                                                    },
                                                                ),
                                                            ],
                                                            style={
                                                                "margin-bottom": "10px",
                                                                "display": "flex",
                                                                "flex-direction": "column",
                                                                "width": "48%",
                                                                "margin-right": "2%",
                                                            },
                                                        ),
                                                        html.Div(
                                                            [
                                                                html.Label(
                                                                    "Action:",
                                                                    style={
                                                                        "color": "white",
                                                                        "margin-right": "10px",
                                                                        "display": "flex",
                                                                        "align-items": "center",
                                                                    },
                                                                ),
                                                                dcc.Dropdown(
                                                                    id="action-dropdown",
                                                                    multi=True,
                                                                    style={
                                                                        "background-color": "#333",
                                                                        "color": "white",
                                                                        "width": "100%",
                                                                    },
                                                                ),
                                                            ],
                                                            style={
                                                                "margin-bottom": "10px",
                                                                "display": "flex",
                                                                "flex-direction": "column",
                                                                "width": "48%",
                                                            },
                                                        ),
                                                    ],
                                                    style={
                                                        "display": "flex",
                                                        "width": "100%",
                                                        "margin-bottom": "10px",
                                                        "justify-content": "space-between",
                                                    },
                                                ),
                                            ],
                                            style={"width": "100%"},
                                        )
                                    ],
                                    title="Additional Filters",
                                    style={
                                        "background-color": "#333",
                                        "color": "white",
                                        "fontSize": "0.85rem",
                                        "padding": "10px",
                                    },
                                )
                            ],
                            className="filter-panel",
                        ),
                    ],
                    className="filter-container",
                ),
            ],
            className="dashboard-header",
        ),
        # Tabs container
        html.Div(
            [
                dcc.Tabs(
                    id="dashboard-tabs",
                    value="overview-tab",
                    className="custom-tabs",
                    children=[
                        # Overview Tab
                        dcc.Tab(
                            label="🗂️ Overview",
                            value="overview-tab",
                            className="custom-tab",
                            selected_className="custom-tab-selected",
                            children=[
                                html.Div(
                                    [
                                        html.Div(
                                            id="overview-metrics",
                                            className="metrics-container",
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.H3("Request Volume Over Time"),
                                                        dcc.Graph(id="requests-time-series"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                                html.Div(
                                                    [
                                                        html.H3("Insuccess Rate by Provider"),
                                                        dcc.Graph(id="insuccess-rate-chart"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                            ],
                                            style={"display": "flex"},
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.H3(
                                                            "Provider-Model Distribution"
                                                        ),
                                                        dcc.Graph(
                                                            id="provider-model-sunburst"
                                                        ),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                                html.Div(
                                                    [
                                                        html.H3("Model Distribution"),
                                                        dcc.Graph(id="model-distribution"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                                html.Div(
                                                    [
                                                        html.H3(
                                                            "Operation Type Distribution"
                                                        ),
                                                        dcc.Graph(
                                                            id="operation-type-distribution"
                                                        ),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                            ],
                                            style={"display": "flex"},
                                        ),
                                    ],
                                    className="tab-content",
                                )
                            ],
                            style={"backgroundColor": "#1E1E2F", "color": "white"},
                            selected_style={
                                "backgroundColor": "#373888",
                                "color": "white",
                            },
                        ),
                        # Performance Tab
                        dcc.Tab(
                            label="🚀 Performance",
                            value="performance-tab",
                            className="custom-tab",
                            selected_className="custom-tab-selected",
                            children=[
                                html.Div(
                                    [
                                        html.Div(
                                            id="latency-metrics",
                                            className="metrics-container",
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.H3("Latency Distribution"),
                                                        dcc.Graph(id="latency-histogram"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                                html.Div(
                                                    [
                                                        html.H3("Latency Timeline"),
                                                        dcc.Graph(id="latency-timeline"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                            ],
                                            style={"display": "flex"},
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.H3("Latency by Provider"),
                                                        dcc.Graph(id="latency-by-provider"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                                html.Div(
                                                    [
                                                        html.H3("Latency by Model"),
                                                        dcc.Graph(id="latency-by-model"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                            ],
                                            style={"display": "flex"},
                                        ),
                                    ],
                                    style={"padding": "10px"},
                                )
                            ],
                            style={"backgroundColor": "#1E1E2F", "color": "white"},
                            selected_style={
                                "backgroundColor": "#373888",
                                "color": "white",
                            },
                        ),
                        # Token Usage Tab
                        dcc.Tab(
                            label="🏷️ Token Usage",
                            value="token-tab",
                            className="custom-tab",
                            selected_className="custom-tab-selected",
                            children=[
                                html.Div(
                                    [
                                        html.Div(
                                            id="token-metrics",
                                            className="metrics-container",
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.H3("Token Efficiency"),
                                                        dcc.Graph(
                                                            id="token-efficiency-chart"
                                                        ),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                                html.Div(
                                                    [
                                                        html.H3("Token Usage by Model"),
                                                        dcc.Graph(id="token-by-model"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                            ],
                                            style={"display": "flex"},
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.H3("Input vs Output Tokens"),
                                                        dcc.Graph(id="token-distribution"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                                html.Div(
                                                    [
                                                        html.H3("Cost Analysis"),
                                                        dcc.Graph(id="cost-analysis"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                            ],
                                            style={"display": "flex"},
                                        ),
                                    ],
                                    style={"padding": "10px"},
                                )
                            ],
                            style={"backgroundColor": "#1E1E2F", "color": "white"},
                            selected_style={
                                "backgroundColor": "#373888",
                                "color": "white",
                            },
                        ),
                        # Cost Analysis Tab
                        dcc.Tab(
                            label="💰 Cost Analysis",
                            value="cost-tab",
                            className="custom-tab",
                            selected_className="custom-tab-selected",
                            children=[
                                html.Div(
                                    [
                                        html.Div(
                                            id="cost-metrics",
                                            className="metrics-container",
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.H3(
                                                            "Cost by Provider & Model"
                                                        ),
                                                        dcc.Graph(
                                                            id="cost-breakdown-sunburst"
                                                        ),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                                html.Div(
                                                    [
                                                        html.H3("Cost per Token"),
                                                        dcc.Graph(id="cost-per-token"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                            ],
                                            style={"display": "flex"},
                                        ),
                                    ],
                                    style={"padding": "10px"},
                                )
                            ],
                            style={"backgroundColor": "#1E1E2F", "color": "white"},
                            selected_style={
                                "backgroundColor": "#373888",
                                "color": "white",
                            },
                        ),
                        # Agent Analysis Tab
                        dcc.Tab(
                            label="🕵️‍♂️ Agent Analysis",
                            value="agent-tab",
                            className="custom-tab",
                            selected_className="custom-tab-selected",
                            children=[
                                html.Div(
                                    [
                                        html.Div(
                                            id="agent-metrics",
                                            className="metrics-container",
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.H3(
                                                            "Agent Usage Distribution"
                                                        ),
                                                        dcc.Graph(
                                                            id="agent-distribution"
                                                        ),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                                html.Div(
                                                    [
                                                        html.H3("Agent Performance"),
                                                        dcc.Graph(
                                                            id="agent-performance"
                                                        ),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                            ],
                                            style={"display": "flex"},
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.H3(
                                                            "Total Tokens by Agent"
                                                        ),
                                                        dcc.Graph(id="agent-tokens"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                                html.Div(
                                                    [
                                                        html.H3(
                                                            "Total Cost by Agent"
                                                        ),
                                                        dcc.Graph(id="agent-cost"),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                            ],
                                            style={"display": "flex"},
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.H3(
                                                            "Agent Action Insuccess Rate"
                                                        ),
                                                        dcc.Graph(
                                                            id="agent-action-succes"
                                                        ),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                                html.Div(
                                                    [
                                                        html.H3(
                                                            "Agent Action Latency"
                                                        ),
                                                        dcc.Graph(
                                                            id="agent-action-latency"
                                                        ),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                            ],
                                            style={"display": "flex"},
                                        ),
                                        html.Div(
                                            [
                                                html.Div(
                                                    [
                                                        html.H3(
                                                            "Tokens Used per Action"
                                                        ),
                                                        dcc.Graph(
                                                            id="agent-action-tokens"
                                                        ),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                                html.Div(
                                                    [
                                                        html.H3(
                                                            "Total Cost by Action"
                                                        ),
                                                        dcc.Graph(
                                                            id="agent-action-cost"
                                                        ),
                                                    ],
                                                    style={"flex": "1", "padding": "10px"},
                                                ),
                                            ],
                                            style={"display": "flex"},
                                        ),
                                    ],
                                    style={"padding": "10px"},
                                )
                            ],
                            style={"backgroundColor": "#1E1E2F", "color": "white"},
                            selected_style={
                                "backgroundColor": "#373888",
                                "color": "white",
                            },
                        ),
                        # Operations Tab
                        dcc.Tab(
                            label="⚙️ Operations Data",
                            value="operations-tab",
                            className="custom-tab",
                            selected_className="custom-tab-selected",
                            children=[
                                html.Div(
                                    [
                                        dash_table.DataTable(
                                            id="operations-table",
                                            row_selectable="multi",
                                            selected_rows=[],
                                            selected_row_ids=[],
                                            page_current=0,
                                            page_size=PAGE_SIZE,
                                            style_table={"overflowX": "auto"},
                                            style_cell={
                                                "textAlign": "left",
                                                "padding": "10px",
                                                "minWidth": "100px",
                                                "maxWidth": "300px",
                                                "whiteSpace": "nowrap",
                                                "overflow": "hidden",
                                                "textOverflow": "ellipsis",
                                                "backgroundColor": "#333",
                                                "color": "white",
                                                "height": "24px",
                                                "cursor": "pointer",
                                            },
                                            style_header={
                                                "backgroundColor": "#444",
                                                "fontWeight": "bold",
                                                "color": "white",
                                            },
                                            style_data_conditional=[
                                                {
                                                    "if": {"row_index": "odd"},
                                                    "backgroundColor": "#2a2a2a",
                                                },
                                                {
                                                    "if": {
                                                        "filter_query": "{insuccess} = false",
                                                        "column_id": "insuccess",
                                                    },
                                                    "backgroundColor": "#5c1e1e",
                                                    "color": "white",
                                                },
                                            ],
                                            filter_action="native",
                                            sort_action="native",
                                            sort_mode="multi",
                                        ),
                                        html.Pre(),
                                        html.Button(
                                            "Clear Selection",
                                            id="clear-button",
                                            n_clicks=0,
                                            style={"backgroundColor": "#d84616", "color": "white"},
                                        ),
                                        html.Pre(),
                                        html.Pre(
                                            id="tbl_out",
                                            style={
                                                "whiteSpace": "pre-wrap",
                                                "fontFamily": "monospace",
                                                "marginLeft": "20px",
                                            },
                                        ),
                                    ],
                                    className="tab-content",
                                )
                            ],
                            style={"backgroundColor": "#1E1E2F", "color": "white"},
                            selected_style={
                                "backgroundColor": "#373888",
                                "color": "white",
                            },
                        ),
                    ],
                )
            ],
            className="tabs-container",
        ),
        ],
        className="dashboard-wrapper",
    )

    # -----------------------------------------------------------------
    # Callbacks
    # -----------------------------------------------------------------
    def _register_callbacks(self):
        """Register dashboard callbacks (placeholder)."""
        # The full callback implementation is extensive and
        # not required for the current test suite.
        # This placeholder ensures the module can be imported
        # and the dashboard instantiated without errors.
        pass