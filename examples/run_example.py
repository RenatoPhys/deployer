"""
Exemplo de execução do sistema de trading automatizado.
"""

from deployer.deploy import deploy_from_config

# SÓ ISSO! Pega tudo do JSON automaticamente
# Usa um arquivo específico
deploy_from_config("combined_strategy.json", strategies_file="entries.py")