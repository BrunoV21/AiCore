import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()


install_requires = [
    "google-genai== 0.6.0",
    "groq==0.13.1",
    "mistralai==1.2.3",
    # "mistral_common==1.5.1",
    "openai==1.56.1",
    "tiktoken==0.8.0",
    "pydantic==2.10.3",
    "PyYAML==6.0.2"
]

setuptools.setup(
    name="myaicore",
    version="0.1.4",
    author="Bruno V.",
    author_email="bruno.vitorino@tecnico.ulisboa.pt",
    description="..",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/BrunoV21/AiCore",
    packages=setuptools.find_packages(),
    install_requires=install_requires,
    classifiers=(
        "Programming Language :: Python :: 3.13",
        "License :: OSI Approved :: Apache 2.0 License",
        "Operating System :: OS Independent",
    ),
)