from chainlit.input_widget import Select, Slider, Switch, TextInput
from utils import MODELS_PROVIDERS_MAP, REASONER_PROVIDERS_MAP

OPEN_LLM_SETTINGS = [
    Select(
        id="Model",
        label="Llm",
        values=list(MODELS_PROVIDERS_MAP.keys()),
        initial_index=0,
    ),
    Slider(
        id="Temperature",
        label="Temperature",
        initial=0,
        min=0,
        max=1,
        step=0.1,
    ),
    Slider(
        id="Max Tokens",
        label="Max Tokens",
        initial=1024,
        min=512,
        max=8192,
        step=256,
    ),
    TextInput(
        id="System Prompt",
        label="System Prompt",
        initial="You are a helpful assistant."
    ), 
    Switch(
        id="Use Reasoner",
        label="Use reasoner model",
        initial=True
    )
]

REASONER_SETTINGS = [
    Select(
        id="Reasoner Model",
        label="Reasoner Llm",
        values=list(REASONER_PROVIDERS_MAP.keys()),
        initial_index=0,
    ),
    Slider(
        id="Reasoner Temperature",
        label="Reasoner Temperature",
        initial=0.5,
        min=0,
        max=1,
        step=0.1,
    ),
    Slider(
        id="Reasoner Max Tokens",
        label="Reasoner Max Tokens",
        initial=1024,
        min=512,
        max=4096,
        step=256,
    ),
    TextInput(
        id="Reasoner System Prompt",
        label="Reasoner System Prompt",
        initial="You are a helpfull assistant with reasoning capabilites that breaks down problems into the detailed steps required to solve them"
    ), 
]


OPEN_AI_REASONER_SETTINGS = [
    Select(
        id="Reasoner Model",
        label="Reasoner Llm",
        values=list(REASONER_PROVIDERS_MAP.keys()),
        initial_index=0,
    ),
    TextInput(
        id="Reasoner Api Key",
        label="Reasoner Api Key",
        initial="your api key goes here..."
    ),
    Slider(
        id="Reasoner Temperature",
        label="Reasoner Temperature",
        initial=0.5,
        min=0,
        max=1,
        step=0.1,
    ),
    Slider(
        id="Reasoner Max Tokens",
        label="Reasoner Max Tokens",
        initial=1024,
        min=512,
        max=4096,
        step=256,
    ),
    TextInput(
        id="Reasoner System Prompt",
        label="Reasoner System Prompt",
        initial="You are a helpfull assistant with reasoning capabilites that breaks down problems into the detailed steps required to solve them"
    ), 
]

OPEN_AI_SETTINGS = [
    TextInput(
        id="Model",
        label="Llm",
        initial="gpt-4o-mini"
    ),
    TextInput(
        id="Api Key",
        label="Api Key",
        initial="your api key goes here..."
    ),
    TextInput(
        id="Base Url",
        label="Base Url",
        initial="leave this empty to connect to chatGPT"
    ),
    Slider(
        id="Temperature",
        label="Temperature",
        initial=0,
        min=0,
        max=1,
        step=0.1,
    ),
    Slider(
        id="Max Tokens",
        label="Max Tokens",
        initial=1024,
        min=512,
        max=8192,
        step=256,
    ),
    TextInput(
        id="System Prompt",
        label="System Prompt",
        initial="You are a helpful assistant."
    ),     
    Switch(
        id="Use Reasoner",
        label="Use reasoner model",
        initial=True
    )
]

PROFILES_SETTINGS = {
    "Reasoner4All": OPEN_LLM_SETTINGS + REASONER_SETTINGS,
    "OpenAi": OPEN_AI_SETTINGS + OPEN_AI_REASONER_SETTINGS
}