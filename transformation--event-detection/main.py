import os
from quixstreams import Application

# for local dev, load env vars from a .env file
from dotenv import load_dotenv
load_dotenv()

app = Application(consumer_group="event-detection-v1", auto_offset_reset="earliest", use_changelog_topics=False)

input_topic = app.topic(os.environ["input"])
output_topic = app.topic(os.environ["output"])

sdf = app.dataframe(input_topic)

# sdf = sdf.update(print)

sdf = sdf[sdf["rssi_ma5"] > int(os.environ["rssi_threshold"])]

# sdf = sdf.update(print)

# # do something based on events detected in a window of time
n = 30000 # one alert per 30 seconds

def count_alerts(state: dict, row: dict):
    state["count"] += 1
    state["alert"] = row

    return state

# We count alerts to send only first one.
sdf = sdf.tumbling_window(n).reduce(count_alerts, lambda row: count_alerts({"count": 0}, row)).current()

# # Take only first alert.
sdf = sdf[sdf["value"]["count"] == 1]
sdf = sdf.apply(lambda row: row["value"]["alert"])

# sdf = sdf.update(print)

# Send the message to the output topic
sdf = sdf.to_topic(output_topic)

# # tracking last known location
# def count_messages(value: dict, state: State):
#     total = state.get('total', default=0)
#     total += 1
#     state.set('total', total)
#     return {**value, 'total': total}

# # Apply a custom function and inform StreamingDataFrame
# # to provide a State instance to it using "stateful=True"
# sdf = sdf.apply(count_messages, stateful=True)


# Print JSON messages in console.
# sdf = sdf.update(print)
# sdf = sdf.update(lambda row: print(json.dumps(row, indent=4)))



if __name__ == "__main__":
    app.run(sdf)