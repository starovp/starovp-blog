import bt
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt

# Disable SettingWithCopyWarning
pd.options.mode.chained_assignment = None

###### Fetching Data ######

# The tickers we're interested in
tickers = [
    'SPY',
    'VIRT',
    'QQQ',
    'TLT',
    'GLD',
    'UVXY',
    '^VIX'
]

# Get maximum historical data for a single ticker
def get_yf_hist(ticker):
    data = yf.Ticker(ticker).history(period='max')['Close']
    data.rename(ticker, inplace=True)
    return data

# For each ticker, get the historical data and add it to a list
def get_data_for_tickers(tickers):
    data = []
    for ticker in tickers:
        data.append(get_yf_hist(ticker))
    df = pd.concat(data, axis=1)
    return df

data = get_data_for_tickers(tickers)
print(data)

###### Benchmark ######

# The name of our strategy
name = 'long_spy'

# Defining the actual strategy
benchmark_strat = bt.Strategy(
    name, 
    [
        bt.algos.RunOnce(),
        bt.algos.SelectAll(),
        bt.algos.WeighEqually(),
        bt.algos.Rebalance()
    ]
)

# Make sure we're only running on the SPY data by selecting it out,
# and dropping the rows for which we have no data
spy_data = data[['SPY']]
spy_data.dropna(inplace=True)

# Generate the backtest using the defined strategy and data and run it
benchmark_test = bt.Backtest(benchmark_strat, spy_data)
res = bt.run(benchmark_test)

# Print the summary and plot our equity progression
res.plot()
res.display()
plt.show()

###### Strategy 1 ######

name = 'spy_virt_7030'

strategy_1 = bt.Strategy(
    name, 
    [
        bt.algos.RunDaily(),
        bt.algos.SelectAll(),
        bt.algos.WeighSpecified(SPY=0.7, VIRT=0.3),
        bt.algos.Rebalance()
    ]
)

spy_virt_data = data[['SPY', 'VIRT']]
spy_virt_data.dropna(inplace=True)

backtest_1 = bt.Backtest(strategy_1, spy_virt_data)
res = bt.run(backtest_1, benchmark_test)

res.plot()
res.display()
plt.show()

###### Strategy 2 ######

name = 'eq_wt_monthly'

strategy_2 = bt.Strategy(
    name, 
    [
        bt.algos.RunMonthly(run_on_end_of_period=True),
        bt.algos.SelectAll(),
        bt.algos.WeighEqually(),
        bt.algos.Rebalance()
    ]
)

eq_wt_data = data[['SPY', 'QQQ', 'TLT', 'GLD']]
eq_wt_data.dropna(inplace=True)

backtest_2 = bt.Backtest(strategy_2, eq_wt_data)
res = bt.run(backtest_2, benchmark_test)

res.plot()
res.display()
plt.show()

###### Strategy 3 ######

# We're going to isolate our data here first, and then drop nulls, 
# since we need this series for the weights with the proper dates
spy_hl_data = data[['SPY']]
spy_hl_data.dropna(inplace=True)

# Generate returns and isolate the return series for simplicity
spy_ret = (spy_hl_data['SPY']/spy_hl_data['SPY'].shift(1)) - 1

# Rename for validation later
spy_ret.rename('SPY_returns', inplace=True)

# Create our weights series for SPY by copying the SPY price series
target_weights = spy_hl_data['SPY'].copy()

# Let's clear it and set all of them to None (you'll see why)
target_weights[:] = None

# We're going to start our strategy on day 1 with 100% SPY, so let's set the first weight to 1.0 (100%)
target_weights.iloc[0] = 1.0

# Now we need to fill in the dates where we know we want to make a change:
target_weights[spy_ret < 0.02] = 1.0
target_weights[spy_ret >= 0.02] = 0.5

# Weights need to be a DataFrame, not a series
target_weights = pd.DataFrame(target_weights)

# Now we want to fill each value forward to keep its previous allocation until we get an update
# That is, since we initially set every day's weight to have no value,
# and we only filled in day 1 at 100%, and filled in the days when we drop or gain,
# we need to maintain the previous day's allocation until we get a change. 
# So, we use ffill to forward-fill our weights, which will fill in our nulls in order using
# the most recent value seen that's not None/null.
target_weights.ffill(inplace=True)

# Let's make sure our prices, returns, and weights look ok
validation = pd.concat([spy_hl_data, spy_ret, target_weights], axis=1)
print(validation.tail(50))

name = 'spy_high_low'

strategy_3 = bt.Strategy(
    name, 
    [
        bt.algos.RunDaily(),
        bt.algos.SelectAll(),
        bt.algos.WeighTarget(target_weights),
        bt.algos.Rebalance()
    ]
)

backtest_3 = bt.Backtest(strategy_3, spy_hl_data)
res = bt.run(backtest_3, benchmark_test)

res.plot()
res.plot_weights() # Let's also plot our weights this time
res.display()
plt.show()

# How many days are our target weights at 0.5 divided by the total number of days
print(target_weights[target_weights == 0.5].count()/len(target_weights))


###### Strategy 4 ######

# Load in our VX continuous futures stream from our CSV, 
# specifying the 'Date' column as the index and converting it to datetime (so we can concat)
vx_cont = pd.read_csv('vx_cont.csv', index_col='Date')
vx_cont.index = pd.to_datetime(vx_cont.index)

# Add the VX cont series to our data
data = pd.concat([data, vx_cont], axis=1)

# Isolate the UVXY, VIX, and VX_CONT into their own dataset
strategy_4_data = data[['UVXY', '^VIX', 'VX_CONT']]

# Drop nulls so that we only have common data remaining
strategy_4_data.dropna(inplace=True)

# Split out the VIX and VX_CONT for simplicity
vix_spot = strategy_4_data['^VIX']
vix_fut = strategy_4_data['VX_CONT']

# Define the target weights
tw = vix_fut.copy()

# We want to be short by default at half
tw[:] = -0.5

# When current VIX greater than the closest future by more than 10%, revert and go fully long
tw[vix_spot/vix_fut > 1.1] = 1.0

# Convert our weights to a dataframe
tw = pd.DataFrame(tw)

# Rename the column so that it matches the instrument we're using (UVXY)
tw.columns = ['UVXY']

# Define the UVXY strategy
name = 'uvxy_dynamic'
strategy_4_uvxy = bt.Strategy(
    name, 
    [
        bt.algos.WeighTarget(tw), 
        bt.algos.Rebalance()
    ]
)

# Set up the backtest
uvxy_dynamic = bt.Backtest(strategy_4_uvxy, strategy_4_data[['UVXY']], integer_positions=False)

# Why integer positions? See UVXY head data
print(strategy_4_data['UVXY'].head(10))

# Run the backtest
res = bt.run(uvxy_dynamic, benchmark_test)

# Once we ran the previous backtest, we can extract the prices data to create synthetic securities
synthetic = bt.merge(res['uvxy_dynamic'].prices, res['long_spy'].prices)

# This is our new data, which is essentially the equity curve of each sub-strategy we tested.
# We can use this data to test our final strategy, just as before.
strategy_4 = bt.Strategy(
    'combined_uvxy_spy', 
    [
        bt.algos.SelectAll(),
        bt.algos.WeighSpecified(uvxy_dynamic=0.5, long_spy=0.5),
        bt.algos.Rebalance()
    ]
)

# Create and run
t = bt.Backtest(strategy_4, synthetic, integer_positions=False)
res = bt.run(t, benchmark_test)

# Display summary statistics and plot the weights
res.display()
res.plot()
res.plot_weights()
plt.show()