from quixstreams import Application
import os
from airtable import table
import json

from dotenv import load_dotenv
load_dotenv()

app = Application(consumer_group="airtable-destination-v1", auto_offset_reset = "latest")

input_topic = app.topic(os.environ["input"])

sdf = app.dataframe(input_topic)

# call the sink function for every message received.
sdf = sdf.update(lambda record: table.create({'raw': json.dumps(record) }))

# you can print the data row if you want to see what's going on.
# sdf = sdf.update(lambda row: print(row))

if __name__ == "__main__":
    app.run(sdf)