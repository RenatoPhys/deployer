"""
Exemplo de execução do sistema de trading automatizado.
"""

import sys
import os
import importlib
from datetime import datetime
from dotenv import load_dotenv
import MetaTrader5 as mt5

# Adiciona o diretório pai ao path para importar o pacote deployer
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deployer.trader import AlgoTrader
from deployer.config.loader import ConfigManager, ConfigLoader
from deployer.utils.logger import setup_logger


def initialize_mt5():
    """Inicializa conexão com MetaTrader 5."""
    load_dotenv()
    
    login = int(os.getenv("MT5_LOGIN"))
    password = os.getenv("MT5_PASSWORD")
    server = os.getenv("MT5_SERVER")
    path = os.getenv("MT5_PATH")
    
    if not all([login, password, server]):
        raise ValueError("Credenciais MT5 não encontradas no arquivo .env")
    
    # Inicializa MT5
    if not mt5.initialize(login=login, server=server, password=password, path=path):
        raise RuntimeError(f"Falha ao inicializar MT5: {mt5.last_error()}")
    
    return True


def load_strategy_function(strategy_name: str):
    """
    Carrega dinamicamente a função de estratégia.
    
    Args:
        strategy_name: Nome da estratégia a carregar
        
    Returns:
        Função da estratégia
    """
    try:
        # Tenta importar do módulo de estratégias
        module = importlib.import_module("deployer.strategies.entries")
        strategy_func = getattr(module, strategy_name)
        return strategy_func
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Não foi possível carregar a estratégia '{strategy_name}': {str(e)}")


def main():
    """Função principal de execução."""
    logger = setup_logger("Main")
    
    try:
        # Inicializa MT5
        logger.info("Inicializando conexão com MetaTrader 5...")
        initialize_mt5()
        logger.info("MT5 conectado com sucesso!")
        
        # Carrega configuração do diretório examples
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "combined_strategy.json")
        
        if not os.path.exists(config_path):
            logger.error(f"Arquivo de configuração não encontrado: {config_path}")
            logger.info("Certifique-se de que combined_strategy.json está no diretório examples/")
            return
            
        logger.info(f"Carregando configuração de {config_path}...")
        config_manager = ConfigManager(config_path)
        config = config_manager.config
        
        # Verifica hora atual
        current_hour = datetime.now().hour
        logger.info(f"Hora atual: {current_hour}h")
        
        # Verifica se é hora de trading
        if not config_manager.is_trading_hour():
            logger.warning(f"Não há estratégia definida para {current_hour}h")
            logger.info(f"Horas de trading disponíveis: {sorted(config.hours)}")
            return
        
        # Obtém parâmetros da hora atual
        hour_params = config_manager.get_current_hour_params()
        if not hour_params:
            logger.error("Erro ao obter parâmetros da hora atual")
            return
        
        # Carrega função de estratégia
        logger.info(f"Carregando estratégia: {config.strategy}")
        strategy_func = load_strategy_function(config.strategy)
        
        # Prepara parâmetros da estratégia
        strategy_params = {
            "length_rsi": int(hour_params.get("length_rsi", 8)),
            "rsi_low": hour_params.get("rsi_low", 30),
            "rsi_high": hour_params.get("rsi_high", 70),
            "allowed_hours": hour_params.get("allowed_hours", [current_hour]),
            "position_type": hour_params.get("position_type", "both"),
        }
        
        # Log de configurações
        logger.info("=" * 60)
        logger.info("CONFIGURAÇÕES DE TRADING")
        logger.info(f"Símbolo: {config.symbol}")
        logger.info(f"Timeframe: {config.timeframe}")
        logger.info(f"Estratégia: {config.strategy}_{current_hour}h")
        logger.info(f"Position Type: {hour_params['position_type']}")
        logger.info(f"Take Profit: {hour_params['tp']} pontos")
        logger.info(f"Stop Loss: {hour_params['sl']} pontos")
        logger.info(f"Lote: {config.lote}")
        logger.info("=" * 60)
        
        # Obtém timeframe MT5
        mt5_timeframe = ConfigLoader.get_mt5_timeframe(config.timeframe)
        
        # Inicializa trader
        trader = AlgoTrader(
            symbol=config.symbol,
            timeframe=mt5_timeframe,
            strategy_name=f"{config.strategy}_{current_hour}h",
            strategy_func=strategy_func,
            strategy_params=strategy_params,
            tp=hour_params["tp"],
            sl=hour_params["sl"],
            lot_size=config.lote
        )
        
        # Inicia trading
        logger.info("Iniciando sistema de trading automatizado...")
        trader.start_trading()
        
    except KeyboardInterrupt:
        logger.info("Trading interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro fatal: {str(e)}", exc_info=True)
    finally:
        # Desconecta do MT5
        mt5.shutdown()
        logger.info("Conexão MT5 encerrada")


if __name__ == "__main__":
    main()