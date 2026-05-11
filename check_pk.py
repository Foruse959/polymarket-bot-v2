import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), verbose=True)

pk = os.getenv('POLY_PRIVATE_KEY', '')
print(f'PK from env: {pk[:12]}... len={len(pk)}')

from config import Config
print(f'Config PK: {Config.POLY_PRIVATE_KEY[:12]}... len={len(Config.POLY_PRIVATE_KEY)}')
print(f'Config PROXY: {Config.POLY_PROXY_WALLET}')