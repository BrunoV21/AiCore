from setuptools import setup, find_packages
from pathlib import Path

here = Path(__file__).resolve().parent
long_description = (here / "README.md").read_text(encoding="utf-8")

# Load requirements
install_requires = (here / "requirements.txt").read_text(encoding="utf-8").splitlines()
requirements_dashboard = (here / "requirements-dashboard.txt").read_text(encoding="utf-8").splitlines()
requirements_sql = (here / "requirements-sql.txt").read_text(encoding="utf-8").splitlines()

# Define extras
extras_require = {
    "dashboard": requirements_dashboard,
    "sql": requirements_sql,
}
extras_require["all"] = sorted(set(req for group in extras_require.values() for req in group))

setup(
    name="core-for-ai",
    version="0.2.1",
    author="Bruno V.",
    author_email="bruno.vitorino@tecnico.ulisboa.pt",
    description="A unified interface for interacting with various LLM and embedding providers, with observability tools.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/BrunoV21/AiCore",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "aicore": ["models_metadata.json"],
        "aicore.observability": ["assets/styles.css", "assets/favicon.ico"]
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
