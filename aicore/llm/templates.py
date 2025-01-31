DEFAULT_SYSTEM_PROMPT = "You are a helpfull assistant"

REASONER_DEFAULT_SYSTEM_PROMPT = "You are a helpfull assistant with reasoning capabilites that breaks down problems into the detailed steps required to solve them"

REASONING_INJECTION_TEMPLATE = """
Consider the following reasoning steps to help you generate the answer:

{reasoning}
{reasoning_stop_token}
"""