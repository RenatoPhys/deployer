"""
Módulo principal do trader para execução de estratégias de algo trading.
"""

import numpy as np
import datetime as dt
import pandas as pd
import MetaTrader5 as mt5
import time
from typing import Callable, Dict, Optional, Union
from .utils.logger import setup_logger


class AlgoTrader:
    """
    Classe principal para gerenciamento e execução de trades algorítmicos.
    
    Attributes:
        symbol: Símbolo do ativo a ser negociado
        timeframe: Timeframe para análise (ex: mt5.TIMEFRAME_M1)
        strategy_name: Nome identificador da estratégia
        strategy_func: Função que implementa a lógica da estratégia
        strategy_params: Parâmetros específicos da estratégia
        tp: Take Profit em pontos
        sl: Stop Loss em pontos
    """
    
    def __init__(
        self, 
        symbol: str, 
        timeframe: int, 
        strategy_name: str,
        strategy_func: Optional[Callable] = None, 
        strategy_params: Optional[Dict] = None, 
        tp: Optional[float] = None, 
        sl: Optional[float] = None,
        lot_size: float = 1.0,
        magic_number: int = 2
    ):
        # Configurações básicas
        self.symbol = symbol
        self.timeframe = timeframe
        self.strategy_name = strategy_name
        self.strategy_func = strategy_func
        self.strategy_params = strategy_params or {}
        self.tp = tp
        self.sl = sl
        self.lot_size = lot_size
        self.magic_number = magic_number
        
        # Estado interno
        self.data = None
        self.position = 0
        self.trades = 0
        self.trade_values = []
        self.quote_units = 0
        
        # Logger
        self.logger = setup_logger(f"AlgoTrader_{symbol}")
        
        # Validações
        self._validate_parameters()
        
    def _validate_parameters(self):
        """Valida os parâmetros de inicialização."""
        if self.strategy_func is None:
            raise ValueError("Uma função de estratégia deve ser fornecida.")
        
        if self.tp is None or self.sl is None:
            raise ValueError("Take Profit (tp) e Stop Loss (sl) devem ser definidos.")
        
        if self.tp <= 0 or self.sl <= 0:
            raise ValueError("Take Profit e Stop Loss devem ser valores positivos.")
    
    def start_trading(self, end_hour: int = 17, end_minute: int = 54):
        """
        Inicia o processo de trading automatizado.
        
        Args:
            end_hour: Hora de encerramento do trading
            end_minute: Minuto de encerramento do trading
        """
        try:
            self._log_account_info()
            self._load_historical_data()
            self._stream_and_trade(end_hour, end_minute)
        except Exception as e:
            self.logger.error(f"Erro durante trading: {str(e)}")
            raise
        finally:
            self._close_all_positions()
    
    def _log_account_info(self):
        """Registra informações da conta."""
        account_info = mt5.account_info()
        if account_info is None:
            raise RuntimeError("Não foi possível obter informações da conta")
        
        self.logger.info("-" * 70)
        self.logger.info(f"Iniciando trading - {dt.datetime.now():%Y-%m-%d %H:%M:%S}")
        self.logger.info(f"Símbolo: {self.symbol} | Estratégia: {self.strategy_name}")
        self.logger.info(f"Balance: {account_info.balance:.2f} | "
                        f"Equity: {account_info.equity:.2f} | "
                        f"Profit: {account_info.profit:.2f}")
        self.logger.info("-" * 70)
    
    def _load_historical_data(self, bars: int = 280):
        """
        Carrega dados históricos para análise.
        
        Args:
            bars: Número de barras históricas a carregar
        """
        start = dt.datetime.now()
        rates = mt5.copy_rates_from(self.symbol, self.timeframe, start, bars)
        
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"Não foi possível obter dados para {self.symbol}")
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.rename(columns={'real_volume': 'volume'}, inplace=True)
        df.set_index('time', inplace=True)
        df.drop(df.tail(1).index, inplace=True)
        
        self.data = df
        self.logger.info(f"Dados históricos carregados: {len(df)} barras")
    
    def _stream_and_trade(self, end_hour: int, end_minute: int):
        """
        Faz o streaming de dados e executa trades em tempo real.
        
        Args:
            end_hour: Hora de encerramento
            end_minute: Minuto de encerramento
        """
        today = dt.datetime.now()
        end_time = dt.datetime(today.year, today.month, today.day, end_hour, end_minute, 0)
        
        self.logger.info(f"Trading ativo até {end_time:%H:%M:%S}")
        
        while dt.datetime.now() < end_time:
            try:
                # Obtém a barra mais recente
                rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 1, 1)
                
                if rates is None or len(rates) == 0:
                    self.logger.warning("Falha ao obter dados em tempo real")
                    time.sleep(1)
                    continue
                
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.rename(columns={'real_volume': 'volume'}, inplace=True)
                df.set_index('time', inplace=True)
                
                # Verifica se é uma nova barra
                if df.index[0] > self.data.index[-1]:
                    self._update_data(df)
                    self._process_strategy()
                    self._execute_trades()
                
                # Feedback visual
                print(".", end="", flush=True)
                
            except Exception as e:
                self.logger.error(f"Erro no streaming: {str(e)}")
            
            time.sleep(0.75)
        
        self.logger.info("Horário de trading encerrado")
    
    def _update_data(self, new_bar: pd.DataFrame):
        """Atualiza o dataframe com a nova barra."""
        self.data.loc[new_bar.index[0]] = [
            new_bar['open'].iloc[0],
            new_bar['high'].iloc[0],
            new_bar['low'].iloc[0],
            new_bar['close'].iloc[0],
            new_bar['tick_volume'].iloc[0],
            new_bar['spread'].iloc[0],
            new_bar['volume'].iloc[0]
        ]
    
    def _process_strategy(self):
        """Processa a estratégia e define posições."""
        df = self.data.copy()
        
        # Aplica a estratégia
        positions = self.strategy_func(df, **self.strategy_params)
        
        if isinstance(positions, pd.Series):
            df['position'] = positions
        else:
            df = positions
            if 'position' not in df.columns:
                raise ValueError("A estratégia deve retornar posições")
        
        # Força fechamento após 18h
        df.loc[df.index.to_series().dt.hour >= 18, 'position'] = 0
        df['position'] = df['position'].ffill().fillna(0)
        
        self.prepared_data = df
    
    def _execute_trades(self):
        """Executa trades baseado nas posições da estratégia."""
        new_position = self.prepared_data['position'].iloc[-1]
        
        # Só executa se houver mudança de posição
        if new_position == self.position:
            return
        
        # Fecha posição anterior se necessário
        if self.position != 0:
            self._close_position()
        
        # Abre nova posição
        if new_position != 0:
            self._open_position(new_position)
    
    def _open_position(self, position: int):
        """
        Abre uma nova posição.
        
        Args:
            position: 1 para compra, -1 para venda
        """
        order_type = mt5.ORDER_TYPE_BUY if position == 1 else mt5.ORDER_TYPE_SELL
        
        # Obtém preços atuais
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            self.logger.error("Não foi possível obter cotação atual")
            return
        
        # Define preços de entrada, TP e SL
        if position == 1:  # Compra
            price = tick.ask
            sl_price = price - self.sl
            tp_price = price + self.tp
            action_name = "COMPRA"
        else:  # Venda
            price = tick.bid
            sl_price = price + self.sl
            tp_price = price - self.tp
            action_name = "VENDA"
        
        # Monta requisição
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot_size,
            "type": order_type,
            "sl": sl_price,
            "tp": tp_price,
            "deviation": 10,
            "magic": self.magic_number,
            "comment": self.strategy_name,
            "type_time": mt5.ORDER_TIME_DAY,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }
        
        # Envia ordem
        result = mt5.order_send(request)
        
        if result is None:
            self.logger.error("Falha ao enviar ordem: resultado nulo")
            return
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Ordem rejeitada: {result.comment}")
            return
        
        # Atualiza estado
        self.position = position
        self.trades += 1
        self.quote_units = self.lot_size * price
        
        # Registra trade
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"{action_name} executada - {dt.datetime.now():%H:%M:%S}")
        self.logger.info(f"Preço: {price:.2f} | Volume: {self.lot_size}")
        self.logger.info(f"SL: {sl_price:.2f} | TP: {tp_price:.2f}")
        self.logger.info(f"{'='*50}\n")
        
        # Atualiza valores para cálculo de lucro
        self.trade_values.append(-self.quote_units if position == 1 else self.quote_units)
    
    def _close_position(self):
        """Fecha a posição atual."""
        positions = mt5.positions_get(symbol=self.symbol)
        
        for position in positions:
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY,
                "position": position.ticket,
                "deviation": 10,
                "magic": self.magic_number,
                "comment": f"Fechamento_{self.strategy_name}",
                "type_time": mt5.ORDER_TIME_DAY,
                "type_filling": mt5.ORDER_FILLING_RETURN,
            }
            
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"Posição fechada: {position.ticket}")
    
    def _close_all_positions(self):
        """Fecha todas as posições abertas do símbolo."""
        positions = mt5.positions_get(symbol=self.symbol)
        
        if positions:
            self.logger.info(f"Fechando {len(positions)} posições abertas")
            for position in positions:
                mt5.Close(self.symbol)
        
        self.position = 0