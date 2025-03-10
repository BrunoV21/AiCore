from aicore.observability.collector import LlmOperationCollector

import dash
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
from typing import Optional, Any
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
        """Add date columns for time-based analysis"""
        self.df = self.df.with_columns(date=pl.col("timestamp").str.to_datetime())
        self.df = self.df.with_columns(
            day=pl.col("date").dt.date(),
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
                        # Workspace and Session in the same row
                        html.Div([
                            html.Div([
                                html.Label("Workspace:", style={"color": "white"}),
                                dcc.Dropdown(
                                    id='workspace-dropdown',
                                    multi=True,
                                    style={"background-color": "#333", "color": "white"}
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
                                            dcc.Dropdown(
                                                id='provider-dropdown',
                                                multi=True,
                                                style={"background-color": "#333", "color": "white"}
                                            ),
                                        ], style={"margin-bottom": "10px"}),

                                        html.Div([
                                            html.Button('Refresh Data', id='refresh-data', n_clicks=0, className="btn btn-secondary btn-sm")
                                        ], style={"margin-bottom": "5px"}),

                                        html.Div([
                                            html.Label("Model:", style={"color": "white"}),
                                            dcc.Dropdown(
                                                id='model-dropdown',
                                                multi=True,
                                                style={"background-color": "#333", "color": "white"}
                                            ),
                                        ], style={"margin-bottom": "10px"}),

                                        html.Div([
                                            html.Label("Agent:", style={"color": "white"}),
                                            dcc.Dropdown(
                                                id='agent-dropdown',
                                                multi=True,
                                                style={"background-color": "#333", "color": "white"}
                                            ),
                                        ], style={"margin-bottom": "10px"}),

                                        html.Button('Apply Filters', id='apply-filters', n_clicks=0, className="btn btn-primary btn-block"),
                                    ],
                                    title="Additional Filters", style={
                                        "backgroundColor": "#333",
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
                    dcc.Tab(label='Overview', value='overview-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
                            html.Div(id='overview-metrics', className="metrics-container"),

                            html.Div([
                                html.Div([
                                    html.H3("Request Volume Over Time"),
                                    dcc.Graph(id='requests-time-series')
                                ], style={'flex': '1', 'padding': '10px'}),
                                html.Div([
                                    html.H3("Success Rate by Provider"),
                                    dcc.Graph(id='success-rate-chart')
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
                    ]),

                    # Performance Tab
                    dcc.Tab(label='Performance', value='performance-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
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
                    ]),

                    # Token Usage Tab
                    dcc.Tab(label='Token Usage', value='token-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
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
                    ]),

                    # Cost Analysis Tab
                    dcc.Tab(label='Cost Analysis', value='cost-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
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
                    ]),

                    # Agent Analysis Tab
                    dcc.Tab(label='Agent Analysis', value='agent-tab', className="custom-tab", selected_className="custom-tab-selected", children=[
                        html.Div([
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

                            # Row 2: Agent preferences
                            html.Div([
                                html.Div([
                                    html.H3("Agent Model Preference"),
                                    dcc.Graph(id='agent-model-preference')
                                ], style={'flex': '1', 'padding': '10px'}),
                                html.Div([
                                    html.H3("Agent Provider Preference"),
                                    dcc.Graph(id='agent-provider-preference')
                                ], style={'flex': '1', 'padding': '10px'})
                            ], style={'display': 'flex'}),

                            # Row 3: Token and cost consumption by agent
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
                        ], style={'padding': '10px'})
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
                                        'whiteSpace': 'nowrap',  # Prevents wrapping
                                        'overflow': 'hidden',  # Hides overflow text
                                        'textOverflow': 'ellipsis',  # Shows ellipsis for overflow text
                                        'backgroundColor': '#333',
                                        'color': 'white',
                                        'height': '24px',  # Defines row height (adjust based on font size)
                                        'cursor': 'pointer'  # Indicates clickability
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
                            ], className="table-container")
                        ], className="tab-content")
                    ])
                ]),
            ], className="tabs-container"),
        ], className="dashboard-wrapper")
        
    def _register_callbacks(self):
        """Register dashboard callbacks."""
        
        @self.app.callback(
            [Output('provider-dropdown', 'options'),
            Output('model-dropdown', 'options'),
            Output('agent-dropdown', 'options'),
            Output('session-dropdown', 'options'),
            Output('workspace-dropdown', 'options')],
            [Input('apply-filters', 'n_clicks'),
            Input('workspace-dropdown', 'value')]
        )
        def update_dropdowns(n_clicks, selected_workspaces):
            """Update dropdown options based on available data, filtering by workspace if provided."""
            if self.df.is_empty():
                return [], [], [], [], []
            
            # Compute workspace options from the full dataframe
            workspaces = self.df["workspace"].unique().to_list()
            workspace_options = [{'label': w, 'value': w} for w in workspaces]
            
            # If a workspace filter is applied, filter the dataframe accordingly
            df_filtered = self.df
            if selected_workspaces:
                df_filtered = self.df.filter(pl.col("workspace").is_in(selected_workspaces))
            
            # Compute other dropdown options from the filtered dataframe
            providers = df_filtered["provider"].unique().to_list()
            models = df_filtered["model"].unique().to_list()
            sessions = df_filtered["session_id"].unique().to_list()
            agents = [a for a in df_filtered["agent_id"].unique().to_list() if a]  # Filter empty agent IDs
            
            provider_options = [{'label': p, 'value': p} for p in providers]
            model_options = [{'label': m, 'value': m} for m in models]
            session_options = [{'label': s, 'value': s} for s in sessions]
            agent_options = [{'label': a, 'value': a} for a in agents]
            
            return provider_options, model_options, agent_options, session_options, workspace_options

        @self.app.callback(
            [
                # Overview Tab
                Output('overview-metrics', 'children'),
                Output('requests-time-series', 'figure'),
                Output('success-rate-chart', 'figure'),
                Output('provider-model-sunburst', 'figure'),
                Output('model-distribution', 'figure'),
                
                # Performance Tab
                Output('latency-histogram', 'figure'),
                Output('latency-by-provider', 'figure'),
                Output('latency-by-model', 'figure'),
                Output('latency-timeline', 'figure'),
                
                # Token Usage Tab
                Output('token-efficiency-chart', 'figure'),
                Output('token-by-model', 'figure'),
                Output('token-distribution', 'figure'),
                Output('cost-analysis', 'figure'),
                
                # Cost Analysis Tab
                Output('cost-breakdown-sunburst', 'figure'),
                Output('cost-per-token', 'figure'),
                
                # Agent Analysis Tab
                Output('agent-distribution', 'figure'),
                Output('agent-performance', 'figure'),
                Output('agent-model-preference', 'figure'),
                Output('agent-provider-preference', 'figure'),
                # New outputs for tokens and cost by agent:
                Output('agent-tokens', 'figure'),
                Output('agent-cost', 'figure'),
                
                # Additional Observability Plot
                Output('operation-type-distribution', 'figure'),
                
                # Operations Tab
                Output('operations-table', 'data'),
                Output('operations-table', 'columns')
            ],
            [Input('apply-filters', 'n_clicks'), Input('refresh-data', 'n_clicks')],
            [State('date-picker-range', 'start_date'),
            State('date-picker-range', 'end_date'),
            State('session-dropdown', 'value'),
            State('workspace-dropdown', 'value'),
            State('provider-dropdown', 'value'),
            State('model-dropdown', 'value'),
            State('agent-dropdown', 'value')]
        )
        def update_dashboard(n_clicks, refresh_clicks, start_date, end_date, session_id, workspace, providers, models, agents):
            """Update dashboard visualizations based on filters."""
            filtered_df = self.filter_data(start_date, end_date, session_id, workspace, providers, models, agents)
            
            if filtered_df.is_empty():
                # Return empty visualizations if no data
                empty_outputs = self._create_empty_dashboard()
                # Append an empty pie chart for the additional observability plot
                empty_outputs += (px.pie({"operation_type": ["No data"], "count": [1]},
                                        names='operation_type',
                                        values='count',
                                        template=TEMPLATE,
                                        title="Operation Type Distribution"),)
                # Also append empty figures for the new agent tokens and cost plots
                empty_outputs += (px.bar({"agent_id": ["No data"], "total_tokens": [0]},
                                        x="agent_id", y="total_tokens",
                                        template=TEMPLATE,
                                        title="Total Tokens by Agent"),
                                px.bar({"agent_id": ["No data"], "total_cost": [0]},
                                        x="agent_id", y="total_cost",
                                        template=TEMPLATE,
                                        title="Total Cost by Agent"))
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
                template=TEMPLATE,
                title="Token Usage by Model"
            )
            token_model_fig.update_layout(yaxis_title="Total Tokens")
            
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
            
            # Cost per token
            cost_per_token = filtered_df.filter(
                (pl.col("cost") > 0) & (pl.col("total_tokens") > 0)
            ).with_columns(
                cost_per_token=(pl.col("cost") / pl.col("total_tokens")) * 1000
            ).group_by("model").agg(
                pl.col("cost_per_token").mean().alias("avg_cost_per_1k")
            )
            cost_per_token_fig = px.bar(
                cost_per_token, 
                x="model", 
                y="avg_cost_per_1k", 
                template=TEMPLATE,
                title="Cost per 1K Tokens by Model"
            )
            cost_per_token_fig.update_layout(yaxis_title="Cost per 1K Tokens ($)")
            
            # Agent Analysis Tab
            # Agent distribution
            agent_data = filtered_df.filter(pl.col("agent_id") != "")
            if agent_data.height > 0:
                agent_dist = agent_data.group_by("agent_id").agg(pl.len().alias("count"))
                agent_dist_fig = px.pie(
                    agent_dist,
                    names='agent_id',
                    values='count',
                    template=TEMPLATE,
                    title="Agent Distribution"
                )
            else:
                agent_dist_fig = px.pie(
                    {"agent_id": ["No agent data"], "count": [1]},
                    names='agent_id',
                    values='count',
                    template=TEMPLATE,
                    title="No agent data available"
                )
            
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
                    template=TEMPLATE,
                    title="Agent Performance"
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
                    template=TEMPLATE,
                    title="No agent data available"
                )
            
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
                    template=TEMPLATE,
                    title="Agent Model Preference"
                )
            else:
                agent_model_fig = px.bar(
                    {"agent_id": ["No agent data"], "count": [0], "model": ["None"]},
                    x='agent_id',
                    y='count',
                    color='model',
                    template=TEMPLATE,
                    title="No agent data available"
                )
            
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
                    template=TEMPLATE,
                    title="Agent Provider Preference"
                )
            else:
                agent_provider_fig = px.bar(
                    {"agent_id": ["No agent data"], "count": [0], "provider": ["None"]},
                    x='agent_id',
                    y='count',
                    color='provider',
                    template=TEMPLATE,
                    title="No agent data available"
                )
            
            # New: Tokens consumed by agent
            if agent_data.height > 0:
                tokens_by_agent = agent_data.group_by("agent_id").agg(
                    pl.col("total_tokens").sum().alias("total_tokens"),
                    pl.col("input_tokens").sum().alias("input_tokens"),
                    pl.col("output_tokens").sum().alias("output_tokens")
                )
                agent_tokens_fig = px.bar(
                    tokens_by_agent.sort("total_tokens", descending=True),
                    x="agent_id",
                    y=["total_tokens", "input_tokens", "output_tokens"],
                    template=TEMPLATE,
                    title="Tokens by Agent"
                )
                agent_tokens_fig.update_layout(
                    yaxis_title="Tokens",
                    barmode="group"
                )
            else:
                agent_tokens_fig = px.bar(
                    {"agent_id": ["No agent data"], "total_tokens": [0]},
                    x="agent_id",
                    y="total_tokens",
                    template=TEMPLATE,
                    title="No token data available"
                )
            
            # New: Cost incurred by agent
            if agent_data.height > 0:
                cost_by_agent = agent_data.filter(pl.col("cost") > 0).group_by("agent_id").agg(
                    pl.col("cost").sum().alias("total_cost")
                )
                agent_cost_fig = px.bar(
                    cost_by_agent.sort("total_cost", descending=True),
                    x="agent_id",
                    y="total_cost",
                    template=TEMPLATE,
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
            display_columns = filtered_df.columns
            table_data = filtered_df.select(display_columns).to_dicts()
            table_columns = [{"name": i, "id": i} for i in display_columns]
            
            return (
                # Overview Tab
                metrics, requests_ts_fig, success_rate_fig, sunburst_fig, model_fig,
                
                # Performance Tab
                latency_fig, latency_provider_fig, latency_model_fig, latency_timeline_fig,
                
                # Token Usage Tab
                token_efficiency_fig, token_model_fig, token_dist_fig, cost_fig,
                
                # Cost Analysis Tab
                cost_sunburst_fig, cost_per_token_fig,
                
                # Agent Analysis Tab
                agent_dist_fig, agent_perf_fig, agent_model_fig, agent_provider_fig,
                agent_tokens_fig, agent_cost_fig,
                
                # Additional Observability Plot
                op_type_fig,
                
                # Operations Data Tab
                table_data, table_columns
            )
    
    def filter_data(self, start_date, end_date, session_id, workspace, providers, models, agents):
        """Filter dataframe based on selected filters."""
        filtered_df = self.df.clone()
        #TODO implement filter in polars
        # Column order for better analysis
        # if not filtered_df.is_empty():
        #     filtered_df = filtered_df.select(["timestamp", "operation_id", "session_id", "agent_id", "provider", "model", "operation_type", "success", "latency_ms", "input_tokens", "output_tokens", "total_tokens", "cost", "error_message", "system_prompt", "user_prompt", "response"])
        
        return filtered_df
        
    def _create_overview_metrics(self, df):
        """Create dynamic overview metrics from dataframe."""
        total_requests = len(df)
        successful_count = len([_ for _ in df["success"] if _])
        success_rate = successful_count / total_requests * 100 if total_requests > 0 else 0
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
            "textAlign": "center"
        }

        return html.Div([
            # First row: Total Requests, Success Rate, and Avg. Latency
            html.Div([
                html.Div([
                    html.H4("📊 Total Requests", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{total_requests:,}", style={"color": "#007bff"}),
                    html.P("Requests processed", style={"color": "#cccccc", "fontSize": "0.9rem"})
                ], className="metric-card", style=card_style),
                html.Div([
                    html.H4("✅ Success Rate", style={"color": "#ffffff", "marginBottom": "5px"}),
                    html.H2(f"{success_rate:.1f}%", style={"color": "#28a745"}),
                    html.P(f"{successful_count} of {total_requests} succeeded", style={"color": "#cccccc", "fontSize": "0.9rem"})
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
            
            # Cost Analysis Tab
            empty_fig, empty_fig,
            
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