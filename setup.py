
import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()


install_requires = [
    "google-genai==0.6.0",
    "groq==0.13.1",
    "mistralai==1.2.3",
    "loguru==0.7.3",
    # "mistral_common==1.5.1",
    "openai==1.56.1",
    "tenacity==9.0.0",
    "tiktoken==0.8.0",
    "pydantic==2.10.3",
    "PyYAML==6.0.2",
    "ulid==1.1"
]

extras_require = {
    "dashboard": [
        "dash==2.14.1",
        "plotly==5.18.0",
        "pyarrow==19.0.1"
    ]
}

setuptools.setup(
    name="aicore",
    version="0.1.9",
    author="Bruno V.",
    author_email="bruno.vitorino@tecnico.ulisboa.pt",
    description="A unified interface for interacting with various LLM and embedding providers, with observability tools.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/BrunoV21/AiCore",
    packages=setuptools.find_packages(),
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