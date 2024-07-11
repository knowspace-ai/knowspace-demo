import os
from pyairtable import Api

from dotenv import load_dotenv
load_dotenv()

api = Api(os.environ['AIRTABLE_ACCESS_TOKEN'])
base = os.environ['AIRTABLE_BASE_ID']
# table = os.environ['AIRTABLE_PEOPLE_TABLE']
# tbl = os.environ['AIRTABLE_ALERTS_TABLE']
tbl = os.environ['AIRTABLE_EVENTS_TABLE']

table = api.table(base, tbl)