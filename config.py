import os
from dotenv import load_dotenv

load_dotenv() # Charge les variables du fichier .env

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("La variable d'environnement OPENAI_API_KEY n'est pas définie. Veuillez la configurer.")