# Deployer - Sistema de Deploy para Trading Algorítmico

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Um pacote Python profissional para criação e execução automatizada de estratégias de trading algorítmico com MetaTrader 5 utilizando o **modo hedge**, i.e. quando conseguimos abrir várias ordens simultâneas para o mesmo ativo.

## 📋 Características Principais

- ✅ **Sistema modular** de estratégias de trading
- ✅ **Configuração baseada em JSON** para fácil parametrização
- ✅ **Deploy automatizado** com suporte a múltiplas sessões
- ✅ **Sistema de logging completo** com arquivos detalhados
- ✅ **Gerenciamento automático** de posições e risk management
- ✅ **Suporte a múltiplos timeframes** (1min a 1 dia)
- ✅ **Parâmetros customizáveis por horário** de trading
- ✅ **Sistema automático de Take Profit e Stop Loss**
- ✅ **Magic Number configurável** para identificação de trades
- ✅ **Carregamento dinâmico** de estratégias personalizadas

## 🚀 Instalação

### Pré-requisitos

- Python 3.8 ou superior
- MetaTrader 5 instalado e configurado
- Conta demo ou real no MetaTrader 5

### Instalação do Pacote

```bash
# Clone o repositório
git clone https://github.com/RenatoPhys/deployer.git
cd deployer

# Crie um ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate

# Instale o pacote em modo desenvolvimento
pip install -e .
```

### Instalação das Dependências

```bash
pip install -r requirements.txt
```

## ⚙️ Configuração Inicial

### 1. Configurar Credenciais MT5

Crie um arquivo `.env` na raiz do projeto:

```env
MT5_LOGIN=seu_login_aqui
MT5_PASSWORD=sua_senha_aqui
MT5_SERVER=nome_do_servidor
MT5_PATH=C:/Program Files/MetaTrader 5/terminal64.exe
```

### 2. Configurar Estratégia

Edite o arquivo `examples/combined_strategy.json`:

```json
{
    "symbol": "WIN@N",
    "timeframe": "t5",
    "strategy": "pattern_rsi_trend",
    "hours": [11, 20],
    "hour_params": {
        "11": {
            "length_rsi": 9,
            "rsi_low": 36,
            "rsi_high": 76,
            "position_type": "short",
            "allowed_hours": [11],
            "tp": 1545,
            "sl": 310
        },
        "20": {
            "length_rsi": 8,
            "rsi_low": 39,
            "rsi_high": 67,
            "position_type": "both",
            "allowed_hours": [20],
            "tp": 530,
            "sl": 650
        }
    },
    "lote": 1,
    "magic_number": 2
}
```

## 📖 Uso Básico

### Execução Simplificada

A forma mais simples de usar o sistema:

```python
# examples/run_example.py
from deployer.deploy import deploy_from_config

# Executa trading para a hora atual usando configuração JSON
deploy_from_config("combined_strategy.json", strategies_file="entries.py")
```

### Modos de Execução

```python
from deployer.deploy import deploy_from_config

# 1. Trading apenas na hora atual
deploy_from_config("config.json", mode="current")

# 2. Trading em todas as horas configuradas do dia
deploy_from_config("config.json", mode="full_day")

# 3. Apenas deploy (sem executar trading)
trader = deploy_from_config("config.json", mode="deploy_only")
```

### Uso com AutoDeployer

```python
from deployer.deploy import AutoDeployer

# Inicializa o deployer
deployer = AutoDeployer(
    config_path="combined_strategy.json",
    strategies_file="entries.py"  # ou None para usar estratégias internas
)

# Executa trading para hora atual
deployer.run_current_session(end_hour=17, end_minute=54)

# Ou executa dia completo
deployer.run_full_day(end_hour=17, end_minute=54)
```

## 🔧 Criando Estratégias Personalizadas

### Arquivo de Estratégias Externo

Crie um arquivo `entries.py` no diretório do seu projeto:

