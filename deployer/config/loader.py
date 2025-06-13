"""
Módulo para carregamento e validação de configurações.
"""

import json
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import MetaTrader5 as mt5


@dataclass
class StrategyConfig:
    """Configuração de uma estratégia de trading."""
    symbol: str
    timeframe: str
    strategy: str
    hours: List[int]
    hour_params: Dict[int, Dict[str, Any]]
    lote: float


class ConfigLoader:
    """Carregador e validador de configurações."""
    
    VALID_TIMEFRAMES = {
        "t1": mt5.TIMEFRAME_M1,
        "t5": mt5.TIMEFRAME_M5,
        "t15": mt5.TIMEFRAME_M15,
        "t30": mt5.TIMEFRAME_M30,
        "h1": mt5.TIMEFRAME_H1,
        "h4": mt5.TIMEFRAME_H4,
        "d1": mt5.TIMEFRAME_D1,
    }
    
    @classmethod
    def load_strategy_config(cls, filepath: str) -> StrategyConfig:
        """
        Carrega configuração de estratégia de um arquivo JSON.
        
        Args:
            filepath: Caminho para o arquivo de configuração
            
        Returns:
            StrategyConfig validado
            
        Raises:
            FileNotFoundError: Se o arquivo não existir
            ValueError: Se a configuração for inválida
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Arquivo de configuração não encontrado: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Valida configuração
        cls._validate_config(data)
        
        # Converte hour_params de string para int nas chaves
        hour_params = {
            int(hour): params 
            for hour, params in data['hour_params'].items()
        }
        
        return StrategyConfig(
            symbol=data['symbol'],
            timeframe=data['timeframe'],
            strategy=data['strategy'],
            hours=data['hours'],
            hour_params=hour_params,
            lote=data.get('lote', 1.0),
        )
    
    @classmethod
    def _validate_config(cls, config: Dict[str, Any]):
        """Valida a estrutura da configuração."""
        required_fields = ['symbol', 'timeframe', 'strategy', 'hours', 'hour_params']
        
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Campo obrigatório ausente: {field}")
        
        # Valida timeframe
        if config['timeframe'] not in cls.VALID_TIMEFRAMES:
            raise ValueError(
                f"Timeframe inválido: {config['timeframe']}. "
                f"Valores válidos: {list(cls.VALID_TIMEFRAMES.keys())}"
            )
        
        # Valida hours
        if not isinstance(config['hours'], list) or not config['hours']:
            raise ValueError("'hours' deve ser uma lista não vazia")
        
        # Valida hour_params
        for hour in config['hours']:
            hour_str = str(hour)
            if hour_str not in config['hour_params']:
                raise ValueError(f"Parâmetros ausentes para hora {hour}")
            
            hour_config = config['hour_params'][hour_str]
            cls._validate_hour_params(hour_config)
    
    @classmethod
    def _validate_hour_params(cls, params: Dict[str, Any]):
        """Valida parâmetros específicos de uma hora."""
        required = ['tp', 'sl', 'position_type']
        
        for field in required:
            if field not in params:
                raise ValueError(f"Parâmetro obrigatório ausente: {field}")
        
        # Valida position_type
        valid_positions = ['long', 'short', 'both']
        if params['position_type'] not in valid_positions:
            raise ValueError(
                f"position_type inválido: {params['position_type']}. "
                f"Valores válidos: {valid_positions}"
            )
        
        # Valida TP e SL
        if params['tp'] <= 0:
            raise ValueError("Take Profit (tp) deve ser positivo")
        
        if params['sl'] <= 0:
            raise ValueError("Stop Loss (sl) deve ser positivo")
    
    @classmethod
    def get_mt5_timeframe(cls, timeframe_str: str) -> int:
        """Converte string de timeframe para constante MT5."""
        return cls.VALID_TIMEFRAMES.get(timeframe_str, mt5.TIMEFRAME_M5)


class ConfigManager:
    """Gerenciador de configurações com funcionalidades extras."""
    
    def __init__(self, config_path: str):
        self.config = ConfigLoader.load_strategy_config(config_path)
        self._current_hour_cache = None
    
    def get_current_hour_params(self, hour: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Obtém parâmetros para a hora especificada ou atual.
        
        Args:
            hour: Hora específica (se None, usa hora atual)
            
        Returns:
            Parâmetros da hora ou None se não houver
        """
        from datetime import datetime
        
        if hour is None:
            hour = datetime.now().hour
        
        if hour not in self.config.hours:
            return None
        
        return self.config.hour_params.get(hour)
    
    def is_trading_hour(self, hour: Optional[int] = None) -> bool:
        """Verifica se é hora de trading."""
        from datetime import datetime
        
        if hour is None:
            hour = datetime.now().hour
        
        return hour in self.config.hours
    
    def get_strategy_info(self) -> Dict[str, Any]:
        """Retorna informações resumidas da estratégia."""
        return {
            'symbol': self.config.symbol,
            'strategy': self.config.strategy,
            'trading_hours': sorted(self.config.hours),
            'lot_size': self.config.lote,
            'total_hours': len(self.config.hours)
        }