# python 3.x
from configparser import ConfigParser

config = ConfigParser()

config.add_section('main')
config.set('main', 'CLIENT_ID', '4UQAH7RPU8BKMVLG1VHC0MHFH2VSYWYL')
config.set('main', 'REDIRECT_URI', 'https://localhost/applogin')
config.set('main', 'JSON_PATH', './ts_state.json')
config.set('main', 'ACCOUNT_NUMBER', '866453716')

with open(file='config.ini', mode='w') as f:
    config.write(f)