"""
Módulo principal do trader para execução de estratégias de algo trading.
Versão com diagnóstico melhorado para erros de ordem.
"""

import numpy as np
import datetime as dt
import pandas as pd
import MetaTrader5 as mt5
import time
import os
from pathlib import Path
from typing import Callable, Dict, Optional, Union
from dotenv import load_dotenv
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
        magic_number: int = 2,
        auto_connect: bool = True,
        env_path: Optional[str] = None
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
        self.mt5_connected = False
        self.symbol_info = None
        
        # Logger
        self.logger = setup_logger(f"AlgoTrader_{symbol}")
        
        # Carrega variáveis de ambiente
        self._load_environment(env_path)
        
        # Conecta automaticamente se solicitado
        if auto_connect:
            self.connect_mt5()
            self._initialize_symbol()
        
        # Validações
        self._validate_parameters()
    
    def _load_environment(self, env_path: Optional[str] = None):
        """
        Carrega variáveis de ambiente do arquivo .env.
        
        Args:
            env_path: Caminho específico para o .env (opcional)
        """
        if env_path and Path(env_path).exists():
            load_dotenv(env_path)
            self.logger.info(f"Variáveis carregadas de: {env_path}")
            return
        
        # Procura .env em locais comuns
        search_paths = [
            Path.cwd(),                                    # Diretório atual
            Path(__file__).parent,                         # Diretório do módulo
            Path(__file__).parent.parent,                  # Diretório pai do projeto
            Path(__file__).parent.parent.parent,           # Diretório raiz
            Path.home(),                                   # Diretório home
        ]
        
        for path in search_paths:
            env_file = path / ".env"
            if env_file.exists():
                load_dotenv(env_file)
                self.logger.info(f"Arquivo .env encontrado em: {env_file}")
                return
        
        self.logger.warning("Arquivo .env não encontrado nos locais padrão")
    
    def connect_mt5(self, 
                   login: Optional[int] = None,
                   password: Optional[str] = None, 
                   server: Optional[str] = None,
                   path: Optional[str] = None) -> bool:
        """
        Estabelece conexão com o MetaTrader 5.
        
        Args:
            login: Login da conta (se None, usa MT5_LOGIN do .env)
            password: Senha da conta (se None, usa MT5_PASSWORD do .env)
            server: Servidor (se None, usa MT5_SERVER do .env)
            path: Caminho do MT5 (se None, usa MT5_PATH do .env)
            
        Returns:
            True se conectado com sucesso
            
        Raises:
            ValueError: Se credenciais estão ausentes
            RuntimeError: Se falha na conexão
        """
        if self.mt5_connected:
            self.logger.info("MT5 já está conectado")
            return True
        
        # Usa parâmetros fornecidos ou variáveis de ambiente
        login = login or os.getenv("MT5_LOGIN")
        password = password or os.getenv("MT5_PASSWORD")
        server = server or os.getenv("MT5_SERVER")
        path = path or os.getenv("MT5_PATH")
        
        # Validações
        if not all([login, password, server]):
            missing = []
            if not login: missing.append("MT5_LOGIN")
            if not password: missing.append("MT5_PASSWORD") 
            if not server: missing.append("MT5_SERVER")
            
            raise ValueError(
                f"Credenciais MT5 ausentes: {', '.join(missing)}. "
                "Configure no arquivo .env ou passe como parâmetros."
            )
        
        try:
            login = int(login)
        except (ValueError, TypeError):
            raise ValueError("Login deve ser um número inteiro")
        
        # Verifica se o executável existe
        if path and not Path(path).exists():
            self.logger.warning(f"Executável MT5 não encontrado em: {path}")
            self.logger.info("Tentando inicializar sem caminho específico...")
            path = None
        
        # Inicializa MT5
        self.logger.info(f"Conectando ao MT5 - Login: {login} | Servidor: {server}")
        
        try:
            if path:
                success = mt5.initialize(path=path, login=login, password=password, server=server)
            else:
                success = mt5.initialize(login=login, password=password, server=server)
            
            if not success:
                error = mt5.last_error()
                raise RuntimeError(
                    f"Falha ao conectar MT5 - Código: {error[0]}, Mensagem: {error[1]}"
                )
            
            # Verifica informações da conta
            account_info = mt5.account_info()
            if account_info is None:
                mt5.shutdown()
                raise RuntimeError("Não foi possível obter informações da conta após conexão")
            
            self.mt5_connected = True
            self.logger.info(f"✅ MT5 conectado com sucesso!")
            self.logger.info(f"Conta: {account_info.login} | "
                           f"Servidor: {account_info.server} | "
                           f"Saldo: {account_info.balance:.2f}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Erro ao conectar MT5: {str(e)}")
            raise
    
    def _initialize_symbol(self):
        """Inicializa e valida o símbolo no MT5."""
        # Verifica se o símbolo existe
        symbols = mt5.symbols_get()
        if not any(s.name == self.symbol for s in symbols):
            available = [s.name for s in symbols if self.symbol[:3] in s.name][:5]
            raise ValueError(
                f"Símbolo '{self.symbol}' não encontrado. "
                f"Símbolos similares: {available}"
            )
        
        # Seleciona o símbolo
        if not mt5.symbol_select(self.symbol, True):
            raise RuntimeError(f"Não foi possível selecionar o símbolo {self.symbol}")
        
        # Obtém informações do símbolo
        self.symbol_info = mt5.symbol_info(self.symbol)
        if self.symbol_info is None:
            raise RuntimeError(f"Não foi possível obter informações do símbolo {self.symbol}")
        
        # Log das informações importantes
        self.logger.info(f"Símbolo {self.symbol} inicializado:")
        self.logger.info(f"  - Spread atual: {self.symbol_info.spread}")
        self.logger.info(f"  - Volume mín: {self.symbol_info.volume_min}")
        self.logger.info(f"  - Volume máx: {self.symbol_info.volume_max}")
        self.logger.info(f"  - Step volume: {self.symbol_info.volume_step}")
        # Converte trade_mode para string legível
        trade_modes = {
            mt5.SYMBOL_TRADE_MODE_DISABLED: "Desabilitado",
            mt5.SYMBOL_TRADE_MODE_LONGONLY: "Apenas Compra",
            mt5.SYMBOL_TRADE_MODE_SHORTONLY: "Apenas Venda",
            mt5.SYMBOL_TRADE_MODE_CLOSEONLY: "Apenas Fechamento",
            mt5.SYMBOL_TRADE_MODE_FULL: "Completo"
        }
        trade_mode_str = trade_modes.get(self.symbol_info.trade_mode, "Desconhecido")
        self.logger.info(f"  - Trade mode: {trade_mode_str}")
        
        # Validações importantes
        if not self.symbol_info.visible:
            self.logger.warning("Símbolo não está visível no Market Watch!")
        
        if self.symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
            raise RuntimeError(f"Trading desabilitado para {self.symbol}")
    
    def disconnect_mt5(self):
        """Desconecta do MetaTrader 5."""
        if self.mt5_connected:
            mt5.shutdown()
            self.mt5_connected = False
            self.logger.info("MT5 desconectado")
    
    def _validate_parameters(self):
        """Valida os parâmetros de inicialização."""
        if self.strategy_func is None:
            raise ValueError("Uma função de estratégia deve ser fornecida.")
        
        if self.tp is None or self.sl is None:
            raise ValueError("Take Profit (tp) e Stop Loss (sl) devem ser definidos.")
        
        if self.tp <= 0 or self.sl <= 0:
            raise ValueError("Take Profit e Stop Loss devem ser valores positivos.")
        
        if not self.mt5_connected:
            raise RuntimeError(
                "MT5 não está conectado. Use connect_mt5() ou auto_connect=True"
            )
        
        # Valida volume
        if self.symbol_info:
            if self.lot_size < self.symbol_info.volume_min:
                self.logger.warning(
                    f"Volume {self.lot_size} menor que mínimo {self.symbol_info.volume_min}. "
                    f"Ajustando para mínimo."
                )
                self.lot_size = self.symbol_info.volume_min
            elif self.lot_size > self.symbol_info.volume_max:
                self.logger.warning(
                    f"Volume {self.lot_size} maior que máximo {self.symbol_info.volume_max}. "
                    f"Ajustando para máximo."
                )
                self.lot_size = self.symbol_info.volume_max
    
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
                       
        # Abre nova posição
        if new_position != 0:
            self._open_position(new_position)
    
    def _get_filling_type(self):
        """Determina o tipo de preenchimento correto para o símbolo."""
        if self.symbol_info is None:
            self.logger.warning("symbol_info é None, usando ORDER_FILLING_RETURN")
            return mt5.ORDER_FILLING_RETURN
        
        filling = self.symbol_info.filling_mode
        self.logger.debug(f"Filling mode do símbolo: {filling}")
        
        # Para mini-índice geralmente é ORDER_FILLING_RETURN (2)
        # Se o filling_mode for 0 ou inválido, usa RETURN como padrão
        if filling == 0:
            self.logger.info("Filling mode é 0, usando ORDER_FILLING_RETURN como padrão")
            return mt5.ORDER_FILLING_RETURN
        
        # Verifica os modos suportados usando valores numéricos
        # FOK = 1, IOC = 2, RETURN = 3
        if filling & 1:  # Fill or Kill
            return mt5.ORDER_FILLING_FOK
        elif filling & 2:  # Immediate or Cancel
            return mt5.ORDER_FILLING_IOC
        else:
            return mt5.ORDER_FILLING_RETURN
    
    def _open_position(self, position: int):
        """
        Abre uma nova posição com diagnóstico detalhado.
        
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
        
        # Ajusta precisão dos preços
        digits = self.symbol_info.digits
        price = round(price, digits)
        sl_price = round(sl_price, digits)
        tp_price = round(tp_price, digits)
        
        # Ajusta volume para step correto
        volume_step = self.symbol_info.volume_step
        adjusted_volume = round(self.lot_size / volume_step) * volume_step
        
        # Monta requisição
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": adjusted_volume,
            "type": order_type,
            "price": price,
            "sl": sl_price,
            "tp": tp_price,
            "deviation": 20,
            "magic": self.magic_number,
            "comment": self.strategy_name,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._get_filling_type(),
        }
        
        # Log detalhado antes de enviar
        self.logger.info(f"Preparando ordem {action_name}:")
        self.logger.info(f"  - Preço: {price}")
        self.logger.info(f"  - Volume: {adjusted_volume} (ajustado de {self.lot_size})")
        self.logger.info(f"  - SL: {sl_price} ({self.sl} pontos)")
        self.logger.info(f"  - TP: {tp_price} ({self.tp} pontos)")
        self.logger.info(f"  - Filling: {request['type_filling']}")
        
        # Verifica se pode enviar
        check_result = mt5.order_check(request)
        if check_result is None:
            self.logger.error("order_check retornou None - possível problema de conexão")
            return
        
        # Retcode 0 significa OK, pode prosseguir
        if check_result.retcode != 0:
            self.logger.error(f"Ordem rejeitada no check: {check_result.comment}")
            self.logger.error(f"Retcode: {check_result.retcode}")
            
            # Diagnóstico adicional
            if check_result.retcode == 10030:
                self.logger.error("TRADE_RETCODE_INVALID_FILL - Tipo de preenchimento inválido")
            elif check_result.retcode == 10015:
                self.logger.error("TRADE_RETCODE_INVALID_PRICE - Preço inválido")
            elif check_result.retcode == 10014:
                self.logger.error("TRADE_RETCODE_INVALID_VOLUME - Volume inválido")
            
            return
        
        # Envia ordem
        result = mt5.order_send(request)
        
        if result is None:
            self.logger.error("order_send retornou None. Possíveis causas:")
            self.logger.error("1. Símbolo não selecionado (use mt5.symbol_select)")
            self.logger.error("2. Trading desabilitado para o símbolo")
            self.logger.error("3. Mercado fechado")
            self.logger.error("4. Conexão perdida")
            
            # Tenta diagnóstico adicional
            last_error = mt5.last_error()
            if last_error:
                self.logger.error(f"Último erro MT5: {last_error}")
            
            return
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            self.logger.error(f"Ordem rejeitada: {result.comment}")
            self.logger.error(f"Retcode: {result.retcode}")
            
            # Diagnóstico adicional baseado no retcode
            error_codes = {
                10004: "TRADE_RETCODE_REQUOTE - Requote, preços mudaram",
                10006: "TRADE_RETCODE_REJECT - Ordem rejeitada",
                10007: "TRADE_RETCODE_CANCEL - Ordem cancelada pelo trader",
                10008: "TRADE_RETCODE_PLACED - Ordem colocada",
                10009: "TRADE_RETCODE_DONE - Ordem executada",
                10010: "TRADE_RETCODE_DONE_PARTIAL - Ordem parcialmente executada",
                10011: "TRADE_RETCODE_ERROR - Erro no processamento",
                10012: "TRADE_RETCODE_TIMEOUT - Timeout na execução",
                10013: "TRADE_RETCODE_INVALID - Requisição inválida",
                10014: "TRADE_RETCODE_INVALID_VOLUME - Volume inválido",
                10015: "TRADE_RETCODE_INVALID_PRICE - Preço inválido",
                10016: "TRADE_RETCODE_INVALID_STOPS - Stops inválidos",
                10017: "TRADE_RETCODE_TRADE_DISABLED - Trading desabilitado",
                10018: "TRADE_RETCODE_MARKET_CLOSED - Mercado fechado",
                10019: "TRADE_RETCODE_NO_MONEY - Fundos insuficientes",
                10020: "TRADE_RETCODE_PRICE_CHANGED - Preço mudou",
                10021: "TRADE_RETCODE_PRICE_OFF - Sem cotações",
                10022: "TRADE_RETCODE_INVALID_EXPIRATION - Expiração inválida",
                10023: "TRADE_RETCODE_ORDER_CHANGED - Ordem mudou",
                10024: "TRADE_RETCODE_TOO_MANY_REQUESTS - Muitas requisições",
                10025: "TRADE_RETCODE_NO_CHANGES - Sem mudanças",
                10026: "TRADE_RETCODE_SERVER_DISABLES_AT - Autotrading desabilitado pelo servidor",
                10027: "TRADE_RETCODE_CLIENT_DISABLES_AT - Autotrading desabilitado pelo cliente",
                10028: "TRADE_RETCODE_LOCKED - Requisição bloqueada",
                10029: "TRADE_RETCODE_FROZEN - Ordem ou posição congelada",
                10030: "TRADE_RETCODE_INVALID_FILL - Tipo de preenchimento inválido"
            }
            
            if result.retcode in error_codes:
                self.logger.error(f"Diagnóstico: {error_codes[result.retcode]}")
            
            return
        
        # Atualiza estado
        self.position = position
        self.trades += 1
        self.quote_units = adjusted_volume * price
        
        # Registra trade com sucesso
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"✅ {action_name} EXECUTADA - {dt.datetime.now():%H:%M:%S}")
        self.logger.info(f"Ticket: {result.order}")
        self.logger.info(f"Preço: {price:.{digits}f} | Volume: {adjusted_volume}")
        self.logger.info(f"SL: {sl_price:.{digits}f} | TP: {tp_price:.{digits}f}")
        self.logger.info(f"{'='*50}\n")
        
        # Atualiza valores para cálculo de lucro
        self.trade_values.append(-self.quote_units if position == 1 else self.quote_units)
    
    def _close_position(self):
        """Fecha a posição atual."""
        positions = mt5.positions_get(symbol=self.symbol)
        
        for position in positions:
            close_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": position.volume,
                "type": close_type,
                "position": position.ticket,
                "deviation": 20,
                "magic": self.magic_number,
                "comment": f"Fechamento_{self.strategy_name}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_filling_type(),
            }
            
            # Adiciona preço para alguns tipos de filling
            if request["type_filling"] == mt5.ORDER_FILLING_RETURN:
                tick = mt5.symbol_info_tick(self.symbol)
                if tick:
                    request["price"] = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
            
            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"✅ Posição fechada: {position.ticket}")
            else:
                self.logger.error(f"Erro ao fechar posição: {result.comment if result else 'None'}")
    
    def _close_all_positions(self):
        """Fecha todas as posições abertas do símbolo."""
        positions = mt5.positions_get(symbol=self.symbol)
        
        if positions:
            self.logger.info(f"Fechando {len(positions)} posições abertas")
            for position in positions:
                # Usa método simplificado primeiro
                if not mt5.Close(self.symbol):
                    # Se falhar, tenta método detalhado
                    self._close_position()
        
        self.position = 0
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - desconecta automaticamente."""
        self.disconnect_mt5()