from aicore.observability.collector import LlmOperationCollector

import dash
from dash import dcc, html, dash_table, callback, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

EXTERNAL_STYLESHEETS = [
    "https://stackpath.bootstrapcdn.com/bootswatch/4.5.2/darkly/bootstrap.min.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"
]

TEMPLATE = "plotly_dark"

class ObservabilityDashboard:
    """
    Dashboard for visualizing LLM operation data.
    
    This class implements a Dash application that provides interactive visualizations
    of LLM usage history, including request volumes, latency metrics, token usage,
    model distribution, and other relevant analytics.
    """
    
    def __init__(self, storage_path: Optional[Any] = None, title: str = "Ai Core Observability Dashboard"):
        """
        Initialize the dashboard.
        
        Args:
            storage: OperationStorage instance for accessing operation data
            title: Dashboard title
        """
        self.df :pl.DataFrame = LlmOperationCollector.polars_from_file(storage_path)
        self.add_day_col()
        self.title = title
        self.app = dash.Dash(
            __name__, 
            suppress_callback_exceptions=True,
            external_stylesheets=EXTERNAL_STYLESHEETS
        )
        self._setup_layout()
        self._register_callbacks()

    def add_day_col(self):
        self.df = self.df.with_columns(date=pl.col("timestamp").str.to_datetime())
        self.df = self.df.with_columns(day=pl.col("date").dt.date())
        
    def _setup_layout(self):
        """Set up the dashboard layout."""
        self.app.layout = html.Div([
            html.H1(self.title, className="dashboard-title"),
            
            html.Div([
                html.Div([
                    html.H3("Filters", style={"color": "white"}),
                    html.Label("Date Range:", style={"color": "white"}),
                    dcc.DatePickerRange(
                        id='date-picker-range',
                        start_date=(datetime.now() - timedelta(days=7)).date(),
                        end_date=datetime.now().date(),
                        display_format='YYYY-MM-DD',
                        style={"background-color": "#333", "color": "white"}  # Dark background
                    ),
                    html.Label("Provider:", style={"color": "white"}),
                    dcc.Dropdown(id='provider-dropdown', multi=True, style={"background-color": "#333", "color": "white"}),
                    html.Label("Model:", style={"color": "white"}),
                    dcc.Dropdown(id='model-dropdown', multi=True, 
                        style={"background-color": "#333", "color": "white"}),
                    html.Button('Apply Filters', id='apply-filters', n_clicks=0,
                        style={"background-color": "#444", "color": "white"}),
                ], className="filter-panel"),
                
                html.Div([
                    html.Div([
                        html.H3("Overview Metrics"),
                        html.Div(id='overview-metrics', className="metrics-container")
                    ], className="overview-section"),
                    
                    html.Div([
                        html.H3("Request Volume"),
                        dcc.Graph(id='requests-time-series')
                    ], className="chart-container"),
                    
                    html.Div([
                        html.H3("Latency Distribution"),
                        dcc.Graph(id='latency-histogram')
                    ], className="chart-container"),
                    
                    html.Div([
                        html.H3("Token Usage"),
                        dcc.Graph(id='token-usage-chart')
                    ], className="chart-container"),
                    
                    html.Div([
                        html.H3("Provider/Model Distribution"),
                        dcc.Graph(id='provider-model-distribution')
                    ], className="chart-container"),
                ], className="dashboard-main")
            ], className="dashboard-container"),
            
            html.Div([
                html.H3("Operation Details", style={"color": "white"}),  # White title
                dash_table.DataTable(
                    id='operations-table',
                    page_size=10,
                    style_table={'overflowX': 'auto'},  # Keep horizontal scroll
                    style_cell={
                        'textAlign': 'left',
                        'padding': '10px',
                        'minWidth': '100px', 'maxWidth': '300px',
                        'whiteSpace': 'normal',
                        'textOverflow': 'ellipsis',
                        'backgroundColor': '#333',  # Dark background for table cells
                        'color': 'white'  # White text
                    },
                    style_header={
                        'backgroundColor': '#444',  # Darker background for header
                        'fontWeight': 'bold',
                        'color': 'white'  # White text in header
                    },
                    style_data_conditional=[  # Optional: Add alternating row colors
                        {
                            'if': {'row_index': 'odd'},
                            'backgroundColor': '#2a2a2a'
                        }
                    ]
                )
            ], className="operations-details", style={"background-color": "#222", "padding": "10px", "border-radius": "10px"})
        ], className="dashboard-wrapper")
        
    def _register_callbacks(self):
        """Register dashboard callbacks."""
        
        @self.app.callback(
            [Output('provider-dropdown', 'options'),
             Output('model-dropdown', 'options')],
            [Input('apply-filters', 'n_clicks')]
        )
        def update_dropdowns(_):
            """Update dropdown options based on available data."""
            if self.df.is_empty():
                return [], []
            
            providers = self.df['provider'].unique()
            models = self.df['model'].unique()
            
            provider_options = [{'label': p, 'value': p} for p in providers]
            model_options = [{'label': m, 'value': m} for m in models]
            
            return provider_options, model_options
        
        @self.app.callback(
            [Output('overview-metrics', 'children'),
             Output('requests-time-series', 'figure'),
             Output('latency-histogram', 'figure'),
             Output('token-usage-chart', 'figure'),
             Output('provider-model-distribution', 'figure'),
             Output('operations-table', 'data'),
             Output('operations-table', 'columns')],
            [Input('apply-filters', 'n_clicks')],
            [State('date-picker-range', 'start_date'),
             State('date-picker-range', 'end_date'),
             State('provider-dropdown', 'value'),
             State('model-dropdown', 'value')]
        )
        def update_dashboard(n_clicks, start_date, end_date, providers, models):
            """Update dashboard visualizations based on filters."""
            # Apply filters
            filters = {}
            if providers:
                filters['provider'] = providers
            if models:
                filters['model'] = models

            if self.df.is_empty():
                # Return empty visualizations if no data
                return self._create_empty_dashboard()
            
            # Create overview metrics
            metrics = self._create_overview_metrics()
            
            # Create requests time series figure
            requests_by_date = self.df.group_by("day").agg(pl.col("response").count().alias("count"))
            # requests_by_date_pdf = requests_by_date.to_pandas()
            time_series_fig = px.line(requests_by_date, x='day', y='count', template=TEMPLATE,
                                    title='Requests Over Time').to_dict()
            
            # Create latency histogram
            latency_fig = px.histogram(self.df, x='latency_ms', template=TEMPLATE, title='Operation Latency (ms)').to_dict()

             # Create token usage chart
            token_fig = px.bar(self.df, x='model', y=['input_tokens', 'output_tokens'], 
                              barmode='group', template=TEMPLATE, title='Token Usage by Model')            
            
            # Create provider/model distribution
            distribution_fig = px.sunburst(self.df, path=['provider', 'model'], values='latency_ms', template=TEMPLATE,
                                        title='Provider and Model Distribution').to_dict()
            
            table_data = self.df.to_dicts()
            table_columns = [{"name": i, "id": i} for i in self.df.columns]
            
            return metrics, time_series_fig, latency_fig, token_fig, distribution_fig, table_data, table_columns
        
    def _create_overview_metrics(self) -> List[html.Div]:
        """Create overview metrics from dataframe."""
        total_requests = len(self.df)
        success_rate = self.df['success'].mean() * 100
        avg_latency = self.df['latency_ms'].mean()
        
        return [
            html.Div([html.H4("Total Requests"), html.P(total_requests)], className="metric-card"),
            html.Div([html.H4("Success Rate"), html.P(f"{success_rate:.1f}%")], className="metric-card"),
            html.Div([html.H4("Avg. Latency"), html.P(f"{avg_latency:.2f} ms")], className="metric-card")
        ]
    
    def _create_empty_dashboard(self):
        """Create empty dashboard components when no data is available."""
        empty_metrics = [html.Div([html.H4("No Data"), html.P("No records found")], className="metric-card")]
        empty_fig = go.Figure().update_layout(title="No Data Available")
        empty_table_data = []
        empty_table_columns = [{"name": "No Data", "id": "no_data"}]
        
        return empty_metrics, empty_fig, empty_fig, empty_fig, empty_fig, empty_table_data, empty_table_columns
    
    def run_server(self, debug=False, port=8050, host="127.0.0.1"):
        """Run the dashboard server."""
        self.app.run_server(debug=debug, port=port, host=host)