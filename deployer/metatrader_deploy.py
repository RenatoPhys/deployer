import numpy as np
import warnings
import datetime as dt
import pandas as pd
import MetaTrader5 as mt5
import time
import pandas_ta as ta
import talib
from dotenv import load_dotenv
import os


## Fazendo o login no mt5

# Rico - demo
load_dotenv()
name = int(os.getenv("MT5_LOGIN"))
key = os.getenv("MT5_PASSWORD")
serv = os.getenv("MT5_SERVER")
path = os.getenv("MT5_PATH")


# establish MetaTrader 5 connection to a specified trading account
if not mt5.initialize(login = name, server = serv, password = key, path = path):
    print("initialize() failed, error code =",mt5.last_error())
    quit()

# display data on connection status, server name and trading account
print(mt5.terminal_info())
# display data on MetaTrader 5 version
print(mt5.version())

class TraderClass():
    
    '''
     Classe que inicializa, gerencia e reporta os trades.
    '''
    
    def __init__(self, symbol, timeframe, nome_estrategia, strategy_func=None, strategy_params=None, tp=None, sl=None):
        
        '''     
        Para inicialiar, precisamos dos seguintes inputs:
        symbol = símbolo do ativo (ex. GGBR4)
        timeframe = granularidade temporal
        strategy_func = função que define a estratégia de entrada/saída
        strategy_params = parâmetros específicos da estratégia
        tp = take profit (pode ser um valor fixo ou dicionário por hora)
        sl = stop loss (pode ser um valor fixo ou dicionário por hora)
        '''
        
        self.symbol = symbol # símbolo do ativo
        self.data = None  # dataframe com os dados de negociações
        self.nome_estrategia = nome_estrategia
        self.position = 0  # indicará se estamos comprados (=1), vendidos (=-1), ou neutros (=0)
        self.trades = 0  # número de trades
        self.trade_values = []
        self.quote_units = 0  # quotes
        self.timeframe = timeframe  # granularidade temporal
        self.strategy_func = strategy_func  # função da estratégia
        self.strategy_params = strategy_params or {}  # parâmetros da estratégia
        
        # Parâmetros de TP e SL
        self.tp = tp
        self.sl = sl
        
        # Validação da estratégia
        if self.strategy_func is None:
            self.strategy_func = self._default_strategy
            print("Aviso: Nenhuma estratégia fornecida. Usando estratégia padrão (RSI).")
    
    def start_trading(self):
        ''' função que irá começar o processo de algo trading  '''
        
        # Antes de começar o trade, pegamos algumas infos básicas na conta
        current_account_info = mt5.account_info()
        
        print("------------------------------------------------------------------")
        print("Date: ", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print(f"Balance: 123 BRL, \t" 
              f"Equity: 123 BRL, \t" 
              f"Profit: {current_account_info.profit} BRL")
        print("------------------------------------------------------------------")

        # Pegando os dados mais recentes (muitas estratégias precisam dos dados anteriores)
        self.get_most_recent()
        
        # streaming dos candlesticks -- essa função que irá fazer o gatilha dos trades
        self.stream_candles()
        
    def get_most_recent(self, number = 280):
        ''' Função para obter os dados mais recentes. 
            number = quantos candlesticks para trás queremos'''
    
        start = dt.datetime.today()
        df = mt5.copy_rates_from(self.symbol, self.timeframe, start, number)
        df=pd.DataFrame(df)
        df["time"] = pd.to_datetime(df['time'], unit='s')
        df.rename(columns = {'real_volume':'volume'}, inplace = True)
        df.set_index("time", inplace = True)
        df.drop(df.tail(1).index,inplace=True)
        
        self.data = df

        print(self.data.head())
        
    def stream_candles(self):
        ''' Função para fazer o live stream dos dados e realizar os trades '''
        
        # Iremos fazer os trades até 18:20
        yearc = dt.datetime.now().year
        monthc = dt.datetime.now().month
        dayc = dt.datetime.now().day
        
        while dt.datetime.now() < dt.datetime(yearc, monthc, dayc, 17, 54, 52, 0):
        
            start_pos = 1 # pegamos apenas um dados no live stream (o mais recente)
            count = 1

            df =  mt5.copy_rates_from_pos(self.symbol, self.timeframe, start_pos, count)
            df=pd.DataFrame(df)
            df["time"] = pd.to_datetime(df['time'], unit='s')
            df.rename(columns = {'real_volume':'volume'}, inplace = True)
            df.set_index("time", inplace = True)

            # print out
            print(".", end = "", flush = True) # just print something to get a feedback (everything OK) 

            # Se temos mais um ponto nos dados, é hora de fazer o trade! (ou não)
            if df.index[0] > self.data.index[-1]:
                # CORREÇÃO 1: Usar .iloc[] para acesso posicional
                self.data.loc[df.index[0]] = [
                    df['open'].iloc[0], 
                    df['high'].iloc[0], 
                    df['low'].iloc[0], 
                    df['close'].iloc[0], 
                    df['tick_volume'].iloc[0], 
                    df['spread'].iloc[0],
                    df['volume'].iloc[0]
                ]

                # prepare features and define strategy/trading positions whenever the latest bar is complete
                self.define_strategy()
                self.execute_trades()
            
            time.sleep(0.75)
            
        # Fechamos todas as posições após as 18h
        mt5.Close(self.symbol)
 
    def func_order(self, symbol, lot, position, tp, sl):
        '''função de ordens'''

        # **************************** Open a trade *****************************
        # Buy order Parameters
        if position == 1:
            type_trade = mt5.ORDER_TYPE_BUY
            # Open the trade
            request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "sl": mt5.symbol_info_tick(self.symbol).ask - sl,
            "tp": mt5.symbol_info_tick(self.symbol).ask + tp,
            'deviation': 0,
            "volume": lot,
            "type": type_trade,
            "magic": 2,
            "comment": self.nome_estrategia,
            "type_time": mt5.ORDER_TIME_DAY,
            "type_filling": mt5.ORDER_FILLING_RETURN,
            }
        
            # send a trading request
            result = mt5.order_send(request)

        # Sell order Parameters
        if position == -1:
            type_trade = mt5.ORDER_TYPE_SELL
            # Open the trade
            request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "sl": mt5.symbol_info_tick(self.symbol).bid + sl,
            "tp": mt5.symbol_info_tick(self.symbol).bid - tp,
            'deviation': 0,
            "volume": lot,
            "type": type_trade,
            "magic": 2,
            "comment": self.nome_estrategia,
            "type_time": mt5.ORDER_TIME_DAY,
            "type_filling": mt5.ORDER_FILLING_RETURN,
            }
        
            # send a trading request
            result = mt5.order_send(request)
            
        return result
    

    
    def define_strategy(self):
        ''' Função que aplica a estratégia modular '''
        
        df = self.data.copy()
        
        # CORREÇÃO 2: A função de estratégia retorna uma Series, não DataFrame
        positions = self.strategy_func(df, **self.strategy_params)
        
        # Verifica se retornou uma Series (posições)
        if isinstance(positions, pd.Series):
            # Adiciona as posições ao DataFrame
            df['position'] = positions
        else:
            # Se a função retornar um DataFrame, usa diretamente
            df = positions
            # Garantimos que sempre temos uma coluna 'position'
            if 'position' not in df.columns:
                raise ValueError("A função de estratégia deve retornar um DataFrame com a coluna 'position' ou uma Series com as posições")
        
        # We exit all our positions in the end of the trading's time
        df.loc[(df.index.to_series().dt.hour >= 18), 'position'] = 0
        df['position'] = df['position'].ffill()
        
        self.prepared_data = df.copy()
    
    def _default_strategy(self, df, rsi_length=9, rsi_oversold=34, rsi_overbought=66, trading_hours=[16, 17]):
        '''Estratégia padrão baseada em RSI (a mesma que estava no código original)'''
        
        # Parametros necessarios
        df['close_lag_1'] = df['close'].shift()        
        df["rsi"] = df.ta.rsi(length=rsi_length)
       
        # Posições de compra geral
        cond1 = (df.close <= df.close_lag_1) & (df.rsi <= rsi_oversold) & (df.index.hour.isin(trading_hours))
        cond2 = (df.close > df.close_lag_1) & (df.rsi >= rsi_overbought) & (df.index.hour.isin(trading_hours))
        
        df['position'] = 0
        df.loc[cond1, "position"] = -1
        df.loc[cond2, "position"] = +1
        
        return df
    
    def execute_trades(self): 
        ''' Função para executar os trades '''
        
        # Definindo posiçao
        position_new = self.prepared_data["position"].iloc[-1]
        
        # Usa os valores de TP e SL passados como parâmetros
        tp_value = self.tp 
        sl_value = self.sl
        
        # Dicionário de quantidade de contrato por hora
        self.units = 1.0
        
        # Compra/Venda/Neutro
        if position_new == 1:
            order = self.func_order(self.symbol, self.units, position_new, tp_value, sl_value)
            self.report_trade(order, "GOING LONG")  
            self.quote_units = self.units * 1 * order.price
            self.position = 1
        elif position_new == -1: 
            order = self.func_order(self.symbol, self.units, position_new, tp_value, sl_value)
            self.report_trade(order, "GOING SHORT")
            self.quote_units = self.units * 1 * order.price
            self.position = -1
        elif position_new == 0: 
            self.position = 0
    
    def report_trade(self, order, going): 
        
        time = dt.datetime.now()
        
        # calculate trading profits
        side = order.request.type # buy or sell
        self.trades += 1
        if side == 0: # buy
            self.trade_values.append(-self.quote_units)
        elif side == 1: #sell
            self.trade_values.append(self.quote_units) 
        
        if self.trades % 2 == 0:
            real_profit = round(np.sum(self.trade_values[-2:]), 3) 
            self.cum_profits = round(np.sum(self.trade_values), 3)
        else: 
            real_profit = 0
            self.cum_profits = round(np.sum(self.trade_values[:-1]), 3)
        
        print("\n" + 100* "-")
        print("{} | {}".format(time, going))
        print("{} | units = {} | Price = {}".format(time, self.units, order.price))
        print("{} | Profit = {} | CumProfits = {} ".format(time, real_profit, self.cum_profits))
        print(100 * "-" + "\n")