```python
# entries.py
import numpy as np
import pandas as pd

def minha_estrategia_custom(df, param1=10, param2=20, position_type="both", **kwargs):
    """
    Estratégia personalizada de exemplo.
    
    Args:
        df: DataFrame com dados OHLC
        param1, param2: Parâmetros customizáveis
        position_type: "long", "short" ou "both"
        **kwargs: Outros parâmetros
    
    Returns:
        pd.Series: Posições (-1=short, 0=neutro, 1=long)
    """
    df = df.copy()
    
    # Sua lógica aqui
    ma_short = df['close'].rolling(param1).mean()
    ma_long = df['close'].rolling(param2).mean()
    
    # Sinais de entrada
    long_signal = ma_short > ma_long
    short_signal = ma_short < ma_long
    
    # Aplica position_type
    if position_type == "long":
        df['position'] = np.where(long_signal, 1, 0)
    elif position_type == "short":
        df['position'] = np.where(short_signal, -1, 0)
    else:  # "both"
        df['position'] = np.where(long_signal, 1, np.where(short_signal, -1, 0))
    
    return df['position']
```

### Configuração JSON para Estratégia Custom

```json
{
    "symbol": "WIN@N",
    "timeframe": "t5",
    "strategy": "minha_estrategia_custom",
    "hours": [9, 14],
    "hour_params": {
        "9": {
            "param1": 5,
            "param2": 20,
            "position_type": "long",
            "tp": 1000,
            "sl": 500
        },
        "14": {
            "param1": 10,
            "param2": 30,
            "position_type": "both",
            "tp": 800,
            "sl": 400
        }
    },
    "lote": 1,
    "magic_number": 123
}
```

## 📁 Estrutura do Projeto

```
deployer/
├── deployer/                    # Código principal do pacote
│   ├── __init__.py
│   ├── trader.py               # Classe AlgoTrader principal
│   ├── deploy.py               # Sistema de deploy automatizado
│   ├── strategies/             # Estratégias internas
│   │   ├── __init__.py
│   │   └── entries.py          # pattern_rsi_trend, bb_trend
│   ├── config/                 # Sistema de configuração
│   │   ├── __init__.py
│   │   └── loader.py           # ConfigManager, ConfigLoader
│   └── utils/                  # Utilitários
│       ├── __init__.py
│       └── logger.py           # Sistema de logging
├── examples/                   # Exemplos e configurações
│   ├── combined_strategy.json  # Configuração de exemplo
│   ├── run_example.py         # Script de execução simples
│   └── entries.py             # Suas estratégias personalizadas
├── configs/                    # Suas configurações (criar se necessário)
├── logs/                       # Logs automáticos (criado automaticamente)
├── .env                        # Suas credenciais MT5
├── requirements.txt
└── README.md
```

## 🎯 Configurações Avançadas

### Timeframes Suportados

| Código | Descrição |
|--------|-----------|
| `t1`   | 1 minuto  |
| `t5`   | 5 minutos |
| `t15`  | 15 minutos |
| `t30`  | 30 minutos |
| `h1`   | 1 hora    |
| `h4`   | 4 horas   |
| `d1`   | 1 dia     |

### Tipos de Posição

- **`long`**: Apenas operações de compra
- **`short`**: Apenas operações de venda  
- **`both`**: Compras e vendas (padrão)

### Magic Numbers

Cada configuração pode ter seu próprio `magic_number` para identificar trades:

```json
{
    "magic_number": 123,
    // ... resto da configuração
}
```

### Sistema de Logging

Os logs são organizados automaticamente:

- **Console**: Feedback em tempo real
- **Arquivo**: `logs/Trading_SYMBOL_STRATEGY_YYYYMMDD.log`
- **Estrutura**: Data/hora, nível, mensagem detalhada

## 🔍 Estratégias Internas Disponíveis

### 1. pattern_rsi_trend

Estratégia baseada em variação percentual e RSI inverso:

```json
{
    "strategy": "pattern_rsi_trend",
    "hour_params": {
        "9": {
            "length_rsi": 8,
            "rsi_low": 30,
            "rsi_high": 70,
            "position_type": "both"
        }
    }
}
```

### 2. bb_trend

Estratégia baseada em Bandas de Bollinger:

