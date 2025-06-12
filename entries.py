
import numpy as np
import pandas as pd

def pattern_rsi_trend(df, length_rsi, rsi_low, rsi_high, allowed_hours=None, position_type="both"):
    """
    Estratégia de entrada baseada na variação percentual de preços e RSI inverso.
    
    Args:
        df (pandas.DataFrame): DataFrame com dados OHLC.
        allowed_hours (list): Lista de horas permitidas para operar.
        position_type (str): Tipo de posição permitida: "long", "short" ou "both".
        length_rsi (int): Período para cálculo do RSI.
        rsi_low (int): Nível de sobrevenda do RSI (para entrar vendido).
        rsi_high (int): Nível de sobrecompra do RSI (para entrar comprado).
        
    Returns:
        pandas.Series: Posições (-1=short, 0=neutro, 1=long)
    """
    
    df = df.copy()  # Para evitar SettingWithCopyWarning
    
    # Calcular a variação percentual
    df['pct_change'] = df['close'].pct_change().fillna(0)
    
    # Calcula o RSI
    df['rsi'] = df.ta.rsi(length= length_rsi).fillna(0)
    
    # Determinar posições com base no position_type e RSI (lógica inversa)
    if position_type == "long":
        df['position'] = np.where((df['pct_change'] > 0) & (df['rsi'] > rsi_high), 1, 0)
    elif position_type == "short":
        df['position'] = np.where((df['pct_change'] < 0) & (df['rsi'] < rsi_low), -1, 0)
    else:  # "both" ou qualquer outro valor padrão
        long_condition = (df['pct_change'] > 0) & (df['rsi'] > rsi_high)
        short_condition = (df['pct_change'] < 0) & (df['rsi'] < rsi_low)
        
        df['position'] = np.where(long_condition, 1, np.where(short_condition, -1, 0))
    
    # Restrição de horários
    if allowed_hours is not None:
        # Zera posição fora dos horários permitidos
        current_hours = df.index.to_series().dt.hour
        df.loc[~current_hours.isin(allowed_hours), 'position'] = 0
    
    return df['position']



def bb_trend(df, bb_length, std, allowed_hours=None, position_type="both"):
    """
    Estratégia baseada em Bandas de Bollinger.
    
    Args:
        df (pandas.DataFrame): DataFrame com dados OHLC.
        bb_length (int): Período para cálculo da média e desvio padrão.
        std (float): Número de desvios padrão para as bandas.
        allowed_hours (list): Horas que vamos executar a estratégia.
        position_type (str): Tipo de posições permitidas:
                            - "long": Apenas posições de compra (+1)
                            - "short": Apenas posições de venda (-1)
                            - "both": Ambas as posições (padrão)
        
    Returns:
        pandas.Series: Posições (-1=short, 0=neutro, 1=long)
    """
    df = df.copy()  # Para evitar SettingWithCopyWarning
    
    aux = df.ta.bbands(length=bb_length, std=std)
    df[f"BBL_{bb_length}_{std}"] = aux[f"BBL_{bb_length}_{std}"]
    df[f"BBU_{bb_length}_{std}"] = aux[f"BBU_{bb_length}_{std}"]
    df[f"BBM_{bb_length}_{std}"] = aux[f"BBM_{bb_length}_{std}"]    
    
    # Inicializar a coluna de posição com zeros
    df['position'] = 0
    
    # Calculando entradas (buy/sell)
    cond1 = (df.close < df[f"BBL_{bb_length}_{std}"]) & (df.close.shift(+1) >= df[f"BBL_{bb_length}_{std}"].shift(+1))
    cond2 = (df.close > df[f"BBU_{bb_length}_{std}"]) & (df.close.shift(+1) <= df[f"BBU_{bb_length}_{std}"].shift(+1))
    
    # Aplicar as posições de acordo com o parâmetro position_type
    if position_type.lower() == "both":
        df.loc[cond1, "position"] = +1
        df.loc[cond2, "position"] = -1
    elif position_type.lower() == "long":
        df.loc[cond2, "position"] = -1
    elif position_type.lower() == "short":
        df.loc[cond1, "position"] = +1
    else:
        raise ValueError("position_type deve ser 'long', 'short' ou 'both'")
    
    # Restrição de horários
    if allowed_hours is not None:
        # Zera posição fora dos horários permitidos
        current_hours = df.index.to_series().dt.hour
        df.loc[~current_hours.isin(allowed_hours), 'position'] = 0
    
    return df['position']