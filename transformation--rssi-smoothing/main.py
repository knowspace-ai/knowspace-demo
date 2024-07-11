import logging.config
import os
from datetime import timedelta
from quixstreams import Application, State
import uuid
import logging
from functools import partial
from statistics import mean

logging.disable(logging.WARNING)
# logger = logging.getLogger(__name__)
# for local dev, load env vars from a .env file
from dotenv import load_dotenv
load_dotenv()


app = Application(consumer_group="rssi-averaging-v2", auto_offset_reset="latest")
# app = Application(consumer_group=str(uuid.uuid4()), auto_offset_reset="latest")

input_topic = app.topic(os.environ["input"], timestamp_extractor=lambda row, *_: int(row["received"]))
output_topic = app.topic(os.environ["output"])

ma_window_size = int(os.environ.get("ma_window_size","5000"))
ma_step = int(os.environ.get("ma_step","500"))
ma_grace = int(os.environ.get("ma_grace", "100"))

moving_averages = tuple(map(int, os.environ.get("moving_averages","3 5 10").split(" ")))

sdf = app.dataframe(input_topic)

def reduce(agg: dict, current: dict):
    # skip previously seen hashes
    if current["hash"] in agg["known_hashes"]:
        return agg

    agg["window_contents"].append(current)
    agg["rssi_values"].append(current["rssi"])
    agg["rssi_count"] += 1
    agg["known_hashes"].append(current["hash"])

    return agg

def initialize(current):
    return {
        "window_contents": [current],
        "rssi_values": [current["rssi"]],
        "rssi_count": 0,
        "known_hashes": [current["hash"]]
    }

sdf = (
    # Define a hopping window of 10s with step 2s and grace period of 500ms
    # strange behavior of history being updated made the charts kind of flicker and jump around, expected of hopping window rewriting history
    # sdf.hopping_window(
    #     duration_ms=ma_window_size,
    #     step_ms=ma_step,
    #     grace_ms=ma_grace
    # )

    # tumbling windows have harsh boundaries and leave moving averages kind of disjoint from one window to the next
    sdf.tumbling_window(
        duration_ms=ma_window_size,
        grace_ms=ma_grace
    )

    # Specify the aggregation function
    .reduce(reducer=reduce, initializer=initialize)

    # Specify how the results should be emitted downstream.
    # "all()" will emit results as they come for each updated window,
    # possibly producing multiple messages per key-window pair
    # "final()" will emit windows only when they are closed and cannot
    # receive any updates anymore.
    # .current()
    .final()

    # promote the value to the full dataframe, remove start and end markers for the window
    .apply(lambda row: row["value"])
)

def calculate_moving_average(window_size, frame, state: State):
    """
    this function calculates moving averages for a given dyanmic window_size
        and stores historical values (outside of the current streaming window) in app state
        so the moving averages are smoothed across window boundaries
    """

    # list of moving averages is loaded from env to make it easy to explore new values
    global moving_averages
    max_window_size = max(moving_averages)

    rssi_values = frame['rssi_values']

    # Fetch previous RSSI values from the state
    prev_rssi_values = state.get('prev_rssi_values', [])

    # Combine previous and current RSSI values
    combined_rssi_values = prev_rssi_values + rssi_values

    # Ensure we keep all the most recent values needed for the largest possible window size
    state.set('prev_rssi_values', combined_rssi_values[-max_window_size:])

    # just calculate the moving average for the current window size
    # can't remember why this is returned as a single item list anymore
    # probably something chatgpt tricked me into accepting during a brief moment of weakness
    return [round(mean(combined_rssi_values[-window_size:]))]

# Calculate moving average of multiple sizes
moving_averages_headers = [(ma, f"rssi_ma{ma}") for ma in moving_averages]

for (ma, mah) in moving_averages_headers:
    # curry the cma function since we need the value of ma
    # and apply() requires a callback reference to engage application State
    # we could move this into the window reducer above
    cma = partial(calculate_moving_average, ma)

    # calculate the moving average for this particular value of ma
    # and turn on stateful tracking so we can smooth moving averages
    # across window boundaries, otherwise they get choppy
    sdf[mah] = sdf[["rssi_values"]].apply(cma, stateful=True)

# the window collapses (using reduce) the data for aggregate calculations
# so we want to expand it into rows again
def expander(row: dict):
    if "rssi_values" not in row:
        return [row]
    rows = []
    for index, value in enumerate(row["rssi_values"]):
        if index < len(row[mah]):
            new_row = {
                "rssi": value,
                **(row["window_contents"][index]),
                **{mah: row[mah][index -1] for (_, mah) in moving_averages_headers}
            }

            rows.append(new_row)
    return rows

# here is where the reduced rows get expanded
sdf = sdf.apply(expander, expand=True)

# sanity check
# just focus on the wristwatch beacon til i figure out what the hell is going on here
# sdf = sdf.filter(lambda row: row["gateway"] == "582b0aa9025d")    # office gateway
# sdf = sdf.filter(lambda row: row["beacon"] == "ea5d53e0907a")     # wristwatch beacon
# sdf = sdf[["received","source","gateway", "beacon", "hash", "rssi", "rssi_ma"]]       # just the facts, maam
# sdf = sdf[["received","source", "hash", "rssi", "rssi_ma", "rssi_count"]]             # just the facts

# easier to treat the visible columns as independent lines when messing around
# columns = [
#     "received",
#     "source",
#     # "hash",
#     "rssi",
# ]
# columns.extend(mah for (ma, mah) in moving_averages_headers)
# sdf = sdf[columns]

# sdf = sdf.update(print)

# someday soon!
sdf = sdf.to_topic(output_topic)

if __name__ == "__main__":
    app.run(sdf)
