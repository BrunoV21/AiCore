from aicore.llm.providers.anthropic.oauth import authenticate_claude_max
# import json

if __name__ == '__main__':
    print("Anthropic OAuth Authentication")
    print("=" * 50)
    result = authenticate_claude_max()
    if result['type'] == 'success':
        print("\nAuthentication successful!")
        print(f"Access Token: {result['access'][:20]}...")
        print(f"Refresh Token: {result['refresh'][:20]}...")
        # print(f"{json.dumps(result), indent=4}")
    else:
        print("\nAuthentication failed!")
