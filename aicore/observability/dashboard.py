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
    
    def __init__(self, storage_path: Optional[Any] = None, title: str = "AI Core Observability Dashboard"):
        """
        Initialize the dashboard.
        
        Args:
            storage: OperationStorage instance for accessing operation data
            title: Dashboard title
        """
        self.df = LlmOperationCollector.polars_from_file(storage_path)
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
        """Add date columns for time-based analysis"""
        self.df = self.df.with_columns(date=pl.col("timestamp").str.to_datetime())
        self.df = self.df.with_columns(day=pl.col("date").dt.date())
        self.df = self.df.with_columns(
            hour=pl.col("date").dt.hour(),
            minute=pl.col("date").dt.minute()
        )
        
    def _setup_layout(self):
        """Set up the dashboard layout with tabs."""
        self.app.layout = html.Div([
            # Header
            html.Div([
                html.H1(self.title, className="dashboard-title"),
                html.Div([
                    html.Div([
                        html.H3("Global Filters", style={"color": "white", "margin-bottom": "15px"}),
                        html.Div([
                            html.Label("Date Range:", style={"color": "white"}),
                            dcc.DatePickerRange(
                                id='date-picker-range',
                                start_date=(datetime.now() - timedelta(days=7)).date(),
                                end_date=datetime.now().date(),
                                display_format='YYYY-MM-DD',
                                style={"background-color": "#333", "color": "white"}
                            ),
                        ], style={"margin-bottom": "10px"}),
                        
                        html.Div([
                            html.Label("Provider:", style={"color": "white"}),
                            dcc.Dropdown(id='provider-dropdown', multi=True, 
                                style={"background-color": "#333", "color": "white"}),
                        ], style={"margin-bottom": "10px"}),
                        
                        html.Div([
                            html.Label("Model:", style={"color": "white"}),
                            dcc.Dropdown(id='model-dropdown', multi=True, 
                                style={"background-color": "#333", "color": "white"}),
                        ], style={"margin-bottom": "10px"}),
                        
                        html.Div([
                            html.Label("Agent:", style={"color": "white"}),
                            dcc.Dropdown(id='agent-dropdown', multi=True, 
                                style={"background-color": "#333", "color": "white"}),
                        ], style={"margin-bottom": "15px"}),
                        
                        html.Button('Apply Filters', id='apply-filters', n_clicks=0,
                            className="btn btn-primary btn-block"),
                    ], className="filter-panel"),
                ], className="filter-container"),
            ], className="dashboard-header"),
            
            # Tabs container
            html.Div([
                dcc.Tabs(id="dashboard-tabs", value='overview-tab', className="custom-tabs", children=[
                    # Overview Tab
                    dcc.Tab(label='Overview', value='overview-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
                            html.Div(id='overview-metrics', className="metrics-container"),
                            
                            html.Div([
                                html.Div([
                                    html.H3("Request Volume Over Time"),
                                    dcc.Graph(id='requests-time-series')
                                ], className="chart-box"),
                                
                                html.Div([
                                    html.H3("Success Rate by Provider"),
                                    dcc.Graph(id='success-rate-chart')
                                ], className="chart-box"),
                            ], className="chart-row"),
                            
                            html.Div([
                                html.Div([
                                    html.H3("Provider Distribution"),
                                    dcc.Graph(id='provider-distribution')
                                ], className="chart-box"),
                                
                                html.Div([
                                    html.H3("Model Distribution"),
                                    dcc.Graph(id='model-distribution')
                                ], className="chart-box"),
                            ], className="chart-row"),
                        ], className="tab-content")
                    ]),
                    
                    # Performance Tab
                    dcc.Tab(label='Performance', value='performance-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.H3("Latency Distribution"),
                                    dcc.Graph(id='latency-histogram')
                                ], className="chart-box"),
                                
                                html.Div([
                                    html.H3("Latency by Provider"),
                                    dcc.Graph(id='latency-by-provider')
                                ], className="chart-box"),
                            ], className="chart-row"),
                            
                            html.Div([
                                html.Div([
                                    html.H3("Latency by Model"),
                                    dcc.Graph(id='latency-by-model')
                                ], className="chart-box"),
                                
                                html.Div([
                                    html.H3("Latency Timeline"),
                                    dcc.Graph(id='latency-timeline')
                                ], className="chart-box"),
                            ], className="chart-row"),
                        ], className="tab-content")
                    ]),
                    
                    # Token Usage Tab
                    dcc.Tab(label='Token Usage', value='token-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.H3("Token Usage by Provider"),
                                    dcc.Graph(id='token-by-provider')
                                ], className="chart-box"),
                                
                                html.Div([
                                    html.H3("Token Usage by Model"),
                                    dcc.Graph(id='token-by-model')
                                ], className="chart-box"),
                            ], className="chart-row"),
                            
                            html.Div([
                                html.Div([
                                    html.H3("Input vs Output Tokens"),
                                    dcc.Graph(id='token-distribution')
                                ], className="chart-box"),
                                
                                html.Div([
                                    html.H3("Cost Analysis"),
                                    dcc.Graph(id='cost-analysis')
                                ], className="chart-box"),
                            ], className="chart-row"),
                        ], className="tab-content")
                    ]),
                    
                    # Agent Analysis Tab
                    dcc.Tab(label='Agent Analysis', value='agent-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
                            html.Div([
                                html.Div([
                                    html.H3("Agent Usage Distribution"),
                                    dcc.Graph(id='agent-distribution')
                                ], className="chart-box"),
                                
                                html.Div([
                                    html.H3("Agent Performance"),
                                    dcc.Graph(id='agent-performance')
                                ], className="chart-box"),
                            ], className="chart-row"),
                            
                            html.Div([
                                html.Div([
                                    html.H3("Agent Model Preference"),
                                    dcc.Graph(id='agent-model-preference')
                                ], className="chart-box"),
                                
                                html.Div([
                                    html.H3("Agent Provider Preference"),
                                    dcc.Graph(id='agent-provider-preference')
                                ], className="chart-box"),
                            ], className="chart-row"),
                        ], className="tab-content")
                    ]),
                    
                    # Operations Tab
                    dcc.Tab(label='Operations Data', value='operations-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
                            html.Div([
                                html.H3("Operation Details"),
                                dash_table.DataTable(
                                    id='operations-table',
                                    page_size=15,
                                    style_table={'overflowX': 'auto'},
                                    style_cell={
                                        'textAlign': 'left',
                                        'padding': '10px',
                                        'minWidth': '100px', 'maxWidth': '300px',
                                        'whiteSpace': 'normal',
                                        'textOverflow': 'ellipsis',
                                        'backgroundColor': '#333',
                                        'color': 'white'
                                    },
                                    style_header={
                                        'backgroundColor': '#444',
                                        'fontWeight': 'bold',
                                        'color': 'white'
                                    },
                                    style_data_conditional=[
                                        {
                                            'if': {'row_index': 'odd'},
                                            'backgroundColor': '#2a2a2a'
                                        },
                                        {
                                            'if': {'filter_query': '{success} = false', 'column_id': 'success'},
                                            'backgroundColor': '#5c1e1e',
                                            'color': 'white'
                                        }
                                    ],
                                    filter_action="native",
                                    sort_action="native",
                                    sort_mode="multi",
                                )
                            ], className="table-container")
                        ], className="tab-content")
                    ]),
                ]),
            ], className="tabs-container"),
        ], className="dashboard-wrapper")
        
    def _register_callbacks(self):
        """Register dashboard callbacks."""
        
        @self.app.callback(
            [Output('provider-dropdown', 'options'),
             Output('model-dropdown', 'options'),
             Output('agent-dropdown', 'options')],
            [Input('apply-filters', 'n_clicks')]
        )
        def update_dropdowns(_):
            """Update dropdown options based on available data."""
            if self.df.is_empty():
                return [], [], []
            
            providers = self.df['provider'].unique().to_list()
            models = self.df['model'].unique().to_list()
            agents = [a for a in self.df['agent_id'].unique().to_list() if a]  # Filter empty agent IDs
            
            provider_options = [{'label': p, 'value': p} for p in providers]
            model_options = [{'label': m, 'value': m} for m in models]
            agent_options = [{'label': a if a else 'No Agent', 'value': a} for a in agents]
            
            return provider_options, model_options, agent_options
        
        @self.app.callback(
            [
                # Overview Tab
                Output('overview-metrics', 'children'),
                Output('requests-time-series', 'figure'),
                Output('success-rate-chart', 'figure'),
                Output('provider-distribution', 'figure'),
                Output('model-distribution', 'figure'),
                
                # Performance Tab
                Output('latency-histogram', 'figure'),
                Output('latency-by-provider', 'figure'),
                Output('latency-by-model', 'figure'),
                Output('latency-timeline', 'figure'),
                
                # Token Usage Tab
                Output('token-by-provider', 'figure'),
                Output('token-by-model', 'figure'),
                Output('token-distribution', 'figure'),
                Output('cost-analysis', 'figure'),
                
                # Agent Analysis Tab
                Output('agent-distribution', 'figure'),
                Output('agent-performance', 'figure'),
                Output('agent-model-preference', 'figure'),
                Output('agent-provider-preference', 'figure'),
                
                # Operations Tab
                Output('operations-table', 'data'),
                Output('operations-table', 'columns')
            ],
            [Input('apply-filters', 'n_clicks')],
            [State('date-picker-range', 'start_date'),
             State('date-picker-range', 'end_date'),
             State('provider-dropdown', 'value'),
             State('model-dropdown', 'value'),
             State('agent-dropdown', 'value')]
        )
        def update_dashboard(n_clicks, start_date, end_date, providers, models, agents):
            """Update dashboard visualizations based on filters."""
            filtered_df = self.filter_data(start_date, end_date, providers, models, agents)
            
            if filtered_df.is_empty():
                # Return empty visualizations if no data
                empty_outputs = self._create_empty_dashboard()
                return empty_outputs
            
            # Overview Tab
            metrics = self._create_overview_metrics(filtered_df)
            
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
            
            # Success rate by provider
            success_by_provider = filtered_df.group_by("provider").agg(
                pl.col("success").mean().mul(100).round(1).alias("success_rate"),
                pl.len().alias("count")
            )
            success_rate_fig = px.bar(
                success_by_provider, 
                x='provider', 
                y='success_rate',
                color='success_rate',
                color_continuous_scale='RdYlGn',
                text='success_rate',
                template=TEMPLATE
            )
            success_rate_fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            success_rate_fig.update_layout(yaxis_title="Success Rate (%)")
            
            # Provider distribution pie chart
            provider_dist = filtered_df.group_by("provider").agg(pl.len().alias("count"))
            provider_fig = px.pie(
                provider_dist, 
                names='provider', 
                values='count',
                hole=0.4,
                template=TEMPLATE
            )
            
            # Model distribution pie chart
            model_dist = filtered_df.group_by("model").agg(pl.len().alias("count"))
            model_fig = px.pie(
                model_dist, 
                names='model', 
                values='count',
                hole=0.4,
                template=TEMPLATE
            )
            
            # Performance Tab
            # Latency histogram
            latency_fig = px.histogram(
                filtered_df, 
                x='latency_ms', 
                nbins=30,
                color_discrete_sequence=['#636EFA'],
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
                template=TEMPLATE
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
                template=TEMPLATE
            )
            latency_model_fig.update_layout(yaxis_title="Avg Latency (ms)")
            
            # Latency timeline
            latency_timeline_fig = px.scatter(
                filtered_df.sort("timestamp"),
                x='timestamp',
                y='latency_ms',
                color='provider',
                hover_data=['model', 'success'],
                template=TEMPLATE
            )
            latency_timeline_fig.update_layout(yaxis_title="Latency (ms)")
            
            # Token Usage Tab
            # Token usage by provider
            token_by_provider = filtered_df.filter(
                (pl.col("input_tokens") > 0) | (pl.col("output_tokens") > 0)
            ).group_by("provider").agg(
                pl.col("input_tokens").sum().alias("input_tokens"),
                pl.col("output_tokens").sum().alias("output_tokens"),
                pl.col("total_tokens").sum().alias("total_tokens")
            )
            token_provider_fig = px.bar(
                token_by_provider,
                x='provider',
                y=['input_tokens', 'output_tokens'],
                barmode='group',
                template=TEMPLATE
            )
            
            # Token usage by model
            token_by_model = filtered_df.filter(
                (pl.col("input_tokens") > 0) | (pl.col("output_tokens") > 0)
            ).group_by("model").agg(
                pl.col("input_tokens").sum().alias("input_tokens"),
                pl.col("output_tokens").sum().alias("output_tokens"),
                pl.col("total_tokens").sum().alias("total_tokens")
            )
            token_model_fig = px.bar(
                token_by_model,
                x='model',
                y='total_tokens',
                color='model',
                template=TEMPLATE
            )
            token_model_fig.update_layout(yaxis_title="Total Tokens")
            
            # Input vs Output tokens distribution
            token_dist_data = filtered_df.filter(
                (pl.col("input_tokens") > 0) | (pl.col("output_tokens") > 0)
            ).select(
                pl.col("input_tokens").sum().alias("Input"),
                pl.col("output_tokens").sum().alias("Output")
            )
            
            # Convert to format suitable for pie chart
            token_dist_data = {
                "category": ["Input Tokens", "Output Tokens"],
                "value": [token_dist_data[0,0], token_dist_data[0,1]]
            }
            token_dist_fig = px.pie(
                token_dist_data,
                names='category',
                values='value',
                color_discrete_sequence=['#1f77b4', '#ff7f0e'],
                template=TEMPLATE
            )
            
            # Cost analysis
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
                    template=TEMPLATE
                )
                cost_fig.update_layout(yaxis_title="Total Cost")
            else:
                cost_fig = px.bar(
                    {"model": ["No cost data"], "total_cost": [0]},
                    x='model',
                    y='total_cost',
                    template=TEMPLATE
                )
                cost_fig.update_layout(title="No cost data available")
            
            # Agent Analysis Tab
            # Agent distribution
            agent_data = filtered_df.filter(pl.col("agent_id") != "")
            if agent_data.height > 0:
                agent_dist = agent_data.group_by("agent_id").agg(pl.len().alias("count"))
                agent_dist_fig = px.pie(
                    agent_dist,
                    names='agent_id',
                    values='count',
                    template=TEMPLATE
                )
            else:
                agent_dist_fig = px.pie(
                    {"agent_id": ["No agent data"], "count": [1]},
                    names='agent_id',
                    values='count',
                    template=TEMPLATE
                )
                agent_dist_fig.update_layout(title="No agent data available")
            
            # Agent performance (success rate)
            if agent_data.height > 0:
                agent_perf = agent_data.group_by("agent_id").agg(
                    pl.col("success").mean().mul(100).round(1).alias("success_rate"),
                    pl.col("latency_ms").mean().alias("avg_latency"),
                    pl.len().alias("count")
                )
                agent_perf_fig = px.scatter(
                    agent_perf,
                    x='success_rate',
                    y='avg_latency',
                    size='count',
                    hover_name='agent_id',
                    color='agent_id',
                    template=TEMPLATE
                )
                agent_perf_fig.update_layout(
                    xaxis_title="Success Rate (%)",
                    yaxis_title="Avg Latency (ms)"
                )
            else:
                agent_perf_fig = px.scatter(
                    {"success_rate": [0], "avg_latency": [0], "count": [0], "agent_id": ["No agent data"]},
                    x='success_rate',
                    y='avg_latency',
                    size='count',
                    hover_name='agent_id',
                    template=TEMPLATE
                )
                agent_perf_fig.update_layout(title="No agent data available")
            
            # Agent model preference
            if agent_data.height > 0:
                agent_model_pref = agent_data.group_by(["agent_id", "model"]).agg(
                    pl.len().alias("count")
                )
                agent_model_fig = px.bar(
                    agent_model_pref,
                    x='agent_id',
                    y='count',
                    color='model',
                    barmode='stack',
                    template=TEMPLATE
                )
            else:
                agent_model_fig = px.bar(
                    {"agent_id": ["No agent data"], "count": [0], "model": ["None"]},
                    x='agent_id',
                    y='count',
                    color='model',
                    template=TEMPLATE
                )
                agent_model_fig.update_layout(title="No agent data available")
            
            # Agent provider preference
            if agent_data.height > 0:
                agent_provider_pref = agent_data.group_by(["agent_id", "provider"]).agg(
                    pl.len().alias("count")
                )
                agent_provider_fig = px.bar(
                    agent_provider_pref,
                    x='agent_id',
                    y='count',
                    color='provider',
                    barmode='stack',
                    template=TEMPLATE
                )
            else:
                agent_provider_fig = px.bar(
                    {"agent_id": ["No agent data"], "count": [0], "provider": ["None"]},
                    x='agent_id',
                    y='count',
                    color='provider',
                    template=TEMPLATE
                )
                agent_provider_fig.update_layout(title="No agent data available")
            
            # Operations Data Tab
            # Table data - select relevant columns
            display_columns = [
                "timestamp", "agent_id", "provider", "model", 
                "latency_ms", "input_tokens", "output_tokens", "total_tokens",
                "success", "cost", "operation_id", "session_id"
            ]
            table_data = filtered_df.select(display_columns).to_dicts()
            table_columns = [{"name": i, "id": i} for i in display_columns]
            
            return (
                # Overview Tab
                metrics, requests_ts_fig, success_rate_fig, provider_fig, model_fig,
                
                # Performance Tab
                latency_fig, latency_provider_fig, latency_model_fig, latency_timeline_fig,
                
                # Token Usage Tab
                token_provider_fig, token_model_fig, token_dist_fig, cost_fig,
                
                # Agent Analysis Tab
                agent_dist_fig, agent_perf_fig, agent_model_fig, agent_provider_fig,
                
                # Operations Data Tab
                table_data, table_columns
            )
        
    def filter_data(self, start_date, end_date, providers, models, agents):
        """Filter dataframe based on selected filters."""
        filtered_df = self.df.clone()
        
        # # Apply date filter
        # if start_date and end_date:
        #     filtered_df = filtered_df.filter(
        #         (pl.col("day") >= start_date) & 
        #         (pl.col("day") <= end_date)
        #     )
        
        # # Apply provider filter
        # if providers and len(providers) > 0:
        #     filtered_df = filtered_df.filter(pl.col("provider").is_in(providers))
        
        # # Apply model filter
        # if models and len(models) > 0:
        #     filtered_df = filtered_df.filter(pl.col("model").is_in(models))
        
        # # Apply agent filter
        # if agents and len(agents) > 0:
        #    filtered_df = filtered_df.filter(pl.col("agent_id").is_in(agents))
        
        return filtered_df
        
    def _create_overview_metrics(self, df):
        """Create overview metrics from dataframe."""
        total_requests = len(df)
        success_rate = df['success'].mean() * 100 if len(df) > 0 else 0
        avg_latency = df['latency_ms'].mean() if len(df) > 0 else 0
        
        # Count unique values
        unique_providers = len(df['provider'].unique())
        unique_models = len(df['model'].unique())
        unique_agents = len([a for a in df['agent_id'].unique() if a])  # Filter empty values
        
        # Tokens and cost (if available)
        total_tokens = df['total_tokens'].sum() if 'total_tokens' in df.columns else 0
        total_cost = df['cost'].sum() if 'cost' in df.columns else 0
        
        return [
            html.Div([
                html.H4("Total Requests"), 
                html.P(f"{total_requests:,}")
            ], className="metric-card"),
            
            html.Div([
                html.H4("Success Rate"), 
                html.P(f"{success_rate:.1f}%")
            ], className="metric-card"),
            
            html.Div([
                html.H4("Avg. Latency"), 
                html.P(f"{avg_latency:.2f} ms")
            ], className="metric-card"),
            
            html.Div([
                html.H4("Providers"), 
                html.P(f"{unique_providers}")
            ], className="metric-card"),
            
            html.Div([
                html.H4("Models"), 
                html.P(f"{unique_models}")
            ], className="metric-card"),
            
            html.Div([
                html.H4("Agents"), 
                html.P(f"{unique_agents}")
            ], className="metric-card"),
            
            html.Div([
                html.H4("Total Tokens"), 
                html.P(f"{int(total_tokens):,}")
            ], className="metric-card"),
            
            html.Div([
                html.H4("Total Cost"), 
                html.P(f"${total_cost:.4f}")
            ], className="metric-card"),
        ]
    
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
            empty_fig, empty_fig, empty_fig, empty_fig,
            
            # Token Usage Tab
            empty_fig, empty_fig, empty_fig, empty_fig,
            
            # Agent Analysis Tab
            empty_fig, empty_fig, empty_fig, empty_fig,
            
            # Operations Tab
            empty_table_data, empty_table_columns
        )
    
    def run_server(self, debug=False, port=8050, host="127.0.0.1"):
        """Run the dashboard server."""
        self.app.run_server(debug=debug, port=port, host=host)

if __name__ == "__main__":
    od = ObservabilityDashboard()
    print(od.df)
    od.run_server()