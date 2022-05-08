import json
import pprint
import pandas as pd
import operator

from datetime import datetime
from datetime import timedelta
from configparser import ConfigParser

from td.client import TDClient

from pyrobot.robot import PyRobot
from pyrobot.indicators import Indicators
from pyrobot.trades import Trade

# Read config file
config = ConfigParser()
config.read("config/config.ini")

# Read the different values
CLIENT_ID = config.get('main', "CLIENT_ID")
REDIRECT_URI = config.get('main', "REDIRECT_URI")
CREDENTIALS_PATH = config.get('main', "JSON_PATH")
ACCOUNT_NUMBER = config.get('main', "ACCOUNT_NUMBER")

# initialize the PyRobot Object
trading_robot = PyRobot(
    client_id=CLIENT_ID,
    redirect_uri=REDIRECT_URI,
    credentials_path=CREDENTIALS_PATH,
    trading_account=ACCOUNT_NUMBER,
    paper_trading=True
)

# create a portfolio
trading_robot_portfolio = trading_robot.create_portfolio()

# define trading symbol
trading_symbol = 'AAPL'

# add single position
trading_robot_portfolio.add_position(symbol=trading_symbol, asset_type='equity')

# grab historical prices, first define start and end date
start_date = datetime.today()
end_date = start_date - timedelta(days=30)

# grab historical prices
historical_prices = trading_robot.grab_historical_prices(
    start=end_date,
    end=start_date,
    bar_size=1,
    bar_type='minute'
)
# convert data to a stock frame
stock_frame = trading_robot.create_stock_frame(
    data=historical_prices['aggregated']
)

# add stock frame to portfolio
trading_robot.portfolio.stock_frame = stock_frame
trading_robot.portfolio.historical_prices = historical_prices

# new indicator object
indicator_client = Indicators(price_data_frame=stock_frame)

# add 200/50 day sma
indicator_client.sma(period=20, column_name="sma_20")
indicator_client.sma(period=9, column_name="sma_9")

# add signal checker
indicator_client.set_indicator_signal_compare(
    indicator_1="sma_9",
    indicator_2="sma_20",
    condition_buy=operator.ge,
    condition_sell=operator.le
)

# Create a new trade object
new_long_trade = trading_robot.create_trade(
    trade_id='long_enter',
    enter_or_exit='enter',
    long_or_short='long',
    order_type='mkt'
)

# add order leg
new_long_trade.instrument(
    symbol=trading_symbol,
    quantity=1,
    asset_type='EQUITY'
)

# Exit position
# Create a new trade object
new_exit_trade = trading_robot.create_trade(
    trade_id='long_exit',
    enter_or_exit='exit',
    long_or_short='long',
    order_type='mkt'
)

# add order leg
new_exit_trade.instrument(
    symbol=trading_symbol,
    quantity=1,
    asset_type='EQUITY'
)


def default(obj):
    if isinstance(obj, TDClient):
        return str(obj)


# Save order
with open(file='order_strategies.json', mode='w+') as order_file:
    json.dump(
        obj=[new_long_trade.to_dict(), new_exit_trade.to_dict()],
        fp=order_file,
        default=default,
        indent=4
    )

# define trading dictionary
trades_dict = {
    trading_symbol: {
        'buy': {
            'trade_func': trading_robot.trades['long_enter'],
            'trade_id': trading_robot.trades['long_enter'].trade_id
        },
        'sell': {
            'trade_func': trading_robot.trades['long_exit'],
            'trade_id': trading_robot.trades['long_exit'].trade_id
        }
    }
}

# define the ownership
ownership_dict = {
    trading_symbol: False
}

# Initialize order variable
order = None

while trading_robot.regular_market_open:
    # Grab latest bar
    latest_bars = trading_robot.get_latest_bar()
    # add to the stockframe
    stock_frame.add_rows(data=latest_bars)
    # refresh the indicators
    indicator_client.refresh()

    print("=" * 50)
    print("Current Stock Frame:")
    print("-" * 50)
    print(stock_frame.symbol_groups.tail())
    print("-" * 50)
    print("")

    # check for signals
    signals = indicator_client.check_signals()

    # define the buy and sell signals
    buys = signals["buys"].to_list()
    sells = signals["sells"].to_list()

    print("=" * 50)
    print("Current Signals:")
    print("-" * 50)
    print("Symbol: {}".format(list(trades_dict.keys())[0]))
    print("Ownership Status: {}".format(ownership_dict[trading_symbol]))
    print("Buy Signals: {}".format(buys))
    print("Sell Signals: {}".format(sells))
    print("-" * 50)
    print("")

    if ownership_dict[trading_symbol] is False and buys:
        # execute trade
        trading_robot.execute_signals(
            signals=signals,
            trades_to_execute=trades_dict
        )
        ownership_dict[trading_symbol] = True
        buy_order: Trade = trades_dict[trading_symbol]['buy']['trade_func']
    elif ownership_dict[trading_symbol] is True and sells:
        # execute trade
        trading_robot.execute_signals(
            signals=signals,
            trades_to_execute=trades_dict
        )
        ownership_dict[trading_symbol] = False
        buy_order: Trade = trades_dict[trading_symbol]['sell']['trade_func']


    # grab the last row
    last_row = trading_robot.stock_frame.frame.tail(n=1)
    # Grab the last bar timestamp
    last_bar_timestamp = last_row.index.get_level_values(1)

    # wait til nex bar
    trading_robot.wait_till_next_bar(last_bar_timestamp=last_bar_timestamp)

    if order:
        order.check_status()