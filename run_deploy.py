import pandas as pd
import importlib
import MetaTrader5 as mt5
from datetime import datetime
from metatrader_deploy import TraderClass
import json

# Carregar parâmetros do JSON
with open("combined_strategy.json", "r") as f:
    config = json.load(f)
    
# Hora atual
current_hour = datetime.now().hour

# Verifica se essa hora tem estratégia definida
if current_hour not in config['hours']:
    print(f"[{current_hour}h] Não há estratégia definida para este horário.")
    exit()

# Seleciona os parâmetros da hora atual
hour_config = config['hour_params'][str(current_hour)]

# Importa a função de estratégia dinamicamente
strategy_name = config['strategy']
module = importlib.import_module("entries")
strategy_func = getattr(module, strategy_name)

# Inicializa a classe TraderClass
trader = TraderClass(
    symbol=config['symbol'],
    timeframe=mt5.TIMEFRAME_M5 if config['timeframe'] == 't5' else mt5.TIMEFRAME_M1,  # pode expandir conforme necessário
    nome_estrategia=f"{strategy_name}_{current_hour}h",
    strategy_func=strategy_func,
    strategy_params={
        "length_rsi": int(hour_config["length_rsi"]),
        "rsi_low": hour_config["rsi_low"],
        "rsi_high": hour_config["rsi_high"],
        "allowed_hours": hour_config.get("allowed_hours", [current_hour]),
        "position_type": hour_config.get("position_type", "both"),
    }
)

# Começar trading
trader.start_trading()