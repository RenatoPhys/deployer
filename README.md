# Deployer - Algo Trading Deployment System

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Um pacote Python profissional para criação e execução de scripts de deploy para trading algorítmico com MetaTrader 5.

## 📋 Características

- ✅ Sistema modular de estratégias de trading
- ✅ Configuração baseada em JSON
- ✅ Sistema de logging completo
- ✅ Gerenciamento automático de posições
- ✅ Suporte a múltiplos timeframes
- ✅ Parâmetros customizáveis por horário
- ✅ Sistema de Take Profit e Stop Loss automático

## 🚀 Instalação

### Pré-requisitos

- Python 3.8 ou superior
- MetaTrader 5 instalado
- Conta demo ou real no MetaTrader 5

### Instalação via pip (desenvolvimento)

```bash
# Clone o repositório
git clone https://github.com/seu_usuario/deployer.git
cd deployer

# Crie um ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate

# Instale o pacote em modo desenvolvimento
pip install -e .
```

### Instalação das dependências

```bash
pip install -r requirements.txt
```

## ⚙️ Configuração

### 1. Configurar credenciais MT5

Crie um arquivo `.env` na raiz do projeto:

```env
MT5_LOGIN=seu_login_aqui
MT5_PASSWORD=sua_senha_aqui
MT5_SERVER=nome_do_servidor
MT5_PATH=C:/Program Files/MetaTrader 5/terminal64.exe
```

### 2. Configurar estratégia

Edite o arquivo `examples/combined_strategy.json` com seus parâmetros:

```json
{
    "symbol": "WINM25",
    "timeframe": "t5",
    "strategy": "pattern_rsi_trend",
    "hours": [9, 10, 11, 12, 13, 14, 15, 16, 17],
    "hour_params": {
        "9": {
            "length_rsi": 8,
            "rsi_low": 50,
            "rsi_high": 50,
            "position_type": "short",
            "tp": 1445,
            "sl": 200
        }
    }
}
```

## 📖 Uso Básico

### Executar o trading automatizado

```bash
cd examples
python run_example.py
```

### Criar uma estratégia customizada

```python
# deployer/strategies/my_strategy.py
import numpy as np
import pandas as pd

def my_custom_strategy(df, param1=10, param2=20, **kwargs):
    """
    Sua estratégia customizada aqui.
    
    Returns:
        pd.Series: Série com posições (-1=short, 0=neutro, 1=long)
    """
    # Implementar lógica da estratégia
    positions = pd.Series(0, index=df.index)
    
    # Exemplo: compra quando preço cruza média móvel
    ma = df['close'].rolling(param1).mean()
    positions[df['close'] > ma] = 1
    positions[df['close'] < ma] = -1
    
    return positions
```

### Uso programático

```python
from deployer.trader import AlgoTrader
from deployer.config.loader import ConfigManager
from deployer.strategies.entries import pattern_rsi_trend
import MetaTrader5 as mt5

# Carregar configuração
config = ConfigManager("config.json")

# Criar trader
trader = AlgoTrader(
    symbol="WINM25",
    timeframe=mt5.TIMEFRAME_M5,
    strategy_name="minha_estrategia",
    strategy_func=pattern_rsi_trend,
    strategy_params={"length_rsi": 8, "rsi_low": 30},
    tp=1000,
    sl=500,
    lot_size=1.0
)

# Iniciar trading
trader.start_trading()
```

## 📁 Estrutura do Projeto

```
deployer/
├── deployer/              # Código principal do pacote
│   ├── __init__.py
│   ├── trader.py          # Classe principal AlgoTrader
│   ├── strategies/        # Estratégias de trading
│   │   ├── __init__.py
│   │   └── entries.py
│   ├── config/           # Módulo de configuração (código Python)
│   │   ├── __init__.py
│   │   └── loader.py     # Carregador de configurações
│   └── utils/            # Utilitários
│       ├── __init__.py
│       └── logger.py
├── examples/             # Exemplos de uso e configurações
│   ├── combined_strategy.json    # Exemplo de configuração
│   ├── run_example.py           # Script de exemplo
│   └── create_config.py         # Criar nova configuração
├── configs/              # Suas configurações pessoais (opcional)
│   └── my_strategy.json
├── logs/                 # Arquivos de log (criado automaticamente)
├── tests/                # Testes unitários
├── .env                  # Suas credenciais (não committar!)
├── .env.example          # Exemplo de configuração
├── requirements.txt      # Dependências
├── setup.py             # Configuração do pacote
└── README.md            # Este arquivo
```

### Organização dos Arquivos

- **`deployer/`**: Código fonte do pacote
- **`examples/`**: Exemplos e templates de configuração
- **`configs/`**: Suas configurações pessoais (crie esta pasta para suas estratégias)
- **`logs/`**: Logs de execução (criado automaticamente)

## 🔧 Configurações Avançadas

### Timeframes Suportados

- `t1`: 1 minuto
- `t5`: 5 minutos
- `t15`: 15 minutos
- `t30`: 30 minutos
- `h1`: 1 hora
- `h4`: 4 horas
- `d1`: 1 dia

### Tipos de Posição

- `long`: Apenas compras
- `short`: Apenas vendas
- `both`: Compras e vendas

### Sistema de Logging

Os logs são salvos automaticamente em `logs/` com o formato:
- Console: Informações em tempo real
- Arquivo: `logs/Trading_SYMBOL_STRATEGY_YYYYMMDD.log`

## 🐛 Solução de Problemas

### Erro de conexão MT5

```python
# Verificar se MT5 está aberto
# Verificar credenciais no .env
# Verificar caminho do terminal
```

### Estratégia não encontrada

```python
# Verificar nome da função
# Verificar se está importada corretamente
# Verificar caminho do módulo
```

## 📊 Métricas e Performance

O sistema registra automaticamente:
- Número de trades executados
- Lucro/prejuízo por operação
- Taxa de acerto
- Drawdown máximo

## 🤝 Contribuindo

1. Fork o projeto
2. Crie sua branch (`git checkout -b feature/NovaFuncionalidade`)
3. Commit suas mudanças (`git commit -m 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/NovaFuncionalidade`)
5. Abra um Pull Request

## ⚠️ Avisos Importantes

- **USE CONTA DEMO PRIMEIRO**: Sempre teste suas estratégias em conta demo
- **RISCO**: Trading algorítmico envolve riscos significativos
- **MONITORAMENTO**: Sempre monitore suas operações
- **BACKTEST**: Faça backtest antes de usar em conta real

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 👤 Autor

Renato - [GitHub](https://github.com/seu_usuario)

## 🙏 Agradecimentos

- MetaTrader 5 pela plataforma
- Comunidade Python por bibliotecas excelentes
- Todos os contribuidores do projeto