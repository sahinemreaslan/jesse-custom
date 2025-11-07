"""
Jesse Configuration File
"""
from jesse.config import config as jesse_config

# PostgreSQL database configuration
config = jesse_config

config['databases']['postgres_host'] = '127.0.0.1'
config['databases']['postgres_name'] = 'jesse_db'
config['databases']['postgres_port'] = 5432
config['databases']['postgres_username'] = 'voidstring'
config['databases']['postgres_password'] = ''

# Redis configuration
config['databases']['redis_host'] = '127.0.0.1'
config['databases']['redis_port'] = 6379
config['databases']['redis_password'] = ''

# Exchanges
config['env']['exchanges']['Binance Futures'] = {
    'fee': 0.0004,  # 0.04% trading fee
}

config['env']['exchanges']['Binance'] = {
    'fee': 0.001,  # 0.1% trading fee
}

# App settings
config['app']['trading_mode'] = 'backtest'
config['app']['considering_exchanges'] = ['Binance Futures']
