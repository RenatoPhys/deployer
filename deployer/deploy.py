"""
Sistema de deploy automatizado para estratégias de trading.
Versão com modo de espera para horários sem trading.
"""

import MetaTrader5 as mt5
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from pathlib import Path
import importlib.util
import sys
import time

from .trader import AlgoTrader
from .config.loader import ConfigManager
from .utils.logger import setup_logger


class AutoDeployer:
    """
    Classe para deploy automatizado de estratégias usando arquivos de configuração.
    """
    
    def __init__(self, config_path: str, env_path: Optional[str] = None, strategies_file: Optional[str] = None):
        """
        Inicializa o deployer com arquivo de configuração.
        
        Args:
            config_path: Caminho para o arquivo JSON de configuração
            env_path: Caminho para arquivo .env (opcional)
            strategies_file: Caminho para arquivo com estratégias (default: ./entries.py)
        """
        self.config_path = Path(config_path)
        self.env_path = env_path
        self.logger = setup_logger("AutoDeployer")
        
        # Define arquivo de estratégias (prioriza diretório atual)
        if strategies_file is None:
            # Procura primeiro no diretório atual
            local_entries = Path.cwd() / "entries.py"
            if local_entries.exists():
                strategies_file = str(local_entries)
                self.logger.info(f"Usando estratégias locais: {strategies_file}")
            else:
                # Fallback para o módulo interno
                strategies_file = "builtin"
                self.logger.info("Usando estratégias internas do pacote")
        
        self.strategies_file = strategies_file
        
        # Carrega configuração
        self.config_manager = ConfigManager(str(self.config_path))
        self.config = self.config_manager.config
        
        # Carrega a estratégia dinamicamente
        self.strategy_func = self._load_strategy()
        
        self.logger.info(f"Configuração carregada: {self.config_path}")
        self.logger.info(f"Estratégia: {self.config.strategy}")
        self.logger.info(f"Símbolo: {self.config.symbol}")
        self.logger.info(f"Horas de trading: {sorted(self.config.hours)}")
        self.logger.info(f"Magic Number: {self.config.magic_number}")
    
    def _load_strategy(self) -> Callable:
        """
        Carrega a estratégia dinamicamente do arquivo especificado.
        
        Returns:
            Função da estratégia
            
        Raises:
            ValueError: Se a estratégia não for encontrada
        """
        strategy_name = self.config.strategy
        
        # Se for "builtin", usa as estratégias internas
        if self.strategies_file == "builtin":
            from .strategies.entries import pattern_rsi_trend, bb_trend
            builtin_strategies = {
                "pattern_rsi_trend": pattern_rsi_trend,
                "bb_trend": bb_trend,
            }
            if strategy_name not in builtin_strategies:
                raise ValueError(f"Estratégia builtin '{strategy_name}' não encontrada")
            return builtin_strategies[strategy_name]
        
        # Carrega arquivo externo
        strategies_path = Path(self.strategies_file)
        if not strategies_path.exists():
            raise FileNotFoundError(f"Arquivo de estratégias não encontrado: {strategies_path}")
        
        # Importa o módulo dinamicamente
        spec = importlib.util.spec_from_file_location("custom_strategies", strategies_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Não foi possível carregar: {strategies_path}")
        
        module = importlib.util.module_from_spec(spec)
        sys.modules["custom_strategies"] = module
        spec.loader.exec_module(module)
        
        # Procura a estratégia no módulo
        if not hasattr(module, strategy_name):
            # Lista estratégias disponíveis
            available = [name for name in dir(module) 
                        if not name.startswith('_') and callable(getattr(module, name))]
            raise ValueError(
                f"Estratégia '{strategy_name}' não encontrada em {strategies_path}.\n"
                f"Disponíveis: {available}"
            )
        
        strategy_func = getattr(module, strategy_name)
        if not callable(strategy_func):
            raise ValueError(f"'{strategy_name}' não é uma função válida")
        
        self.logger.info(f"Estratégia '{strategy_name}' carregada de: {strategies_path}")
        return strategy_func
    
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
        self.logger.info(f"Magic Number: {self.config.magic_number}")
        
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
            strategy_func=self.strategy_func,
            strategy_params=strategy_params,
            tp=tp,
            sl=sl,
            lot_size=self.config.lote,
            magic_number=self.config.magic_number,
            env_path=self.env_path
        )
        
        # Passa a referência do config_manager
        trader.config_manager = self.config_manager
        
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
    
    def get_next_trading_hour(self) -> Optional[int]:
        """
        Retorna a próxima hora de trading configurada.
        
        Returns:
            Próxima hora de trading ou None se não houver mais hoje
        """
        current_hour = datetime.now().hour
        sorted_hours = sorted(self.config.hours)
        
        # Procura próxima hora maior que a atual
        for hour in sorted_hours:
            if hour > current_hour:
                return hour
        
        # Se não houver mais horas hoje, retorna a primeira hora de amanhã
        return sorted_hours[0] if sorted_hours else None
    
    def wait_for_next_trading_hour(self, check_interval: int = 60):
        """
        Aguarda até a próxima hora de trading.
        
        Args:
            check_interval: Intervalo em segundos para verificar a hora
        """
        while True:
            current_hour = datetime.now().hour
            
            # Verifica se é hora de trading
            if self.config_manager.is_trading_hour(current_hour):
                self.logger.info(f"✅ Hora de trading detectada: {current_hour}h")
                return current_hour
            
            # Calcula próxima hora de trading
            next_hour = self.get_next_trading_hour()
            
            if next_hour is None:
                self.logger.warning("Nenhuma hora de trading configurada!")
                return None
            
            # Calcula tempo de espera
            now = datetime.now()
            if next_hour > current_hour:
                # Próxima hora é hoje
                next_time = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
            else:
                # Próxima hora é amanhã
                tomorrow = now + timedelta(days=1)
                next_time = tomorrow.replace(hour=next_hour, minute=0, second=0, microsecond=0)
            
            wait_seconds = (next_time - now).total_seconds()
            wait_minutes = wait_seconds / 60
            
            self.logger.info(f"⏳ Aguardando próxima hora de trading: {next_hour}h")
            self.logger.info(f"   Tempo de espera: {wait_minutes:.1f} minutos")
            
            # Aguarda com verificações periódicas
            while datetime.now() < next_time:
                # Verifica se chegou na hora
                if datetime.now().hour == next_hour:
                    return next_hour
                
                # Feedback visual a cada 5 minutos
                remaining = (next_time - datetime.now()).total_seconds() / 60
                if int(remaining) % 5 == 0:
                    self.logger.info(f"   Faltam {remaining:.0f} minutos para {next_hour}h...")
                
                time.sleep(min(check_interval, wait_seconds))
    
    def run_current_session(self, end_hour: int = 17, end_minute: int = 54, wait_mode: bool = True):
        """
        Executa sessão de trading para a hora atual.
        
        Args:
            end_hour: Hora de encerramento
            end_minute: Minuto de encerramento
            wait_mode: Se True, aguarda próxima hora de trading se não for horário
        """
        trader = self.deploy_current_hour()
        
        if trader is None:
            if wait_mode:
                self.logger.info("🔄 Modo de espera ativado - aguardando próxima hora de trading")
                trading_hour = self.wait_for_next_trading_hour()
                
                if trading_hour is not None:
                    # Tenta novamente após esperar
                    trader = self.deploy_for_hour(trading_hour)
                else:
                    self.logger.error("Não foi possível determinar próxima hora de trading")
                    return
            else:
                self.logger.info("Não há trading configurado para o horário atual")
                return
        
        if trader is not None:
            try:
                with trader:  # Context manager para desconexão automática
                    trader.start_trading(end_hour=end_hour, end_minute=end_minute)
            except Exception as e:
                self.logger.error(f"Erro durante execução: {str(e)}")
                raise
    
    def run_continuous(self, end_hour: int = 17, end_minute: int = 54):
        """
        Executa trading continuamente, aguardando entre as sessões.
        
        Args:
            end_hour: Hora de encerramento do último período
            end_minute: Minuto de encerramento
        """
        self.logger.info("=== MODO CONTÍNUO INICIADO ===")
        self.logger.info(f"Horas configuradas: {sorted(self.config.hours)}")
        self.logger.info(f"Magic Number: {self.config.magic_number}")
        
        while True:
            current_hour = datetime.now().hour
            
            # Verifica se é hora de trading
            if self.config_manager.is_trading_hour(current_hour):
                self.logger.info(f"\n--- Iniciando trading para {current_hour}h ---")
                
                trader = self.deploy_for_hour(current_hour)
                if trader:
                    try:
                        with trader:
                            # Define fim como próxima hora ou end_hour
                            next_hour = self.get_next_trading_hour()
                            if next_hour and next_hour > current_hour:
                                session_end = next_hour
                                session_end_minute = 0
                            else:
                                session_end = end_hour
                                session_end_minute = end_minute
                            
                            trader.start_trading(end_hour=session_end, end_minute=session_end_minute)
                    except Exception as e:
                        self.logger.error(f"Erro na sessão {current_hour}h: {str(e)}")
                        
                # Aguarda próxima hora
                self.wait_for_next_trading_hour()
            else:
                # Não é hora de trading, aguarda
                self.wait_for_next_trading_hour()
    
    def run_full_day(self, end_hour: int = 17, end_minute: int = 54):
        """
        Executa trading para todas as horas configuradas do dia.
        
        Args:
            end_hour: Hora de encerramento do último período
            end_minute: Minuto de encerramento
        """
        self.logger.info("=== INICIANDO TRADING DIÁRIO ===")
        self.logger.info(f"Horas configuradas: {sorted(self.config.hours)}")
        self.logger.info(f"Magic Number: {self.config.magic_number}")
        
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
                        trader.start_trading(
                            end_hour=session_end, 
                            end_minute=0 if hour < max(self.config.hours) else end_minute
                        )
                except Exception as e:
                    self.logger.error(f"Erro na sessão {hour}h: {str(e)}")
                    continue
        
        self.logger.info("=== TRADING DIÁRIO FINALIZADO ===")
    
    def _wait_until_hour(self, target_hour: int):
        """Aguarda até atingir a hora especificada."""
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
            "strategy_source": self.strategies_file,
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
            "lot_size": self.config.lote,
            "magic_number": self.config.magic_number,
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
    env_path: Optional[str] = None,
    strategies_file: Optional[str] = None,
    wait_mode: bool = True
) -> Optional[AlgoTrader]:
    """
    Função de conveniência para deploy direto de arquivo de configuração.
    
    Args:
        config_path: Caminho para arquivo JSON
        mode: Modo de execução ("current", "full_day", "continuous", "deploy_only")
        end_hour: Hora de encerramento
        end_minute: Minuto de encerramento
        env_path: Caminho para .env
        strategies_file: Caminho para arquivo de estratégias (default: ./entries.py)
        wait_mode: Se True, aguarda próxima hora quando não há trading (apenas para mode="current")
        
    Returns:
        AlgoTrader se mode="deploy_only", senão None
    """
    deployer = AutoDeployer(config_path, env_path, strategies_file)
    
    if mode == "current":
        deployer.run_current_session(end_hour, end_minute, wait_mode)
    elif mode == "full_day":
        deployer.run_full_day(end_hour, end_minute)
    elif mode == "continuous":
        deployer.run_continuous(end_hour, end_minute)
    elif mode == "deploy_only":
        return deployer.deploy_current_hour()
    else:
        raise ValueError("Mode deve ser 'current', 'full_day', 'continuous' ou 'deploy_only'")
    
    return None


# Exemplo de uso rápido
if __name__ == "__main__":
    # Deploy com modo de espera ativado
    deploy_from_config("examples/combined_strategy.json", wait_mode=True)