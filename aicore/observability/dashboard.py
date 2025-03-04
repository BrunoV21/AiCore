
"""
Dashboard module for visualizing LLM operation data.

This module implements a Dash application for interactive visualization of LLM usage history,
providing insights into operation patterns, performance metrics, and request details.
"""

import dash
from dash import dcc, html, dash_table, callback, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

from aicore.observability.storage import OperationStorage


class ObservabilityDashboard:
    """
    Dashboard for visualizing LLM operation data.
    
    This class implements a Dash application that provides interactive visualizations
    of LLM usage history, including request volumes, latency metrics, token usage,
    model distribution, and other relevant analytics.
    """
    
    def __init__(self, storage: Optional[OperationStorage] = None, title: str = "AI Core Observability Dashboard"):
        """
        Initialize the dashboard.
        
        Args:
            storage: OperationStorage instance for accessing operation data
            title: Dashboard title
        """
        self.storage = storage or OperationStorage()
        self.title = title
        self.app = dash.Dash(__name__, suppress_callback_exceptions=True)
        self._setup_layout()
        self._register_callbacks()
        
    def _setup_layout(self):
        """Set up the dashboard layout."""
        self.app.layout = html.Div([
            html.H1(self.title, className="dashboard-title"),
            
            html.Div([
                html.Div([
                    html.H3("Filters"),
                    html.Label("Date Range:"),
                    dcc.DatePickerRange(
                        id='date-picker-range',
                        start_date=(datetime.now() - timedelta(days=7)).date(),
                        end_date=datetime.now().date(),
                        display_format='YYYY-MM-DD'
                    ),
                    html.Label("Provider:"),
                    dcc.Dropdown(id='provider-dropdown', multi=True),
                    html.Label("Model:"),
                    dcc.Dropdown(id='model-dropdown', multi=True),
                    html.Button('Apply Filters', id='apply-filters', n_clicks=0),
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
                html.H3("Operation Details"),
                dash_table.DataTable(
                    id='operations-table',
                    page_size=10,
                    style_table={'overflowX': 'auto'},
                    style_cell={
                        'textAlign': 'left',
                        'padding': '10px',
                        'minWidth': '100px', 'maxWidth': '300px',
                        'whiteSpace': 'normal', 'textOverflow': 'ellipsis'
                    },
                    style_header={
                        'backgroundColor': 'rgb(230, 230, 230)',
                        'fontWeight': 'bold'
                    }
                )
            ], className="operations-details")
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
            df = self.storage.get_all_records()
            if df.is_empty():
                return [], []
            
            # Convert to pandas for dropdown options formatting
            pdf = df.to_pandas()
            providers = pdf['provider'].unique()
            models = pdf['model'].unique()
            
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
                
            df = self.storage.query_records(filters, start_date, end_date)
            
            if df.is_empty():
                # Return empty visualizations if no data
                return self._create_empty_dashboard()
            
            # Convert to pandas for visualization
            pdf = df.to_pandas()
            
            # Create overview metrics
            metrics = self._create_overview_metrics(pdf)
            
            # Create time series of requests
            pdf['date'] = pd.to_datetime(pdf['timestamp']).dt.date
            requests_by_date = pdf.groupby('date').size().reset_index(name='count')
            time_series_fig = px.line(requests_by_date, x='date', y='count', 
                                      title='Requests Over Time')
            
            # Create latency histogram
            latency_fig = px.histogram(pdf, x='latency_ms', title='Operation Latency (ms)')
            
            # Create token usage chart
            token_fig = px.bar(pdf, x='model', y=['input_tokens', 'output_tokens'], 
                              barmode='group', title='Token Usage by Model')
            
            # Create provider/model distribution
            distribution_fig = px.sunburst(pdf, path=['provider', 'model'], values='latency_ms',
                                          title='Provider and Model Distribution')
            
            # Prepare table data
            table_data = pdf[['operation_id', 'timestamp', 'provider', 'model', 
                             'operation_type', 'latency_ms', 'success']].to_dict('records')
            table_columns = [{"name": i, "id": i} for i in pdf[['operation_id', 'timestamp', 
                                                              'provider', 'model', 
                                                              'operation_type', 'latency_ms', 
                                                              'success']].columns]
            
            return metrics, time_series_fig, latency_fig, token_fig, distribution_fig, table_data, table_columns
        
    def _create_overview_metrics(self, df: pd.DataFrame) -> List[html.Div]:
        """Create overview metrics from dataframe."""
        total_requests = len(df)
        success_rate = df['success'].mean() * 100
        avg_latency = df['latency_ms'].mean()
        
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