```json
{
    "strategy": "bb_trend", 
    "hour_params": {
        "10": {
            "bb_length": 20,
            "std": 2.0,
            "position_type": "both"
        }
    }
}
```

## 📊 Monitoramento e Métricas

O sistema registra automaticamente:

- ✅ Número total de trades executados
- ✅ Lucro/prejuízo detalhado por operação
- ✅ Horários de entrada e saída
- ✅ Parâmetros utilizados em cada trade
- ✅ Erros e diagnósticos detalhados

### Exemplo de Log

```
2024-01-15 14:30:25 - AlgoTrader_WIN@N - INFO - ✅ COMPRA EXECUTADA - 14:30:25
2024-01-15 14:30:25 - AlgoTrader_WIN@N - INFO - Ticket: 123456789
2024-01-15 14:30:25 - AlgoTrader_WIN@N - INFO - Preço: 135850 | Volume: 1.0
2024-01-15 14:30:25 - AlgoTrader_WIN@N - INFO - SL: 135540 | TP: 137395
```

## 🔧 Uso Programático Avançado

### Controle Manual Completo

```python
from deployer.trader import AlgoTrader
from deployer.strategies.entries import pattern_rsi_trend
import MetaTrader5 as mt5

# Configuração manual completa
trader = AlgoTrader(
    symbol="WIN@N",
    timeframe=mt5.TIMEFRAME_M5,
    strategy_name="minha_estrategia",
    strategy_func=pattern_rsi_trend,
    strategy_params={
        "length_rsi": 8,
        "rsi_low": 30,
        "rsi_high": 70,
        "position_type": "both"
    },
    tp=1000,
    sl=500,
    lot_size=1.0,
    magic_number=456
)

# Context manager para desconexão automática
with trader:
    trader.start_trading(end_hour=17, end_minute=30)
```

### Informações da Estratégia

```python
from deployer.deploy import AutoDeployer

deployer = AutoDeployer("config.json")

# Obter resumo completo
summary = deployer.get_strategy_summary()
print(f"Estratégia: {summary['strategy']}")
print(f"Horas de trading: {summary['trading_hours']}")
print(f"Magic Number: {summary['magic_number']}")
```

## 🐛 Solução de Problemas

### Erros Comuns de Conexão MT5

```python
# Verificar status da conexão
import MetaTrader5 as mt5

if not mt5.terminal_info():
    print("MT5 não está rodando")

if not mt5.account_info():
    print("Não conectado a uma conta")
```

### Erros de Estratégia

```bash
# Estratégia não encontrada
ValueError: Estratégia 'minha_func' não encontrada em entries.py.
Disponíveis: ['pattern_rsi_trend', 'bb_trend', 'minha_estrategia_custom']

# Solução: Verificar nome da função no arquivo entries.py
```

### Erros de Configuração

```bash
# Campo obrigatório ausente
ValueError: Campo obrigatório ausente: tp

# Solução: Adicionar tp e sl em hour_params
```

## ⚠️ Avisos Importantes de Segurança

- **🔴 SEMPRE TESTE EM CONTA DEMO PRIMEIRO**
- **🔴 Trading algorítmico envolve riscos significativos de perda**
- **🔴 Monitore sempre suas operações em tempo real**
- **🔴 Faça backtest completo antes de operar com dinheiro real**
- **🔴 Use risk management adequado (position sizing, stop loss)**

## 🤝 Contribuindo

1. Fork o projeto
2. Crie sua branch de feature (`git checkout -b feature/NovaFuncionalidade`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/NovaFuncionalidade`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 👤 Autor

**Renato Critelli**
- GitHub: [@RenatoPhys](https://github.com/RenatoPhys)
- Email: renato.critelli.ifusp@gmail.com

---

## 🚀 Exemplo Rápido de Início

```bash
# 1. Clone e instale
git clone https://github.com/RenatoPhys/deployer.git
cd deployer
pip install -e .

# 2. Configure .env com suas credenciais MT5

# 3. Execute o exemplo
cd examples
python run_example.py
```

**Pronto! Seu sistema de trading algorítmico está funcionando! 🎉**