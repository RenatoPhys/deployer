# deployer/deploy.py
"""
Sistema de deploy automatizado para estratégias de trading.
"""

import MetaTrader5 as mt5
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from .trader import AlgoTrader
from .config.loader import ConfigManager
from .strategies.entries import pattern_rsi_trend, bb_trend
from .utils.logger import setup_logger


class AutoDeployer:
    """
    Classe para deploy automatizado de estratégias usando arquivos de configuração.
    """
    
    # Mapeamento de estratégias disponíveis
    AVAILABLE_STRATEGIES = {
        "pattern_rsi_trend": pattern_rsi_trend,
        "bb_trend": bb_trend,
    }
    
    def __init__(self, config_path: str, env_path: Optional[str] = None):
        """
        Inicializa o deployer com arquivo de configuração.
        
        Args:
            config_path: Caminho para o arquivo JSON de configuração
            env_path: Caminho para arquivo .env (opcional)
        """
        self.config_path = Path(config_path)
        self.env_path = env_path
        self.logger = setup_logger("AutoDeployer")
        
        # Carrega configuração
        self.config_manager = ConfigManager(str(self.config_path))
        self.config = self.config_manager.config
        
        # Validações
        self._validate_strategy()
        
        self.logger.info(f"Configuração carregada: {self.config_path}")
        self.logger.info(f"Estratégia: {self.config.strategy}")
        self.logger.info(f"Símbolo: {self.config.symbol}")
        self.logger.info(f"Horas de trading: {sorted(self.config.hours)}")
    
    def _validate_strategy(self):
        """Valida se a estratégia existe no sistema."""
        if self.config.strategy not in self.AVAILABLE_STRATEGIES:
            available = list(self.AVAILABLE_STRATEGIES.keys())
            raise ValueError(
                f"Estratégia '{self.config.strategy}' não encontrada. "
                f"Disponíveis: {available}"
            )
    
    def deploy_for_hour(self, target_hour: Optional[int] = None) -> Optional[AlgoTrader]:
        """
        Faz deploy para uma hora específica ou hora atual.
        
        Args:
            target_hour: Hora específica (se None, usa hora atual)
            
        Returns:
            AlgoTrader configurado ou None se não for hora de trading
        """
        if target_hour is None:
            target_hour = datetime.now().hour
        
        # Verifica se é hora de trading
        if not self.config_manager.is_trading_hour(target_hour):
            self.logger.info(f"Hora {target_hour}h não está configurada para trading")
            return None
        
        # Obtém parâmetros da hora
        hour_params = self.config_manager.get_current_hour_params(target_hour)
        if not hour_params:
            self.logger.error(f"Parâmetros não encontrados para hora {target_hour}")
            return None
        
        # Cria trader com configurações específicas da hora
        trader = self._create_trader(hour_params)
        
        self.logger.info(f"✅ Deploy realizado para {target_hour}h")
        self.logger.info(f"TP: {hour_params['tp']} | SL: {hour_params['sl']}")
        self.logger.info(f"Posição: {hour_params['position_type']}")
        
        return trader
    
    def deploy_current_hour(self) -> Optional[AlgoTrader]:
        """
        Faz deploy para a hora atual.
        
        Returns:
            AlgoTrader configurado ou None se não for hora de trading
        """
        return self.deploy_for_hour()
    
    def _create_trader(self, hour_params: Dict[str, Any]) -> AlgoTrader:
        """
        Cria instância do AlgoTrader com parâmetros específicos.
        
        Args:
            hour_params: Parâmetros da hora atual
            
        Returns:
            AlgoTrader configurado
        """
        # Obtém função da estratégia
        strategy_func = self.AVAILABLE_STRATEGIES[self.config.strategy]
        
        # Prepara parâmetros da estratégia (remove TP, SL, etc.)
        strategy_params = hour_params.copy()
        tp = strategy_params.pop('tp')
        sl = strategy_params.pop('sl')
        strategy_params.pop('position_type', None)  # Já incluído nos params
        
        # Converte timeframe
        timeframe = self._get_mt5_timeframe()
        
        # Cria trader
        trader = AlgoTrader(
            symbol=self.config.symbol,
            timeframe=timeframe,
            strategy_name=self.config.strategy,
            strategy_func=strategy_func,
            strategy_params=strategy_params,
            tp=tp,
            sl=sl,
            lot_size=self.config.lote,
            env_path=self.env_path
        )
        
        return trader
    
    def _get_mt5_timeframe(self) -> int:
        """Converte timeframe da config para constante MT5."""
        timeframe_map = {
            "t1": mt5.TIMEFRAME_M1,
            "t5": mt5.TIMEFRAME_M5,
            "t15": mt5.TIMEFRAME_M15,
            "t30": mt5.TIMEFRAME_M30,
            "h1": mt5.TIMEFRAME_H1,
            "h4": mt5.TIMEFRAME_H4,
            "d1": mt5.TIMEFRAME_D1,
        }
        return timeframe_map.get(self.config.timeframe, mt5.TIMEFRAME_M5)
    
    def run_current_session(self, end_hour: int = 17, end_minute: int = 54):
        """
        Executa sessão de trading para a hora atual.
        
        Args:
            end_hour: Hora de encerramento
            end_minute: Minuto de encerramento
        """
        trader = self.deploy_current_hour()
        
        if trader is None:
            self.logger.info("Não há trading configurado para o horário atual")
            return
        
        try:
            with trader:  # Context manager para desconexão automática
                trader.start_trading(end_hour=end_hour, end_minute=end_minute)
        except Exception as e:
            self.logger.error(f"Erro durante execução: {str(e)}")
            raise
    
    def run_full_day(self, end_hour: int = 17, end_minute: int = 54):
        """
        Executa trading para todas as horas configuradas do dia.
        
        Args:
            end_hour: Hora de encerramento do último período
            end_minute: Minuto de encerramento
        """
        self.logger.info("=== INICIANDO TRADING DIÁRIO ===")
        self.logger.info(f"Horas configuradas: {sorted(self.config.hours)}")
        
        for hour in sorted(self.config.hours):
            self.logger.info(f"\n--- Preparando trading para {hour}h ---")
            
            # Aguarda até a hora de início
            self._wait_until_hour(hour)
            
            # Executa trading para esta hora
            trader = self.deploy_for_hour(hour)
            if trader:
                try:
                    with trader:
                        # Define fim como 1 hora depois ou end_hour se for o último
                        session_end = hour + 1 if hour < max(self.config.hours) else end_hour
                        trader.start_trading(end_hour=session_end, end_minute=0 if hour < max(self.config.hours) else end_minute)
                except Exception as e:
                    self.logger.error(f"Erro na sessão {hour}h: {str(e)}")
                    continue
        
        self.logger.info("=== TRADING DIÁRIO FINALIZADO ===")
    
    def _wait_until_hour(self, target_hour: int):
        """Aguarda até atingir a hora especificada."""
        import time
        
        while datetime.now().hour < target_hour:
            current = datetime.now()
            wait_time = (target_hour - current.hour) * 3600 - current.minute * 60 - current.second
            
            if wait_time > 0:
                self.logger.info(f"Aguardando {wait_time//60}min para iniciar às {target_hour}h")
                time.sleep(min(wait_time, 300))  # Max 5min de sleep
    
    def get_strategy_summary(self) -> Dict[str, Any]:
        """Retorna resumo da estratégia configurada."""
        return {
            "config_file": str(self.config_path),
            "strategy": self.config.strategy,
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
            "lot_size": self.config.lote,
            "trading_hours": sorted(self.config.hours),
            "total_sessions": len(self.config.hours),
            "hour_configs": {
                hour: {
                    "tp": params["tp"],
                    "sl": params["sl"], 
                    "position_type": params["position_type"]
                }
                for hour, params in self.config.hour_params.items()
            }
        }


# Função de conveniência para uso direto
def deploy_from_config(
    config_path: str, 
    mode: str = "current",
    end_hour: int = 17,
    end_minute: int = 54,
    env_path: Optional[str] = None
) -> Optional[AlgoTrader]:
    """
    Função de conveniência para deploy direto de arquivo de configuração.
    
    Args:
        config_path: Caminho para arquivo JSON
        mode: Modo de execução ("current", "full_day", "deploy_only")
        end_hour: Hora de encerramento
        end_minute: Minuto de encerramento
        env_path: Caminho para .env
        
    Returns:
        AlgoTrader se mode="deploy_only", senão None
    """
    deployer = AutoDeployer(config_path, env_path)
    
    if mode == "current":
        deployer.run_current_session(end_hour, end_minute)
    elif mode == "full_day":
        deployer.run_full_day(end_hour, end_minute)
    elif mode == "deploy_only":
        return deployer.deploy_current_hour()
    else:
        raise ValueError("Mode deve ser 'current', 'full_day' ou 'deploy_only'")
    
    return None


# Exemplo de uso rápido
if __name__ == "__main__":
    # Deploy simples para hora atual
    deploy_from_config("examples/combined_strategy.json")