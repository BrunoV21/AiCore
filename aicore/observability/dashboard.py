from aicore.observability.collector import LlmOperationCollector
from aicore.logger import _logger

import dash
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
from typing import Optional, Any
from datetime import datetime, timedelta
from pathlib import Path

EXTERNAL_STYLESHEETS = [
    dbc.themes.BOOTSTRAP,
    dbc.themes.GRID,
    dbc.themes.DARKLY,
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"
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

class ObservabilityDashboard:
    """
    Dashboard for visualizing LLM operation data.
    
    This class implements a Dash application that provides interactive visualizations
    of LLM usage history, including request volumes, latency metrics, token usage,
    model distribution, and other relevant analytics.
    """
    
    def __init__(self,
            storage_path: Optional[Any] = None,
            from_local_records_only :bool=False,
            title: str = "AiCore Observability Dashboard",
            lazy: bool = False):
        """
        Initialize the dashboard.

        Args:
            storage_path: Path to observability data storage
            from_local_records_only: If True, only load data from local files
            title: Dashboard title
            lazy: If True, only pre-load session_ids and load full data on demand
        """
        self.storage_path = storage_path
        self.from_local_records_only = from_local_records_only
        self.default_days = 5  # Default to 5 day of data for initial load
        self.lazy = lazy
        self.available_sessions = []  # Store available session_ids for lazy loading

        if self.lazy:
            # In lazy mode, only fetch the list of available session_ids
            self.available_sessions = self.fetch_session_list()
            self.df = pl.DataFrame()  # Empty dataframe initially
        else:
            # In normal mode, fetch all data
            self.fetch_df(days=self.default_days)

        self.title = title
        self.app = dash.Dash(
            __name__,
            suppress_callback_exceptions=True,
            external_stylesheets=EXTERNAL_STYLESHEETS
        )
        self.app.title = "Observability Dash"
        self._setup_layout()
        self._register_callbacks()

    def fetch_session_list(self) -> list:
        """
        Fetch the list of available session_ids from storage and/or database.
        This is used in lazy mode to pre-load only session identifiers.

        Returns:
            List of available session_id strings
        """
        session_ids = set()

        # Scan local files for session directories
        if self.storage_path or self.from_local_records_only:
            try:
                collector = LlmOperationCollector.fom_observable_storage_path(self.storage_path)
                root_dir = Path(collector.storage_path)
                print(f"[fetch_session_list] Scanning directory: {root_dir}")

                if root_dir.exists():
                    # Each subdirectory represents a session_id
                    session_dirs = [d.name for d in root_dir.iterdir() if d.is_dir()]
                    print(f"[fetch_session_list] Found {len(session_dirs)} session directories: {session_dirs}")
                    session_ids.update(session_dirs)
                else:
                    print(f"[fetch_session_list] Directory does not exist: {root_dir}")
            except Exception as e:
                print(f"[fetch_session_list] ERROR scanning local session directories: {e}")
                _logger.logger.warning(f"Error scanning local session directories: {e}")

        # Query database for session_ids if not restricted to local records only
        if not self.from_local_records_only:
            try:
                # Query distinct session_ids from database
                collector = LlmOperationCollector()
                if collector._session_factory and collector._engine:
                    from aicore.observability.models import Session
                    with collector._session_factory() as session:
                        results = session.query(Session.session_id).distinct().all()
                        db_sessions = [r[0] for r in results]
                        print(f"[fetch_session_list] Found {len(db_sessions)} sessions in DB")
                        session_ids.update(db_sessions)
            except Exception as e:
                print(f"[fetch_session_list] ERROR querying database for session_ids: {e}")
                _logger.logger.warning(f"Error querying database for session_ids: {e}")

        result = sorted(list(session_ids))
        print(f"[fetch_session_list] Total available sessions: {len(result)}")
        return result

    def fetch_df(self, days=None, session_ids=None):
        """
        Fetch data with optional day limit and session filtering.

        Args:
            days: Number of days to look back (optional)
            session_ids: List of session_ids to load (optional, for lazy loading)
        """
        if session_ids:
            # Load specific sessions only (lazy mode)
            print(f"[fetch_df] Fetching sessions: {session_ids}")
            print(f"[fetch_df] Storage path: {self.storage_path}")
            print(f"[fetch_df] from_local_records_only: {self.from_local_records_only}")
            session_dfs = []
            for session_id in session_ids:
                # Try loading from local files first
                try:
                    print(f"[fetch_df] Attempting to load {session_id} from files...")
                    df = LlmOperationCollector.polars_from_file(
                        self.storage_path,
                        session_id=session_id
                    )
                    if df is not None and not df.is_empty():
                        print(f"[fetch_df] Loaded {len(df)} rows for {session_id} from files")
                        session_dfs.append(df)
                    else:
                        print(f"[fetch_df] No data found in files for {session_id}")
                        # If not found in files and DB is available, try DB
                        if not self.from_local_records_only:
                            print(f"[fetch_df] Attempting to load {session_id} from DB...")
                            df = LlmOperationCollector.polars_from_db(session_id=session_id)
                            if df is not None and not df.is_empty():
                                print(f"[fetch_df] Loaded {len(df)} rows for {session_id} from DB")
                                session_dfs.append(df)
                            else:
                                print(f"[fetch_df] No data found in DB for {session_id}")
                except Exception as e:
                    print(f"[fetch_df] ERROR loading session {session_id}: {e}")
                    _logger.logger.warning(f"Error loading session {session_id}: {e}")

            # Combine new session dataframes
            print(f"[fetch_df] Total session_dfs collected: {len(session_dfs)}")
            if session_dfs:
                new_df = pl.concat(session_dfs)
                print(f"[fetch_df] Concatenated new_df has {len(new_df)} rows")
                # Append to existing dataframe if not empty
                if not self.df.is_empty():
                    print(f"[fetch_df] Appending to existing df with {len(self.df)} rows")
                    self.df = pl.concat([self.df, new_df])
                else:
                    print("[fetch_df] Setting df to new_df (was empty)")
                    self.df = new_df
                print(f"[fetch_df] Final df has {len(self.df)} rows")
                print(self.df)
        else:
            # Load all data (normal mode)
            self.df = (
                LlmOperationCollector.polars_from_file(self.storage_path)
                if self.from_local_records_only
                else LlmOperationCollector.polars_from_db()
            )
            if self.df is None:
                self.df = LlmOperationCollector.polars_from_file(self.storage_path)

        if not self.df.is_empty():
            # Add date column if not present
            if "date" not in self.df.columns:
                self.add_day_col()
            if days is not None:
                # Filter to only include the last 'days' days
                cutoff_date = datetime.now() - timedelta(days=days)
                self.df = self.df.filter(pl.col("date") >= cutoff_date)

        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def add_day_col(self):
        """Add date columns for time-based analysis"""
        self.df = self.df.with_columns(date=pl.col("timestamp").str.to_datetime())
        self.df = self.df.with_columns(
            day=pl.col("date").dt.date(),
            hour=pl.col("date").dt.hour(),
            minute=pl.col("date").dt.minute()
        ).sort("date", descending=True)
    
    def _setup_layout(self):
        """Set up the dashboard layout with tabs."""
        self.app.layout = html.Div([
            # Store components for state management
            dcc.Store(id='session-state', data={'selected_rows': [], 'selected_row_ids': [], 'active_cell': None}),
            dcc.Store(id='filter-state', data={}),
            
            # Header
            html.Div([
                html.Div([
                    html.H1(self.title, className="dashboard-title"),
                    html.Div([
                        html.Div([
                            html.Span(id="last-updated-text", className="updated-text", style={"color": "#6c757d"}),
                            html.Div(id="loading-indicator", children=[
                                dcc.Loading(
                                    id="loading-icon",
                                    children=[html.Div(id="loading-output")],
                                    type="circle",
                                    color="#373888"
                                )
                            ], style={"display": "inline-block", "marginLeft": "10px"}),
                        ], style={"display": "flex", "alignItems": "center"}),
                        html.Div([
                            html.Button("↻", id="refresh-button", n_clicks=0, className="refresh-btn", style={"backgroundColor": "#1E1E2F", "color": "white"}),
                            html.Div([
                                dbc.DropdownMenu(
                                    [
                                        dbc.DropdownMenuItem("Last Hour", id="last-hour-option"),
                                        dbc.DropdownMenuItem("Last 6 Hours", id="last-6h-option"),
                                        dbc.DropdownMenuItem("Last 24 Hours", id="last-24h-option"),
                                        dbc.DropdownMenuItem("Last 7 Days", id="last-7d-option"),
                                        dbc.DropdownMenuItem("Custom Range", id="custom-range-option"),
                                    ],
                                    label="Time Range",
                                    color="#1E1E2F",
                                    className="time-range-dropdown"
                                ),
                            ], style={"marginLeft": "10px", "display": "inline-block"}),
                        ], style={"display": "flex", "alignItems": "center"}),
                    ], style={"display": "flex", "alignItems": "center", "gap": "10px"}),
                    dcc.Interval(
                        id="interval-component",
                        interval=5 * 60 * 1000,  # 5 minutes
                        n_intervals=0
                    )
                ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"}),
                html.Div([
                    html.Div([
                        # Workspace and Session in the same row
                        html.Div([
                            html.Div([
                                html.Label("Workspace:", style={"color": "white"}),
                                dcc.Dropdown(
                                    id='workspace-dropdown',
                                    multi=True,
                                    style={"background-color": "#333", "color": "white"},
                                ),
                            ], style={"flex": "1", "margin-right": "10px"}),

                            html.Div([
                                html.Label("Session:", style={"color": "white"}),
                                dcc.Dropdown(
                                    id='session-dropdown',
                                    multi=True,
                                    style={"background-color": "#333", "color": "white"}
                                ),
                            ], style={"flex": "1", "margin-left": "10px"}),
                        ], style={"display": "flex", "margin-bottom": "10px"}),

                        # Additional filters hidden inside an accordion
                        dbc.Accordion(
                            [
                                dbc.AccordionItem(
                                    [
                                        html.Div([
                                            html.Label("Date Range:", style={"color": "white", "display": "block", "text-align": "center", "margin-bottom": "5px"}),
                                            html.Div([
                                                dcc.DatePickerRange(
                                                    id='date-picker-range',
                                                    start_date=(datetime.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).date(),
                                                    end_date=datetime.now().date(),
                                                    display_format='YYYY-MM-DD',
                                                    style={"background-color": "#333", "color": "white"}
                                                ),
                                            ], style={"display": "flex", "justify-content": "center", "width": "100%"}),
                                        ], style={"margin-bottom": "10px", "width": "100%", "display": "flex", "flex-direction": "column", "align-items": "center"}),

                                        html.Div([
                                            html.Div([
                                                html.Div([
                                                    html.Label("Provider:", style={"color": "white", "margin-right": "10px", "display": "flex", "align-items": "center"}),
                                                    dcc.Dropdown(
                                                        id='provider-dropdown',
                                                        multi=True,
                                                        style={"background-color": "#333", "color": "white", "width": "100%"}
                                                    ),
                                                ], style={"margin-bottom": "10px", "display": "flex", "flex-direction": "column", "width": "48%", "margin-right": "2%"}),
                                                html.Div([
                                                    html.Label("Model:", style={"color": "white", "margin-right": "10px", "display": "flex", "align-items": "center"}),
                                                    dcc.Dropdown(
                                                        id='model-dropdown',
                                                        multi=True,
                                                        style={"background-color": "#333", "color": "white", "width": "100%"}
                                                    ),
                                                ], style={"margin-bottom": "10px", "display": "flex", "flex-direction": "column", "width": "48%"}),
                                            ], style={"display": "flex", "width": "100%", "margin-bottom": "10px", "justify-content": "space-between"}),

                                            html.Div([
                                                html.Div([
                                                    html.Label("Agent:", style={"color": "white", "margin-right": "10px", "display": "flex", "align-items": "center"}),
                                                    dcc.Dropdown(
                                                        id='agent-dropdown',
                                                        multi=True,
                                                        style={"background-color": "#333", "color": "white", "width": "100%"}
                                                    ),
                                                ], style={"margin-bottom": "10px", "display": "flex", "flex-direction": "column", "width": "48%", "margin-right": "2%"}),
                                                html.Div([
                                                    html.Label("Action:", style={"color": "white", "margin-right": "10px", "display": "flex", "align-items": "center"}),
                                                    dcc.Dropdown(
                                                        id='action-dropdown',
                                                        multi=True,
                                                        style={"background-color": "#333", "color": "white", "width": "100%"}
                                                    ),
                                                ], style={"margin-bottom": "10px", "display": "flex", "flex-direction": "column", "width": "48%"})
                                            ], style={"display": "flex", "width": "100%", "margin-bottom": "10px", "justify-content": "space-between"})
                                        ], style={"width": "100%"})
                                    ],
                                    title="Additional Filters", style={
                                        "background-color": "#333",
                                        "color": "white",
                                        "fontSize": "0.85rem",
                                        "padding": "10px"
                                    }
                                )
                            ],
                            start_collapsed=True,
                            flush=True
                        )
                    ], className="filter-panel"),
                ], className="filter-container"),
            ], className="dashboard-header"),

            # Tabs container
            html.Div([
                dcc.Tabs(id="dashboard-tabs", value='overview-tab', className="custom-tabs", children=[

                    # Overview Tab
                    dcc.Tab(label='🗂️ Overview', value='overview-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
                            html.Div(id='overview-metrics', className="metrics-container"),
                            html.Div([
                                html.Div([
                                    html.H3("Request Volume Over Time"),
                                    dcc.Graph(id='requests-time-series')
                                ], style={'flex': '1', 'padding': '10px'}),
                                html.Div([
                                    html.H3("Insuccess Rate by Provider"),
                                    dcc.Graph(id='insuccess-rate-chart')
                                ], style={'flex': '1', 'padding': '10px'})
                            ], style={'display': 'flex'}),

                            html.Div([
                                html.Div([
                                    html.H3("Provider-Model Distribution"),
                                    dcc.Graph(id='provider-model-sunburst')
                                ], style={'flex': '1', 'padding': '10px'}),
                                html.Div([
                                    html.H3("Model Distribution"),
                                    dcc.Graph(id='model-distribution')
                                ], style={'flex': '1', 'padding': '10px'}),
                                html.Div([
                                    html.H3("Operation Type Distribution"),
                                    dcc.Graph(id='operation-type-distribution')
                                ], style={'flex': '1', 'padding': '10px'})
                            ], style={'display': 'flex'}),
                        ], className="tab-content")
                    ], style={"backgroundColor": "#1E1E2F", "color": "white"}, selected_style={"backgroundColor": "#373888", "color": "white"}),

                    # Performance Tab
                    dcc.Tab(label='🚀 Performance', value='performance-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
                            html.Div(id='latency-metrics', className="metrics-container"),
                            # Row 1: Overall latency stats
                            html.Div([
                                html.Div([
                                    html.H3("Latency Distribution"),
                                    dcc.Graph(id='latency-histogram')
                                ], style={'flex': '1', 'padding': '10px'}),
                                html.Div([
                                    html.H3("Latency Timeline"),
                                    dcc.Graph(id='latency-timeline')
                                ], style={'flex': '1', 'padding': '10px'})
                            ], style={'display': 'flex'}),
                            
                            # Row 2: Latency comparisons
                            html.Div([
                                html.Div([
                                    html.H3("Latency by Provider"),
                                    dcc.Graph(id='latency-by-provider')
                                ], style={'flex': '1', 'padding': '10px'}),
                                html.Div([
                                    html.H3("Latency by Model"),
                                    dcc.Graph(id='latency-by-model')
                                ], style={'flex': '1', 'padding': '10px'})
                            ], style={'display': 'flex'})
                        ], style={'padding': '10px'})
                    ], style={"backgroundColor": "#1E1E2F", "color": "white"}, selected_style={"backgroundColor": "#373888", "color": "white"}),

                    # Token Usage Tab
                    dcc.Tab(label='🏷️ Token Usage', value='token-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([                            
                            html.Div(id='token-metrics', className="metrics-container"),
                            # Row 1: Token efficiency and usage
                            html.Div([
                                html.Div([
                                    html.H3("Token Efficiency"),
                                    dcc.Graph(id='token-efficiency-chart')
                                ], style={'flex': '1', 'padding': '10px'}),
                                html.Div([
                                    html.H3("Token Usage by Model"),
                                    dcc.Graph(id='token-by-model')
                                ], style={'flex': '1', 'padding': '10px'})
                            ], style={'display': 'flex'}),
                            
                            # Row 2: Token distribution and cost analysis
                            html.Div([
                                html.Div([
                                    html.H3("Input vs Output Tokens"),
                                    dcc.Graph(id='token-distribution')
                                ], style={'flex': '1', 'padding': '10px'}),
                                html.Div([
                                    html.H3("Cost Analysis"),
                                    dcc.Graph(id='cost-analysis')
                                ], style={'flex': '1', 'padding': '10px'})
                            ], style={'display': 'flex'})
                        ], style={'padding': '10px'})
                    ], style={"backgroundColor": "#1E1E2F", "color": "white"}, selected_style={"backgroundColor": "#373888", "color": "white"}),

                    # Cost Analysis Tab
                    dcc.Tab(label='💰 Cost Analysis', value='cost-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([                            
                            html.Div(id='cost-metrics', className="metrics-container"),
                            # Row 1: Cost breakdown and cost per token
                            html.Div([
                                html.Div([
                                    html.H3("Cost by Provider & Model"),
                                    dcc.Graph(id='cost-breakdown-sunburst')
                                ], style={'flex': '1', 'padding': '10px'}),
                                html.Div([
                                    html.H3("Cost per Token"),
                                    dcc.Graph(id='cost-per-token')
                                ], style={'flex': '1', 'padding': '10px'})
                            ], style={'display': 'flex'})
                        ], style={'padding': '10px'})
                    ], style={"backgroundColor": "#1E1E2F", "color": "white"}, selected_style={"backgroundColor": "#373888", "color": "white"}),

                    # Agent Analysis Tab
                    dcc.Tab(label='🕵️‍♂️ Agent Analysis', value='agent-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([                            
                            html.Div(id='agent-metrics', className="metrics-container"),
                            # Row 1: Overall agent usage and performance
                            html.Div([
                                html.Div([
                                    html.H3("Agent Usage Distribution"),
                                    dcc.Graph(id='agent-distribution')
                                ], style={'flex': '1', 'padding': '10px'}),
                                html.Div([
                                    html.H3("Agent Performance"),
                                    dcc.Graph(id='agent-performance')
                                ], style={'flex': '1', 'padding': '10px'})
                            ], style={'display': 'flex'}),

                            # Row 2: Token and cost consumption by agent
                            html.Div([
                                html.Div([
                                    html.H3("Total Tokens by Agent"),
                                    dcc.Graph(id='agent-tokens')
                                ], style={'flex': '1', 'padding': '10px'}),
                                html.Div([
                                    html.H3("Total Cost by Agent"),
                                    dcc.Graph(id='agent-cost')
                                ], style={'flex': '1', 'padding': '10px'})
                            ], style={'display': 'flex'})
                        ], style={'padding': '10px'}),

                        # Row 3
                        html.Div([
                            html.Div([
                                html.H3("Agent Action Insuccess Rate"),
                                dcc.Graph(id='agent-action-succes')
                            ], style={'flex': '1', 'padding': '10px'}),
                            html.Div([
                                html.H3("Agent Action Latency"),
                                dcc.Graph(id='agent-action-latency')
                            ], style={'flex': '1', 'padding': '10px'}),

                        ], style={'display': 'flex'}),

                        # Row 4
                        html.Div([
                            html.Div([
                                html.H3("Tokens Used per Action"),
                                dcc.Graph(id='agent-action-tokens')
                            ], style={'flex': '1', 'padding': '10px'}),
                            html.Div([
                                html.H3("Total Cost by Action"),
                                dcc.Graph(id='agent-action-cost')
                            ], style={'flex': '1', 'padding': '10px'})
                        ], style={'display': 'flex'})

                    ], style={"backgroundColor": "#1E1E2F", "color": "white"}, selected_style={"backgroundColor": "#373888", "color": "white"}),

                    # Operations Tab
                    dcc.Tab(label='⚙️ Operations Data', value='operations-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
                            html.Div([
                                dash_table.DataTable(
                                        id='operations-table',
                                        row_selectable="multi",  # Allow multiple rows to be selected
                                        selected_rows=[],        # Initial selection (empty)
                                        selected_row_ids=[],
                                        page_current=0,
                                        page_size=PAGE_SIZE,
                                        style_table={'overflowX': 'auto'},
                                        style_cell={
                                            'textAlign': 'left',
                                            'padding': '10px',
                                            'minWidth': '100px', 'maxWidth': '300px',
                                            'whiteSpace': 'nowrap',
                                            'overflow': 'hidden',
                                            'textOverflow': 'ellipsis',
                                            'backgroundColor': '#333',
                                            'color': 'white',
                                            'height': '24px',
                                            'cursor': 'pointer'
                                        },
                                        style_header={
                                            'backgroundColor': '#444',
                                            'fontWeight': 'bold',
                                            'color': 'white'
                                        },
                                        style_data_conditional=[
                                            {'if': {'row_index': 'odd'}, 'backgroundColor': '#2a2a2a'},
                                            {'if': {'filter_query': '{success} = false', 'column_id': 'success'},
                                            'backgroundColor': '#5c1e1e', 'color': 'white'}
                                        ],
                                        filter_action="native",
                                        sort_action="native",
                                        sort_mode="multi",
                                    )
                            ], className="table-container"),
                            html.Pre(),
                            html.Button("Clear Selection", id="clear-button", n_clicks=0, className="clear-button"),
                            html.Pre(),
                            html.Pre(id='tbl_out', style={"whiteSpace": "pre-wrap", "fontFamily": "monospace", "marginLeft": "20px"})
                        ], className="tab-content")
                    ], style={"backgroundColor": "#1E1E2F", "color": "white"}, selected_style={"backgroundColor": "#373888", "color": "white"})
                ]),
            ], className="tabs-container"),
        ], className="dashboard-wrapper")
        
    def _register_callbacks(self):
        """Register dashboard callbacks."""

        @self.app.callback(
            Output("last-updated-text", "children"),
            Output("loading-output", "children"),
            Input("refresh-button", "n_clicks"),
            Input("interval-component", "n_intervals"),
            Input("last-hour-option", "n_clicks"),
            Input("last-6h-option", "n_clicks"),
            Input("last-24h-option", "n_clicks"),
            Input("last-7d-option", "n_clicks"),
            State('session-state', 'data'),
            prevent_initial_call=True
        )
        def update_time(n_clicks, n_intervals, last_hour, last_6h, last_24h, last_7d, session_state):
            ctx = dash.callback_context
            if not ctx.triggered:
                return f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""
            
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            # Determine time range based on trigger
            days = None
            if trigger_id == "last-hour-option":
                days = 1/24  # 1 hour
            elif trigger_id == "last-6h-option":
                days = 6/24  # 6 hours
            elif trigger_id == "last-24h-option":
                days = 1  # 1 day
            elif trigger_id == "last-7d-option":
                days = 7  # 7 days
            
            # Show loading indicator
            loading_text = "Loading data..."
            
            # Fetch data with the specified time range
            last_updated = self.fetch_df(days=days)
            
            # Hide loading indicator
            return f"Last updated: {last_updated}", ""
        
        @self.app.callback(
            Output('session-state', 'data'),
            Input('operations-table', 'active_cell'),
            Input('operations-table', 'page_current'),
            Input("clear-button", "n_clicks"),
            Input("refresh-button", "n_clicks"),
            Input("interval-component", "n_intervals"),
            State('session-state', 'data'),
            State('operations-table', 'selected_rows'),
            State('operations-table', 'selected_row_ids'),
            State('operations-table', 'data'),
            prevent_initial_call=True
        )
        def update_session_state(active_cell, page_current, n_clicks,
                                 refresh_clicks, last_update, session_state,
                                 selected_rows, selected_row_ids, table_data):
            ctx = dash.callback_context
            if not ctx.triggered:
                return session_state
            
            trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
            
            # Initialize session state if it doesn't exist
            if session_state is None:
                session_state = {'selected_rows': [], 'selected_row_ids': [], 'active_cell': None}
            
            # Handle clear button
            if trigger_id == "clear-button":
                session_state['selected_rows'] = []
                session_state['selected_row_ids'] = []
                session_state['active_cell'] = None
                return session_state
            
            # Handle refresh - preserve current selection
            if trigger_id in ["refresh-button", "interval-component"]:
                # We don't need to do anything here, just return the current state
                return session_state
            
            # Handle table selection
            if trigger_id == "operations-table" and active_cell is not None and page_current is not None:
                # Get the row index in the full dataset
                row_index = active_cell.get('row') + page_current * PAGE_SIZE
                
                # Get the operation_id for this row
                if row_index < len(table_data):
                    row_id = table_data[row_index].get('operation_id')
                    
                    # Check if this row is already selected
                    if row_id in session_state['selected_row_ids']:
                        # Deselect it
                        idx = session_state['selected_row_ids'].index(row_id)
                        session_state['selected_row_ids'].pop(idx)
                        session_state['selected_rows'].pop(idx)
                    else:
                        # Select it
                        session_state['selected_rows'].append(row_index)
                        session_state['selected_row_ids'].append(row_id)
                    
                    # Update active cell
                    session_state['active_cell'] = active_cell
            
            return session_state
        
        @self.app.callback(
            Output('operations-table', 'selected_rows'),
            Output('operations-table', 'selected_row_ids'),
            Output('tbl_out', 'children'),
            Output('operations-table', 'active_cell'),
            Input('session-state', 'data'),
            State('operations-table', 'data'),
            State('operations-table', 'page_current'),
            prevent_initial_call=True
        )
        def update_table_selection(session_state, table_data, page_current):
            if session_state is None or not table_data:
                return [], [], "No data available", None
            
            selected_rows = session_state.get('selected_rows', [])
            selected_row_ids = session_state.get('selected_row_ids', [])
            active_cell = session_state.get('active_cell', None)
            
            # Generate output for selected rows
            if selected_row_ids:
                contents = []
                for row_id in selected_row_ids[::-1]:
                    # Find the row in the table data
                    row_data = next((row for row in table_data if row.get('operation_id') == row_id), None)
                    if row_data:
                        contents.append(
                            MESSAGES_TEMPLATE.format(
                                SEP=SEP,
                                row=row_data.get('index', ''),
                                timestamp=row_data.get('timestamp', ''),
                                agent=row_data.get('agent_id', ''),
                                action=f" @ {row_data.get('action_id', '')}" if row_data.get('action_id') else "",
                                history=row_data.get('history_messages', ''),
                                system=row_data.get('system_prompt', ''),
                                assistant=row_data.get('assistant_message', ''),
                                prompt=row_data.get('user_prompt', ''),
                                response=row_data.get('response', '')
                            )
                        )

                contents = f"\n\n{MULTISEP}".join(contents)
                return selected_rows, selected_row_ids, contents, active_cell
            
            return selected_rows, selected_row_ids, "Click a cell to select its row.", active_cell
        
        @self.app.callback(
            [Output('provider-dropdown', 'options'),
            Output('model-dropdown', 'options'),
            Output('agent-dropdown', 'options'),
            Output('action-dropdown', 'options'),
            Output('session-dropdown', 'options'),
            Output('workspace-dropdown', 'options'),
            Output('date-picker-range', 'start_date'),
            Output('date-picker-range', 'end_date')],
            [Input("refresh-button", "n_clicks"),
            Input("interval-component", "n_intervals"),
            Input('date-picker-range', 'start_date'),
            Input('date-picker-range', 'end_date'),
            Input('session-dropdown', 'value'),
            Input('workspace-dropdown', 'value'),
            Input('provider-dropdown', 'value'),
            Input('model-dropdown', 'value'),
            Input('agent-dropdown', 'value'),
            Input('action-dropdown', 'value')]
        )
        def update_dropdowns(n_clicks, last_update, start_date, end_date, session_id, workspace, providers, models, agents, actions):
            """Update dropdown options based on available data, filtering by workspace if provided."""
            # In lazy mode, handle session selection
            if self.lazy and session_id:
                session_ids_to_load = session_id if isinstance(session_id, list) else [session_id]
                # Get currently loaded sessions
                loaded_sessions = set(self.df["session_id"].unique().to_list()) if not self.df.is_empty() else set()
                # Find sessions that need to be loaded
                sessions_to_fetch = [s for s in session_ids_to_load if s not in loaded_sessions]

                if sessions_to_fetch:
                    # Load new sessions
                    print(f"[LAZY MODE] Loading sessions: {sessions_to_fetch}")
                    print(f"[LAZY MODE] Currently loaded: {loaded_sessions}")
                    print(f"[LAZY MODE] DataFrame before load - rows: {len(self.df)}")
                    self.fetch_df(session_ids=sessions_to_fetch)
                    print(f"[LAZY MODE] DataFrame after load - rows: {len(self.df)}")
                    if not self.df.is_empty():
                        print(f"[LAZY MODE] Loaded sessions now: {self.df['session_id'].unique().to_list()}")

            # In lazy mode, always show all available sessions in dropdown
            if self.lazy:
                session_options = [{'label': s, 'value': s} for s in self.available_sessions]

                if self.df.is_empty():
                    # No data loaded yet, only show session options with default dates
                    default_start = (datetime.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).date()
                    default_end = datetime.now().date()
                    return [], [], [], [], session_options, [], default_start, default_end

                # Data is loaded, compute dates from dataframe and other options from the loaded data
                min_date = self.df["date"].min().date() if "date" in self.df.columns else start_date
                max_date = self.df["date"].max().date() if "date" in self.df.columns else end_date

                workspaces = self.df["workspace"].unique().to_list()
                workspace_options = [{'label': w, 'value': w} for w in workspaces]
                df_filtered = self.filter_data(start_date, end_date, session_id, workspace, providers, models, agents, actions)

                # Compute other dropdown options from the filtered dataframe
                providers = df_filtered["provider"].unique().to_list()
                models = df_filtered["model"].unique().to_list()
                agents = [a for a in df_filtered["agent_id"].unique().to_list() if a]
                actions = [a for a in df_filtered["action_id"].unique().to_list() if a]

                provider_options = [{'label': p, 'value': p} for p in providers]
                model_options = [{'label': m, 'value': m} for m in models]
                agent_options = [{'label': a, 'value': a} for a in agents]
                actions_options = [{'label': a, 'value': a} for a in actions]

                return provider_options, model_options, agent_options, actions_options, session_options, workspace_options, min_date, max_date

            # Normal mode (not lazy) - keep existing dates
            if self.df.is_empty():
                default_start = (datetime.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).date()
                default_end = datetime.now().date()
                return [], [], [], [], [], [], default_start, default_end

            # Compute workspace options from the full dataframe
            workspaces = self.df["workspace"].unique().to_list()
            workspace_options = [{'label': w, 'value': w} for w in workspaces]
            df_filtered = self.filter_data(start_date, end_date, session_id, workspace, providers, models, agents, actions)
            # Compute other dropdown options from the filtered dataframe
            providers = df_filtered["provider"].unique().to_list()
            models = df_filtered["model"].unique().to_list()
            sessions = df_filtered["session_id"].unique().to_list()
            agents = [a for a in df_filtered["agent_id"].unique().to_list() if a]  # Filter empty agent IDs
            actions = [a for a in df_filtered["action_id"].unique().to_list() if a]  # Filter empty agent IDs

            provider_options = [{'label': p, 'value': p} for p in providers]
            model_options = [{'label': m, 'value': m} for m in models]
            session_options = [{'label': s, 'value': s} for s in sessions]
            agent_options = [{'label': a, 'value': a} for a in agents]
            actions_options = [{'label': a, 'value': a} for a in actions]

            return provider_options, model_options, agent_options, actions_options, session_options, workspace_options, start_date, end_date

        @self.app.callback(
            [
                # Overview Tab
                Output('overview-metrics', 'children'),
                Output('requests-time-series', 'figure'),
                Output('insuccess-rate-chart', 'figure'),
                Output('provider-model-sunburst', 'figure'),
                Output('model-distribution', 'figure'),
                
                # Performance Tab
                Output('latency-metrics', 'children'),
                Output('latency-histogram', 'figure'),
                Output('latency-by-provider', 'figure'),
                Output('latency-by-model', 'figure'),
                Output('latency-timeline', 'figure'),
                
                # Token Usage Tab
                Output('token-metrics', 'children'),
                Output('token-efficiency-chart', 'figure'),
                Output('token-by-model', 'figure'),
                Output('token-distribution', 'figure'),
                Output('cost-analysis', 'figure'),
                
                # Cost Analysis Tab
                Output('cost-metrics', 'children'),
                Output('cost-breakdown-sunburst', 'figure'),
                Output('cost-per-token', 'figure'),
                
                # Agent Analysis Tab
                Output('agent-metrics', 'children'),
                Output('agent-distribution', 'figure'),
                Output('agent-performance', 'figure'),
                # New outputs for tokens and cost by agent:
                Output('agent-tokens', 'figure'),
                Output('agent-cost', 'figure'),
                # Actions
                Output('agent-action-succes', 'figure'),
                Output('agent-action-latency', 'figure'),
                Output('agent-action-tokens', 'figure'),
                Output('agent-action-cost', 'figure'),
                
                # Additional Observability Plot
                Output('operation-type-distribution', 'figure'),
                
                # Operations Tab
                Output('operations-table', 'data'),
                Output('operations-table', 'columns')
            ],
            # [Input('apply-filters', 'n_clicks'), Input('refresh-data', 'n_clicks')],
            [Input("refresh-button", "n_clicks"),
            Input("interval-component", "n_intervals"),
            Input('date-picker-range', 'start_date'),
            Input('date-picker-range', 'end_date'),
            Input('session-dropdown', 'value'),
            Input('workspace-dropdown', 'value'),
            Input('provider-dropdown', 'value'),
            Input('model-dropdown', 'value'),
            Input('agent-dropdown', 'value'),
            Input('action-dropdown', 'value')]
        )
        def update_dashboard(n_clicks, last_update, start_date, end_date, session_id, workspace, providers, models, agents, actions):
            """Update dashboard visualizations based on filters."""
            # In lazy mode, ensure data is loaded when sessions are selected
            if self.lazy and session_id and self.df.is_empty():
                session_ids_to_load = session_id if isinstance(session_id, list) else [session_id]
                self.fetch_df(session_ids=session_ids_to_load)

            filtered_df = self.filter_data(start_date, end_date, session_id, workspace, providers, models, agents, actions)
            
            if filtered_df.is_empty():
                # Return empty visualizations if no data
                empty_outputs = self._create_empty_dashboard()
                return empty_outputs
            
            # Overview Tab
            overview_metrics = self._create_overview_metrics(filtered_df)
            
            # Time series chart for requests
            requests_by_date = filtered_df.group_by("day").agg(pl.len().alias("count"))
            requests_ts_fig = px.line(
                requests_by_date.sort("day"), 
                x='day', 
                y='count', 
                template=TEMPLATE,
                title='Daily Request Volume'
            )
            requests_ts_fig.update_traces(mode='lines+markers')
            
            # Insuccess rate by provider
            insuccess_by_provider = filtered_df.group_by("provider").agg(
                (100 - pl.col("success").mean().mul(100).round(1)).alias("insuccess_rate"),
                pl.len().alias("count")
            )
            insuccess_rate_fig = px.bar(
                insuccess_by_provider, 
                x='provider', 
                y='insuccess_rate',
                color='insuccess_rate',
                color_continuous_scale='RdYlGn',
                text='insuccess_rate',
                template=TEMPLATE
            )
            insuccess_rate_fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            insuccess_rate_fig.update_layout(yaxis_title="Insuccess Rate (%)")
            # Provider-Model Sunburst chart (fixed with hierarchical path)
            provider_model = filtered_df.group_by(["provider", "model"]).agg(
                pl.len().alias("count")
            )
            sunburst_fig = px.sunburst(
                provider_model, 
                path=['provider', 'model'],
                values='count',
                template=TEMPLATE,
                title="Provider-Model Distribution"
            )
            
            # Model distribution pie chart
            model_dist = filtered_df.group_by("model").agg(pl.len().alias("count"))
            model_fig = px.pie(
                model_dist, 
                names='model', 
                values='count',
                hole=0.4,
                template=TEMPLATE,
                title="Model Distribution"
            )
            
            # Performance Tab
            # Performance Metrics
            performance_metrics = self._create_performance_metrics(filtered_df)

            # Latency histogram
            latency_fig = px.histogram(
                filtered_df, 
                x='latency_ms', 
                nbins=30,
                template=TEMPLATE
            )
            latency_fig.update_layout(xaxis_title="Latency (ms)", yaxis_title="Count")
            
            # Latency by provider
            latency_by_provider = filtered_df.group_by("provider").agg(
                pl.col("latency_ms").mean().alias("avg_latency"),
                pl.col("latency_ms").min().alias("min_latency"),
                pl.col("latency_ms").max().alias("max_latency"),
                pl.col("latency_ms").quantile(0.5).alias("median_latency")
            )
            latency_provider_fig = px.bar(
                latency_by_provider, 
                x='provider', 
                y='avg_latency',
                error_y=latency_by_provider["max_latency"] - latency_by_provider["avg_latency"],
                error_y_minus=latency_by_provider["avg_latency"] - latency_by_provider["min_latency"],
                template=TEMPLATE,
                title="Average Latency by Provider"
            )
            latency_provider_fig.update_layout(yaxis_title="Latency (ms)")
            
            # Latency by model
            latency_by_model = filtered_df.group_by("model").agg(
                pl.col("latency_ms").mean().alias("avg_latency")
            )
            latency_model_fig = px.bar(
                latency_by_model.sort("avg_latency", descending=True), 
                x='model', 
                y='avg_latency',
                template=TEMPLATE,
                title="Average Latency by Model"
            )
            latency_model_fig.update_layout(yaxis_title="Avg Latency (ms)")
            
            # Latency timeline
            latency_timeline_fig = px.scatter(
                filtered_df.sort("timestamp"),
                x='timestamp',
                y='latency_ms',
                color='provider',
                template=TEMPLATE,
                title="Latency Timeline"
            )
            latency_timeline_fig.update_layout(yaxis_title="Latency (ms)")
            
            # Token Usage Tab
            # Token Usage Metrics
            token_usage_metrics = self._create_token_usage_metrics(filtered_df)

            # Token efficiency chart (tokens per ms)
            token_efficiency = filtered_df.filter(
                (pl.col("total_tokens") > 0) & (pl.col("latency_ms") > 0)
            ).with_columns(
                efficiency=pl.col("total_tokens") / pl.col("latency_ms")
            ).group_by("provider").agg(
                pl.col("efficiency").mean().alias("tokens_per_ms")
            )
            token_efficiency_fig = px.bar(
                token_efficiency.sort("tokens_per_ms", descending=True),
                x="provider",
                y="tokens_per_ms",
                color="tokens_per_ms",
                template=TEMPLATE,
                title="Token Efficiency by Provider"
            )
            token_efficiency_fig.update_layout(yaxis_title="Tokens per millisecond")
            
            # Token usage by model
            # Aggregate token usage by model
            token_by_model = filtered_df.filter(
                (pl.col("input_tokens") > 0) | (pl.col("output_tokens") > 0)
            ).group_by("model").agg(
                pl.col("input_tokens").sum().alias("input_tokens"),
                pl.col("output_tokens").sum().alias("output_tokens"),
                pl.col("total_tokens").sum().alias("total_tokens")
            )

            # Create a grouped bar chart for token usage
            token_model_fig = px.bar(
                token_by_model,
                x="model",
                y=["input_tokens", "output_tokens", "total_tokens"],
                template=TEMPLATE,
                title="Token Usage by Model"
            )
            token_model_fig.update_layout(
                yaxis_title="Tokens",
                barmode="group"
            )

            # Input vs Output tokens distribution
            token_dist_data = filtered_df.filter(
                (pl.col("input_tokens") > 0) | (pl.col("output_tokens") > 0)
            ).select(
                pl.col("input_tokens").sum().alias("Input"),
                pl.col("output_tokens").sum().alias("Output")
            )
            token_dist_data = {
                "category": ["Input Tokens", "Output Tokens"],
                "value": [token_dist_data[0,0], token_dist_data[0,1]]
            }
            token_dist_fig = px.pie(
                token_dist_data,
                names='category',
                values='value',
                template=TEMPLATE,
                title="Input vs Output Tokens"
            )
            
            # Cost analysis
            # Cost analysis metrics
            cost_analysis_metrics = self._create_cost_analysis_metrics(filtered_df)

            cost_by_model = filtered_df.filter(
                pl.col("cost") > 0
            ).group_by("model").agg(
                pl.col("cost").sum().alias("total_cost")
            )
            if cost_by_model.height > 0:
                cost_fig = px.bar(
                    cost_by_model.sort("total_cost", descending=True),
                    x='model',
                    y='total_cost',
                    template=TEMPLATE,
                    title="Cost Analysis by Model"
                )
                cost_fig.update_layout(yaxis_title="Total Cost")
            else:
                cost_fig = px.bar(
                    {"model": ["No cost data"], "total_cost": [0]},
                    x='model',
                    y='total_cost',
                    template=TEMPLATE,
                    title="No cost data available"
                )
                cost_fig.update_layout(yaxis_title="Total Cost")
            
            # Cost breakdown sunburst
            cost_breakdown = filtered_df.filter(
                pl.col("cost") > 0
            ).group_by(["provider", "model"]).agg(
                pl.col("cost").sum().alias("total_cost")
            )
            if cost_breakdown.height > 0:
                cost_sunburst_fig = px.sunburst(
                    cost_breakdown,
                    path=['provider', 'model'],
                    values='total_cost',
                    template=TEMPLATE,
                    title="Cost Breakdown by Provider and Model"
                )
            else:
                cost_sunburst_fig = px.sunburst(
                    {"provider": ["No cost data"], "model": ["No cost data"], "total_cost": [0]},
                    path=['provider', 'model'],
                    values='total_cost',
                    template=TEMPLATE,
                    title="No cost data available"
                )
            
            # Average cost per request
            avg_cost_per_request = filtered_df.filter(
                pl.col("cost") > 0  # Ensure valid cost values
            ).group_by("model").agg(
                pl.col("cost").mean().alias("avg_cost_per_request")
            )

            # Create bar chart
            avg_cost_per_request_fig = px.bar(
                avg_cost_per_request, 
                x="model", 
                y="avg_cost_per_request", 
                template=TEMPLATE,
                title="Average Cost per Request by Model"
            )
            
            # Agent Analysis Tab
            # Agent Analysis metrics
            agent_analysis_metrics = self._create_agent_analysis_metrics(filtered_df)

            # Agent distribution (sunburst version)
            agent_data = filtered_df.filter(pl.col("agent_id") != "")
            if agent_data.height > 0:
                # For simple agent distribution without actions
                if "action_id" not in agent_data.columns or all(agent_data["action_id"].is_null()):
                    # Create a dataframe with root level and agent level
                    sunburst_data = {"ids": ["total"], "labels": ["All Agents"], "parents": [""]}
                    
                    agent_dist = agent_data.group_by("agent_id").agg(pl.len().alias("count"))
                    
                    # Add agent IDs as children of the root
                    sunburst_data["ids"].extend(agent_dist["agent_id"].to_list())
                    sunburst_data["labels"].extend(agent_dist["agent_id"].to_list())
                    sunburst_data["parents"].extend(["total"] * len(agent_dist))
                    
                    # Add values for all elements
                    sunburst_data["values"] = [agent_dist["count"].sum()] + agent_dist["count"].to_list()
                    
                    agent_dist_fig = go.Figure(go.Sunburst(
                        ids=sunburst_data["ids"],
                        labels=sunburst_data["labels"],
                        parents=sunburst_data["parents"],
                        values=sunburst_data["values"],
                        branchvalues="total"
                    ))
                    agent_dist_fig.update_layout(
                        template=TEMPLATE,
                        title="Agent Distribution"
                    )
                else:
                    # With actions, create a hierarchical sunburst
                    action_data = agent_data.filter(pl.col("action_id").is_not_null())
                    
                    # First prepare the data structure for the sunburst chart
                    sunburst_data = {"ids": ["total"], "labels": ["All Agents"], "parents": [""]}
                    
                    # Add agent level data
                    agent_dist = agent_data.group_by("agent_id").agg(pl.len().alias("count"))
                    sunburst_data["ids"].extend(agent_dist["agent_id"].to_list())
                    sunburst_data["labels"].extend(agent_dist["agent_id"].to_list())
                    sunburst_data["parents"].extend(["total"] * len(agent_dist))
                    
                    # Add action level data if available
                    if action_data.height > 0:
                        action_dist = action_data.group_by(["agent_id", "action_id"]).agg(pl.len().alias("count"))
                        
                        # Create combined IDs for action nodes
                        action_ids = [f"{row['agent_id']}_{row['action_id']}" for row in action_dist.to_dicts()]
                        sunburst_data["ids"].extend(action_ids)
                        sunburst_data["labels"].extend(action_dist["action_id"].to_list())
                        sunburst_data["parents"].extend(action_dist["agent_id"].to_list())
                        
                        # Values for each level
                        agent_values = agent_dist["count"].to_list()
                        action_values = action_dist["count"].to_list()
                        sunburst_data["values"] = [sum(agent_values)] + agent_values + action_values
                    else:
                        # Values for agent level only
                        sunburst_data["values"] = [agent_dist["count"].sum()] + agent_dist["count"].to_list()
                    
                    agent_dist_fig = go.Figure(go.Sunburst(
                        ids=sunburst_data["ids"],
                        labels=sunburst_data["labels"],
                        parents=sunburst_data["parents"],
                        values=sunburst_data["values"],
                        branchvalues="total"
                    ))
                    agent_dist_fig.update_layout(
                        template=TEMPLATE,
                        title="Agent & Action Distribution"
                    )
            else:
                agent_dist_fig = go.Figure(go.Sunburst(
                    ids=["no_data"],
                    labels=["No agent data"],
                    parents=[""],
                    values=[1]
                ))
                agent_dist_fig.update_layout(
                    template=TEMPLATE,
                    title="No agent data available"
                )
            
            # Agent performance (insuccess rate)
            if agent_data.height > 0:
                agent_perf = agent_data.group_by("agent_id").agg(
                    (100 - pl.col("success").mean().mul(100).round(1)).alias("insuccess_rate"),
                    pl.col("latency_ms").mean().alias("avg_latency"),
                    pl.len().alias("count")
                )
                agent_perf_fig = px.scatter(
                    agent_perf,
                    x='insuccess_rate',
                    y='avg_latency',
                    size='count',
                    hover_name='agent_id',
                    color='agent_id',
                    template=TEMPLATE,
                    title="Agent Performance"
                )
                agent_perf_fig.update_layout(
                    xaxis_title="Insuccess Rate (%)",
                    yaxis_title="Avg Latency (ms)"
                )
            else:
                agent_perf_fig = px.scatter(
                    {"insuccess_rate": [0], "avg_latency": [0], "count": [0], "agent_id": ["No agent data"]},
                    x='insuccess_rate',
                    y='avg_latency',
                    size='count',
                    hover_name='agent_id',
                    template=TEMPLATE,
                    title="No agent data available"
                )
                
            # Aggregate tokens by agent and action
            if agent_data.height > 0 and "action_id" in agent_data.columns:
                # Filter for non-null actions
                action_data = agent_data.filter(pl.col("action_id").is_not_null())

                if action_data.height > 0:
                    # Create a dataframe with summed tokens for each agent-action pair
                    tokens_by_agent_action = action_data.group_by(["agent_id", "action_id"]).agg(
                        pl.col("total_tokens").sum().alias("total_tokens"),
                        pl.col("input_tokens").sum().alias("input_tokens"),
                        pl.col("output_tokens").sum().alias("output_tokens")
                    )

                    # Convert to long format for stacking input/output tokens
                    input_tokens = tokens_by_agent_action.select(
                        pl.col("agent_id"),
                        pl.col("action_id"),
                        pl.lit("Input").alias("token_type"),
                        pl.col("input_tokens").alias("tokens")
                    )

                    output_tokens = tokens_by_agent_action.select(
                        pl.col("agent_id"),
                        pl.col("action_id"),
                        pl.lit("Output").alias("token_type"),
                        pl.col("output_tokens").alias("tokens")
                    )

                    total_tokens = tokens_by_agent_action.select(
                        pl.col("agent_id"),
                        pl.col("action_id"),
                        pl.lit("Total").alias("token_type"),
                        pl.col("total_tokens").alias("tokens")
                    )

                    # Merge all token types
                    stacked_tokens_df = pl.concat([input_tokens, output_tokens, total_tokens])

                    # Create a stacked bar chart using go.Bar
                    agent_ids = stacked_tokens_df["agent_id"].unique()
                    token_types = ["Total", "Input", "Output"]
                    traces = []

                    for token_type in token_types:
                        _filtered_df = stacked_tokens_df.filter(pl.col("token_type") == token_type)
                        traces.append(
                            go.Bar(
                                name=token_type,
                                x=_filtered_df["agent_id"],
                                y=_filtered_df["tokens"],
                                hovertemplate="<b>Agent ID:</b> %{x}<br>"
                                              "<b>Tokens:</b> %{y}<br>"
                                              "<b>Action ID:</b> %{customdata}",
                                customdata=_filtered_df["action_id"],
                                text=_filtered_df["action_id"],
                                textangle=0
                            )
                        )

                    combined_tokens_fig = go.Figure(traces, 
                        layout=go.Layout( 
                            template=TEMPLATE
                        )
                    )
                    combined_tokens_fig.update_layout(
                        title="Token Usage by Agent, Action, and Token Type",
                        yaxis_title="Tokens",
                        legend_title="Token Type"
                    )

                else:
                    # Fallback when there is no action data available
                    combined_tokens_fig = go.Figure()
                    combined_tokens_fig.add_trace(go.Bar(
                        x=["No action data"],
                        y=[0],
                        name="None"
                    ))
                    combined_tokens_fig.update_layout(
                        title="No action token data available"
                    )
            else:
                # Fallback when agent data or action_id column is not available
                combined_tokens_fig = go.Figure()
                combined_tokens_fig.add_trace(go.Bar(
                    x=["No agent data"],
                    y=[0],
                    name="None"
                ))
                combined_tokens_fig.update_layout(
                    title="No token data available"
                )
                                    
            # New: Cost incurred by agent
            if agent_data.height > 0:
                cost_by_agent = agent_data.filter(pl.col("cost") > 0).group_by(["agent_id", "action_id"]).agg(
                    pl.col("cost").sum().alias("total_cost")
                )
                agent_cost_fig = px.bar(
                    cost_by_agent.sort("total_cost", descending=True),
                    x="agent_id",
                    y="total_cost",
                    template=TEMPLATE,
                    color="action_id",
                    text="action_id",
                    barmode="stack",
                    title="Total Cost by Agent"
                )
                agent_cost_fig.update_layout(yaxis_title="Total Cost ($)")
            else:
                agent_cost_fig = px.bar(
                    {"agent_id": ["No agent data"], "total_cost": [0]},
                    x="agent_id",
                    y="total_cost",
                    template=TEMPLATE,
                    title="No cost data available"
                )

            # Action distribution by Agent
            if agent_data.height > 0 and "action_id" in agent_data.columns:
                action_data = agent_data.filter(pl.col("action_id").is_not_null())
                if action_data.height > 0:
                    # Actions by agent distribution
                    actions_by_agent = action_data.group_by(["agent_id", "action_id"]).agg(
                        pl.len().alias("count")
                    )
                    agent_action_dist_fig = px.bar(
                        actions_by_agent,
                        x='agent_id',
                        y='count',
                        color='action_id',
                        barmode='stack',
                        template=TEMPLATE,
                        title="Actions Distribution by Agent"
                    )
                    agent_action_dist_fig.update_layout(
                        xaxis_title="Agent ID",
                        yaxis_title="Number of Executions"
                    )
                    
                    # Action insuccess rate by agent
                    action_insuccess_by_agent = action_data.group_by(["agent_id", "action_id"]).agg(
                        (100-pl.col("success").mean().mul(100).round(1)).alias("insuccess_rate"),
                        pl.len().alias("count")
                    )
                    action_insuccess_fig = px.scatter(
                        action_insuccess_by_agent,
                        x='agent_id',
                        y='insuccess_rate',
                        size='count',
                        color='action_id',
                        hover_name='action_id',
                        template=TEMPLATE,
                        title="Action Insuccess Rate by Agent"
                    )
                    action_insuccess_fig.update_layout(
                        xaxis_title="Agent ID",
                        yaxis_title="Insuccess Rate (%)"
                    )
                    
                    # Action latency by agent
                    action_latency = action_data.group_by(["agent_id", "action_id"]).agg(
                        pl.col("latency_ms").mean().alias("avg_latency"),
                        pl.len().alias("count")
                    )
                    action_latency_fig = px.scatter(
                        action_latency,
                        x='agent_id',
                        y='avg_latency',
                        size='count',
                        color='action_id',
                        hover_name='action_id',
                        template=TEMPLATE,
                        title="Action Latency by Agent"
                    )
                    action_latency_fig.update_layout(
                        xaxis_title="Agent ID",
                        yaxis_title="Average Latency (ms)"
                    )
                    
                    # Tokens by action
                    tokens_by_action = action_data.group_by(["action_id"]).agg(
                        pl.col("total_tokens").sum().alias("total_tokens"),
                        pl.col("input_tokens").sum().alias("input_tokens"),
                        pl.col("output_tokens").sum().alias("output_tokens")
                    )
                    action_tokens_fig = px.bar(
                        tokens_by_action.sort("total_tokens", descending=True),
                        x="action_id",
                        y=["total_tokens", "input_tokens", "output_tokens"],
                        template=TEMPLATE,
                        title="Tokens by Action"
                    )
                    action_tokens_fig.update_layout(
                        xaxis_title="action_id",
                        yaxis_title="Tokens",
                        barmode="group"
                    )
                    
                    # Cost by action
                    cost_by_action = action_data.filter(pl.col("cost") > 0).group_by("action_id").agg(
                        pl.col("cost").sum().alias("total_cost")
                    )
                    action_cost_fig = px.bar(
                        cost_by_action.sort("total_cost", descending=True),
                        x="action_id",
                        y="total_cost",
                        template=TEMPLATE,
                        title="Total Cost by Action"
                    )
                    action_cost_fig.update_layout(
                        xaxis_title="action_id",
                        yaxis_title="Total Cost ($)"
                    )
                    
                    # Action ratio per agent (pie charts, one per agent)
                    agent_ids = agent_data["agent_id"].unique()
                    action_ratio_figs = []
                    for agent_id in agent_ids:
                        agent_actions = action_data.filter(pl.col("agent_id") == agent_id)
                        if agent_actions.height > 0:
                            agent_action_counts = agent_actions.group_by("action_id").agg(
                                pl.len().alias("count")
                            )
                            fig = px.pie(
                                agent_action_counts,
                                names="action_id",
                                values="count",
                                template=TEMPLATE,
                                title=f"Action Distribution for {agent_id}"
                            )
                            action_ratio_figs.append(fig)
                    
                else:
                    # Default empty charts
                    agent_action_dist_fig = px.bar(
                        {"agent_id": ["No action data"], "count": [0], "action_id": ["None"]},
                        x="agent_id",
                        y="count",
                        color="action_id",
                        template=TEMPLATE,
                        title="No action data available"
                    )
                    action_insuccess_fig = px.scatter(
                        {"agent_id": ["No action data"], "insuccess_rate": [0], "count": [0], "action_id": ["None"]},
                        x="agent_id",
                        y="insuccess_rate",
                        template=TEMPLATE,
                        title="No action data available"
                    )
                    action_latency_fig = px.scatter(
                        {"agent_id": ["No action data"], "avg_latency": [0], "count": [0], "action_id": ["None"]},
                        x="agent_id",
                        y="avg_latency",
                        template=TEMPLATE,
                        title="No action data available"
                    )
                    action_tokens_fig = px.bar(
                        {"action_id": ["No action data"], "total_tokens": [0]},
                        x="action_id",
                        y="total_tokens",
                        template=TEMPLATE,
                        title="No token data available"
                    )
                    action_cost_fig = px.bar(
                        {"action_id": ["No action data"], "total_cost": [0]},
                        x="action_id",
                        y="total_cost",
                        template=TEMPLATE,
                        title="No cost data available"
                    )
            else:
                # Default empty charts if no action data
                agent_action_dist_fig = px.bar(
                    {"agent_id": ["No action data"], "count": [0], "action_id": ["None"]},
                    x="agent_id",
                    y="count",
                    color="action_id",
                    template=TEMPLATE,
                    title="No action data available"
                )
                action_insuccess_fig = px.scatter(
                    {"agent_id": ["No action data"], "insuccess_rate": [0], "count": [0], "action_id": ["None"]},
                    x="agent_id",
                    y="insuccess_rate",
                    template=TEMPLATE,
                    title="No action data available"
                )
                action_latency_fig = px.scatter(
                    {"agent_id": ["No action data"], "avg_latency": [0], "count": [0], "action_id": ["None"]},
                    x="agent_id",
                    y="avg_latency",
                    template=TEMPLATE,
                    title="No action data available"
                )
                action_tokens_fig = px.bar(
                    {"action_id": ["No action data"], "total_tokens": [0]},
                    x="action_id",
                    y="total_tokens",
                    template=TEMPLATE,
                    title="No token data available"
                )
                action_cost_fig = px.bar(
                    {"action_id": ["No action data"], "total_cost": [0]},
                    x="action_id",
                    y="total_cost",
                    template=TEMPLATE,
                    title="No cost data available"
                )
            
            # Additional Observability Plot: Operation Type Distribution
            op_type_data = filtered_df.group_by("operation_type").agg(pl.len().alias("count"))
            op_type_fig = px.pie(
                op_type_data,
                names='operation_type',
                values='count',
                template=TEMPLATE,
                title="Operation Type Distribution"
            )
            
            # Operations Data Tab
            display_columns = [col for col in filtered_df.columns if col not in ["date", "day", "hour", "minute"]]
            table_data = filtered_df.select(display_columns).to_dicts()
            
            # Add index to table data for easier selection handling
            for i, row in enumerate(table_data):
                row['index'] = i
            
            table_columns = [{"name": i, "id": i} for i in display_columns]
            
            return (
                # Overview Tab
                overview_metrics, requests_ts_fig, insuccess_rate_fig, sunburst_fig, model_fig,
                
                # Performance Tab
                performance_metrics , latency_fig, latency_provider_fig, latency_model_fig, latency_timeline_fig,
                
                # Token Usage Tab
                token_usage_metrics, token_efficiency_fig, token_model_fig, token_dist_fig, cost_fig,
                
                # Cost Analysis Tab
                cost_analysis_metrics, cost_sunburst_fig, avg_cost_per_request_fig,
                
                # Agent Analysis Tab
                agent_analysis_metrics, agent_dist_fig, agent_perf_fig,
                combined_tokens_fig, agent_cost_fig, 
                action_insuccess_fig, action_latency_fig, action_tokens_fig, action_cost_fig,
                
                # Additional Observability Plot
                op_type_fig,
                
                # Operations Data Tab
                table_data, table_columns
            )
    
    def filter_data(self, start_date, end_date, session_id, workspace, provider, model, agent_id, action_id):
        """Filter dataframe based on selected filters."""
        filtered_df = self.df.clone()
        if filtered_df.is_empty():
            return filtered_df
        start_date = datetime.fromisoformat(start_date)
        end_date = datetime.fromisoformat(end_date) + timedelta(days=1)
        args = []
        names = ["session_id", "workspace", "provider", "model","agent_id", "action_id"]
        for i, _filter in enumerate([session_id, workspace, provider, model, agent_id, action_id]):
            if not _filter:
                continue
            elif isinstance(_filter, list):
                args.append(pl.col(names[i]).is_in(_filter))
            else:
                args.append(pl.col(names[i]).eq(_filter))
        
        if start_date and end_date:
            args.append(pl.col("date").is_between(start_date, end_date))
        
        filtered_df = filtered_df.filter(*args)
        return filtered_df
        
    def _create_overview_metrics(self, df):
        """Create dynamic overview metrics from dataframe."""
        total_requests = len(df)
        insuccessful_count = len([_ for _ in df["success"] if not(_)])
        insuccess_rate = insuccessful_count / total_requests * 100 if total_requests > 0 else 0
        avg_latency = df["latency_ms"].mean() if total_requests > 0 else 0

        unique_providers = len(df["provider"].unique())
        unique_models = len(df["model"].unique())
        unique_agents = len([a for a in df["agent_id"].unique() if a])  # Filter empty values

        total_tokens = df["total_tokens"].sum() if 'total_tokens' in df.columns else 0
        total_cost = df["cost"].sum() if 'cost' in df.columns else 0

        card_style = {
            "backgroundColor": "#1E1E2F",
            "padding": "20px",
            "borderRadius": "10px",
            "margin": "10px",
            "flex": "1",
            "minWidth": "250px",
            "boxShadow": "0 4px 6px rgba(0,0,0,0.1)",
            "textAlign": "center",
            "transition": "all 0.3s ease",
            "transform": "translateY(0)"
        }

        return html.Div([
            # First row: Total Requests, Insuccess Rate, and Avg. Latency
            html.Div([
                html.Div([
                    html.H4("📊 Total Requests", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{total_requests:,}", style={"color": "#007bff"}),
                    html.P("Requests processed", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("❌ Insuccess Rate", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{insuccess_rate:.1f}%", style={"color": "#28a745" if not insuccess_rate else "#ffc107"}),
                    html.P(f"{total_requests - insuccessful_count} of {total_requests} succeeded", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("⏱️ Avg. Latency", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{avg_latency:.2f} ms", style={"color": "#17a2b8"}),
                    html.P("Average response time", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style)
            ], style={"display": "flex", "flexWrap": "wrap", "justifyContent": "space-around"}),

            # Second row: Providers, Models, and Agents
            html.Div([
                html.Div([
                    html.H4("🏢 Providers", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{unique_providers}", style={"color": "#6f42c1"}),
                    html.P("Unique providers", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("🤖 Models", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{unique_models}", style={"color": "#fd7e14"}),
                    html.P("Different AI models", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("👤 Agents", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{unique_agents}", style={"color": "#dc3545"}),
                    html.P("Active agents", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style)
            ], style={"display": "flex", "flexWrap": "wrap", "justifyContent": "space-around"}),

            # Third row: Total Tokens and Total Cost
            html.Div([
                html.Div([
                    html.H4("💬 Total Tokens", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{int(total_tokens):,}", style={"color": "#20c997"}),
                    html.P("Tokens processed", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("💰 Total Cost", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"${total_cost:.4f}", style={"color": "#ffc107"}),
                    html.P("Total expenditure", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style)
            ], style={"display": "flex", "flexWrap": "wrap", "justifyContent": "space-around"})
        ], style={"display": "flex", "flexDirection": "column"})

    def _create_performance_metrics(self, df):
        """Create dynamic performance metrics from dataframe."""
        total_requests = len(df)
        avg_latency = df["latency_ms"].mean() if total_requests > 0 else 0
        max_latency = df["latency_ms"].max() if total_requests > 0 else 0
        min_latency = df["latency_ms"].min() if total_requests > 0 else 0
        failed_requests = total_requests - len([_ for _ in df["success"] if _])

        card_style = {
            "backgroundColor": "#1E1E2F",
            "padding": "20px",
            "borderRadius": "10px",
            "margin": "10px",
            "flex": "1",
            "minWidth": "250px",
            "boxShadow": "0 4px 6px rgba(0,0,0,0.1)",
            "textAlign": "center",
            "transition": "all 0.3s ease",
            "transform": "translateY(0)"
        }

        return html.Div([
            # First row: Average Latency and Maximum Latency
            html.Div([
                html.Div([
                    html.H4("⏱️ Avg. Latency", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{avg_latency:.2f} ms", style={"color": "#17a2b8"}),
                    html.P("Average response time", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("🚀 Max Latency", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{max_latency:.2f} ms", style={"color": "#dc3545"}),
                    html.P("Slowest response time", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style)
            ], style={"display": "flex", "flexWrap": "wrap", "justifyContent": "space-around"}),

            # Second row: Minimum Latency and Failed Requests
            html.Div([
                html.Div([
                    html.H4("🐢 Min Latency", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{min_latency:.2f} ms", style={"color": "#28a745"}),
                    html.P("Fastest response time", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("❌ Failed Requests", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{failed_requests}", style={"color": "#28a745" if not failed_requests else "#ffc107"}),
                    html.P("Requests that did not succeed", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style)
            ], style={"display": "flex", "flexWrap": "wrap", "justifyContent": "space-around"})
        ], style={"display": "flex", "flexDirection": "column"})

    def _create_token_usage_metrics(self, df):
        """Create dynamic token usage metrics from dataframe."""
        total_requests = len(df)
        total_tokens = df["total_tokens"].sum() if 'total_tokens' in df.columns else 0
        input_tokens = df["input_tokens"].sum() if 'input_tokens' in df.columns else 0
        output_tokens = df["output_tokens"].sum() if 'output_tokens' in df.columns else 0
        avg_tokens = total_tokens / total_requests if total_requests > 0 else 0

        card_style = {
            "backgroundColor": "#1E1E2F",
            "padding": "20px",
            "borderRadius": "10px",
            "margin": "10px",
            "flex": "1",
            "minWidth": "250px",
            "boxShadow": "0 4px 6px rgba(0,0,0,0.1)",
            "textAlign": "center",
            "transition": "all 0.3s ease",
            "transform": "translateY(0)"
        }

        return html.Div([
            # First row: Total Tokens and Input Tokens
            html.Div([
                html.Div([
                    html.H4("💬 Total Tokens", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{int(total_tokens):,}", style={"color": "#20c997"}),
                    html.P("Total tokens processed", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("📝 Input Tokens", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{int(input_tokens):,}", style={"color": "#007bff"}),
                    html.P("Total input tokens", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style)
            ], style={"display": "flex", "flexWrap": "wrap", "justifyContent": "space-around"}),

            # Second row: Output Tokens and Avg. Tokens per Request
            html.Div([
                html.Div([
                    html.H4("🗣️ Output Tokens", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{int(output_tokens):,}", style={"color": "#fd7e14"}),
                    html.P("Total output tokens", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("🔢 Avg. Tokens/Request", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{avg_tokens:.1f}", style={"color": "#28a745"}),
                    html.P("Average tokens per request", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style)
            ], style={"display": "flex", "flexWrap": "wrap", "justifyContent": "space-around"})
        ], style={"display": "flex", "flexDirection": "column"})
    
    def _create_cost_analysis_metrics(self, df):
        """Create dynamic cost analysis metrics from dataframe."""
        total_requests = len(df)
        total_cost = df["cost"].sum() if 'cost' in df.columns else 0.0
        avg_cost = total_cost / total_requests if total_requests > 0 else 0.0
        max_cost = df["cost"].max() if total_requests > 0 else 0.0
        total_tokens = df["total_tokens"].sum() if 'total_tokens' in df.columns and df["total_tokens"].sum() > 0 else 0
        cost_per_token = total_cost / total_tokens if total_tokens else 0.0

        card_style = {
            "backgroundColor": "#1E1E2F",
            "padding": "20px",
            "borderRadius": "10px",
            "margin": "10px",
            "flex": "1",
            "minWidth": "250px",
            "boxShadow": "0 4px 6px rgba(0,0,0,0.1)",
            "textAlign": "center",
            "transition": "all 0.3s ease",
            "transform": "translateY(0)"
        }

        return html.Div([
            # First row: Total Cost and Average Cost per Request
            html.Div([
                html.Div([
                    html.H4("💰 Total Cost", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"${total_cost:.4f}", style={"color": "#ffc107"}),
                    html.P("Cumulative expenditure", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("🧮 Avg. Cost/Request", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"${avg_cost:.4f}", style={"color": "#17a2b8"}),
                    html.P("Average cost per request", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style)
            ], style={"display": "flex", "flexWrap": "wrap", "justifyContent": "space-around"}),

            # Second row: Max Cost and Cost per Token
            html.Div([
                html.Div([
                    html.H4("💸 Max Cost", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"${max_cost:.4f}", style={"color": "#dc3545"}),
                    html.P("Highest cost incurred", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("📊 Cost per Token", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"${cost_per_token:.6f}", style={"color": "#20c997"}),
                    html.P("Average cost per token", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style)
            ], style={"display": "flex", "flexWrap": "wrap", "justifyContent": "space-around"})
        ], style={"display": "flex", "flexDirection": "column"})
    
    def _create_agent_analysis_metrics(self, df: pl.DataFrame):
        """Create dynamic agent analysis metrics from dataframe with action support."""
        # Filter out empty agent IDs
        agent_df = df.filter(pl.col("agent_id") != "")
        total_agent_requests = len(agent_df)
        unique_agents = len(agent_df["agent_id"].unique())
        avg_requests_per_agent = total_agent_requests / unique_agents if unique_agents > 0 else 0

        # Action-related metrics
        action_df = agent_df.filter(pl.col("action_id") != "")
        total_actions = len(action_df)
        unique_actions = len(action_df["action_id"].unique())
        actions_per_agent = total_actions / unique_agents if unique_agents > 0 else 0

        # Identify the top (most active) agent
        if unique_agents > 0:
            top_agent = agent_df["agent_id"][agent_df["agent_id"].value_counts()["count"].arg_max()]
            top_agent_count = agent_df["agent_id"].value_counts()["count"].max()
        else:
            top_agent = "N/A"
            top_agent_count = 0

        # Identify the most used action
        if total_actions > 0:
            top_action = action_df["action_id"][action_df["action_id"].value_counts()["count"].arg_max()]
            top_action_count = action_df["action_id"].value_counts()["count"].max()
        else:
            top_action = "N/A"
            top_action_count = 0

        # Compute agent-specific insuccess rate
        insuccessful_agent_requests = len([_ for _ in agent_df["success"] if not(_)])
        agent_insuccess_rate = insuccessful_agent_requests / total_agent_requests * 100 if total_agent_requests > 0 else 0

        card_style = {
            "backgroundColor": "#1E1E2F",
            "padding": "20px",
            "borderRadius": "10px",
            "margin": "10px",
            "flex": "1",
            "minWidth": "250px",
            "boxShadow": "0 4px 6px rgba(0,0,0,0.1)",
            "textAlign": "center",
            "transition": "all 0.3s ease",
            "transform": "translateY(0)"
        }

        return html.Div([
            # First row: Active Agents and Average Requests per Agent
            html.Div([
                html.Div([
                    html.H4("👥 Active Agents", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{unique_agents}", style={"color": "#6f42c1"}),
                    html.P("Unique agents in action", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("🔄 Unique Actions", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{unique_actions}", style={"color": "#dc3545"}),
                    html.P("Different actions available", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
            ], style={"display": "flex", "flexWrap": "wrap", "justifyContent": "space-around"}),

            # Second row: Top Agent and Agent Insuccess Rate
            html.Div([
                html.Div([
                    html.H4("🏆 Top Agent", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{top_agent} ({top_agent_count})", style={"color": "#fd7e14"}),
                    html.P("Most active agent", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("❌ Agent Insuccess Rate", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{agent_insuccess_rate:.1f}%", style={"color": "#28a745" if not agent_insuccess_rate else "#ffc107"}),
                    html.P("Insuccess rate of agent requests", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("🌟 Top Action", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{top_action} ({top_action_count})", style={"color": "#e83e8c"}),
                    html.P("Most executed action", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
            ], style={"display": "flex", "flexWrap": "wrap", "justifyContent": "space-around"})
        ], style={"display": "flex", "flexDirection": "column"})

    def _create_empty_dashboard(self):
        """Create empty dashboard components when no data is available."""
        empty_metrics = [html.Div([html.H4("No Data"), html.P("No records found")], className="metric-card")]
        empty_fig = go.Figure().update_layout(title="No Data Available", template=TEMPLATE)
        empty_table_data = []
        empty_table_columns = [{"name": "No Data", "id": "no_data"}]
        
        # Return all empty components for all tabs
        return (
            # Overview Tab
            empty_metrics, empty_fig, empty_fig, empty_fig, empty_fig,
            
            # Performance Tab
            empty_metrics, empty_fig, empty_fig, empty_fig, empty_fig,
            
            # Token Usage Tab
            empty_metrics, empty_metrics, empty_fig, empty_fig, empty_fig,
            
            # Cost Analysis Tab
            empty_metrics, empty_fig, empty_fig,
            
            # Agent Analysis Tab
            empty_metrics, empty_fig, empty_fig, empty_fig, empty_fig,
            # Actions
            empty_fig, empty_fig, empty_fig, empty_fig,

            # Additional Observability Plot
            empty_fig,

            # Operations Tab
            empty_table_data, empty_table_columns
        )

    def run_server(self, debug=False, port=8050, host="127.0.0.1"):
        """Run the dashboard server."""
        self.app.run_server(debug=debug, port=port, host=host)
        self.app.scripts.config.serve_locally = True

if __name__ == "__main__":
    # TODO add number of actions into overview -> change sucess rate by provider n -> sunburst with operation type and action
    # TODO consider place date range picker in same row as Global Filters but right alligned bellow refresh button and couple refresh with selected period
    # TODO add most expensive agent and agent with most actions in Agent Analysis
    # TODO add support to execute all operations on db (i.e filters and so on)
    od = ObservabilityDashboard(from_local_records_only=True, lazy=True)
    print(od.df)
    od.run_server()