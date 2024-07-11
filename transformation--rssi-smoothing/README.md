# RSSI Averaging

calculate various moving averages for RSSI

this project is based on Quix' starter transformation

### env

_the env file in this project has no secrets_

```sh
# configure the tumbling (or hopping) window size

ma_window_size=1000
ma_step=200
ma_grace=100

# configure the moving average window sizes

moving_averages="5 10 20 50 100 200"
```