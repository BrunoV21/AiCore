
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()


install_requires = [
    "anthropic==0.49.0",
    "google-genai==0.6.0",
    "groq==0.13.1",
    "mistralai==1.2.3",
    "loguru==0.7.3",
    # "mistral_common==1.5.1",
    "openai==1.66.3",
    "tenacity==9.0.0",
    "tiktoken==0.9.0",
    "pydantic==2.10.3",
    "PyYAML==6.0.2",
    "ulid==1.1"
]

extras_require = {
    "dashboard": [
        "dash==2.18.2",
        "dash_bootstrap_components==1.7.1",
        "pandas==2.2.3",
        "plotly==5.18.0",
        "polars==1.24.0",
        "pyarrow==19.0.1"
    ],
    "sql": [
        "aioodbc==0.5.0",
        "asyncpg==0.30.0",
        "psycopg2==2.9.10",
        "pyodbc==5.2.0",
        "python-dotenv==1.0.1",
        "SQLAlchemy==2.0.36"
    ],
    "all": [
        "dash==2.18.2",
        "dash_bootstrap_components==1.7.1",
        "pandas==2.2.3",
        "plotly==5.18.0",
        "polars==1.24.0",
        "pyarrow==19.0.1",
        "psycopg2==2.9.10",
        "pyodbc==5.2.0",
        "python-dotenv==1.0.1",
        "SQLAlchemy==2.0.36"
    ]
}

setuptools.setup(
    name="core-for-ai",
    version="0.1.87",
    author="Bruno V.",
    author_email="bruno.vitorino@tecnico.ulisboa.pt",
    description="A unified interface for interacting with various LLM and embedding providers, with observability tools.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/BrunoV21/AiCore",
    packages=setuptools.find_packages(),
    include_package_data=True,  # Ensure non-Python files are included
    package_data={
        "aicore.observability": ["assets/styles.css"]  # Specify the exact file path
    },
    install_requires=install_requires,
    extras_require=extras_require,
    classifiers=(
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ),
)
