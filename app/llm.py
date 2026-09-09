'''

This piece of code talks to calude api, returninig SQL

'''

import os
from dotenv import load_dotenv

# reads .env and copies the values into os.environ
load_dotenv()
API_Key = os.environ(['ANTHROPIC_API_KEY'])

