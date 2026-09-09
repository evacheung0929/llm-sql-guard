'''

This piece of code talks to calude api, returninig SQL

'''

import os
from dotenv import load_dotenv
import anthropic

# reads .env and copies the values into os.environ
load_dotenv()
API_Key = os.environ.get('ANTHROPIC_API_KEY')
anthropic_client = anthropic.Client(api_key=API_Key)



def test() -> str:
    role = 'user'
    message_content = "hi claude"
    message = anthropic_client.messages.create(
        model="claude-haiku-4-5",
        messages=[{"role": role, "content": message_content}],
        max_tokens=100,
    )
    print(message)

    return message.content[0].text
test()
