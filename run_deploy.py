import pandas as pd
from metatrader_deploy import TraderClass
import importlib
import MetaTrader5 as mt5

# Especificando estratégia do deploy
name_strategy = 'pattern_rsi_trend'  # Nome da função/classe no módulo entries
module = importlib.import_module('entries')
entry = getattr(module, name_strategy)

# Obtendo parâmetros
sym = 'WDO@N'
df_params = pd.read_json('combied_stategy.json')

# Iniciando trades
trader = TraderClass(
    symbol= sym, 
    timeframe= mt5.TIMEFRAME_M5,
    nome_estrategia = name_strategy,
    strategy_func=entry,
    strategy_params={
        "length_rsi": LENGTH_RSI,
        "rsi_low": RSI_LOW,
        "rsi_high": RSI_HIGH,
    }
)