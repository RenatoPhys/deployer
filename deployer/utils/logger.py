"""
Utilitários para logging do sistema de trading.
"""

import logging
import os
from datetime import datetime
from typing import Optional


def setup_logger(
    name: str, 
    log_dir: str = "logs",
    level: int = logging.INFO,
    console_output: bool = True,
    file_output: bool = True
) -> logging.Logger:
    """
    Configura um logger personalizado para o sistema de trading.
    
    Args:
        name: Nome do logger
        log_dir: Diretório para salvar os logs
        level: Nível de logging (default: INFO)
        console_output: Se deve mostrar logs no console
        file_output: Se deve salvar logs em arquivo
        
    Returns:
        Logger configurado
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove handlers existentes para evitar duplicação
    logger.handlers = []
    
    # Formato das mensagens
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para console
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Handler para arquivo
    if file_output:
        # Cria diretório de logs se não existir
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Nome do arquivo com data
        filename = f"{log_dir}/{name}_{datetime.now():%Y%m%d}.log"
        file_handler = logging.FileHandler(filename, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


class TradingLogger:
    """
    Classe especializada para logging de operações de trading.
    """
    
    def __init__(self, symbol: str, strategy: str):
        self.logger = setup_logger(f"Trading_{symbol}_{strategy}")
        self.symbol = symbol
        self.strategy = strategy
    
    def log_trade(
        self, 
        action: str, 
        price: float, 
        volume: float,
        tp: Optional[float] = None,
        sl: Optional[float] = None,
        profit: Optional[float] = None
    ):
        """Registra informações de um trade."""
        msg = f"[{action}] {self.symbol} | Preço: {price:.2f} | Volume: {volume}"
        
        if tp and sl:
            msg += f" | TP: {tp:.2f} | SL: {sl:.2f}"
        
        if profit is not None:
            msg += f" | Lucro: {profit:.2f}"
        
        self.logger.info(msg)
    
    def log_error(self, error_msg: str, exception: Optional[Exception] = None):
        """Registra erros com detalhes da exceção."""
        if exception:
            self.logger.error(f"{error_msg}: {type(exception).__name__} - {str(exception)}")
        else:
            self.logger.error(error_msg)
    
    def log_summary(self, total_trades: int, total_profit: float, win_rate: float):
        """Registra resumo das operações."""
        self.logger.info("=" * 60)
        self.logger.info("RESUMO DAS OPERAÇÕES")
        self.logger.info(f"Estratégia: {self.strategy}")
        self.logger.info(f"Total de trades: {total_trades}")
        self.logger.info(f"Lucro total: R$ {total_profit:.2f}")
        self.logger.info(f"Taxa de acerto: {win_rate:.2%}")
        self.logger.info("=" * 60)