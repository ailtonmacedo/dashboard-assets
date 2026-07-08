# Dashboard de ETFs

Este repositório contém um script em Python para montar um painel técnico diário de ETFs negociados na B3, com foco em ativos como KDIF11, GOLD11, WRLD11, JURO11, FIXA11 e USDB11.

O projeto baixa dados de mercado, calcula sinais técnicos básicos e gera um relatório em HTML com uma visão rápida do cenário atual de cada ativo.

## O que o projeto faz

- Busca cotações diárias dos ETFs selecionados
- Calcula indicadores técnicos como:
  - RSI 14
  - Média móvel de 9 e 21 períodos
  - MACD
  - Bandas de Bollinger
  - Volume relativo
- Gera um painel visual em HTML com a classificação de cada ativo em COMPRA, VENDA ou NEUTRO
- Também oferece uma análise de correlação entre ativos e indicadores macroeconômicos básicos, como USD/BRL e Ibovespa

## Requisitos

Python 3.9+ e os seguintes pacotes:

```bash
pip install --upgrade yfinance pandas requests matplotlib seaborn
```

## Como usar

### Painel técnico principal

```bash
python dashboard_assets.py
```

Esse comando:

- baixa os dados
- calcula os sinais técnicos
- gera um relatório em HTML com o painel
- tenta abrir o resultado automaticamente no navegador

### Análise de correlação

```bash
python dashboard_assets.py --corr
```

Para exibir os gráficos de correlação em tela, use:

```bash
python dashboard_assets.py --corr --show
```

## Arquivos gerados

O script cria uma pasta com o padrão DD-MM-AAAA_HH-MM-SS para cada execução e salva os arquivos dentro dela. Os principais resultados são:

- painel_etfs.html
- asset_correlation.png
- rolling_asset_correlation.png

Exemplos de saídas podem ser encontrados no repositório em pastas com datas, como:

- 08-07-2026_09-00-00/painel_etfs.html
- 08-07-2026_10-57-30/painel_etfs.html

## Fontes de dados

O script tenta usar, em ordem:

1. Yahoo Finance via yfinance
2. Yahoo Finance via endpoint alternativo do ticker
3. brapi.dev, quando houver um token configurado em BRAPI_TOKEN

## Variável de ambiente opcional

Para usar a fonte brapi.dev com histórico mais completo, defina:

```bash
export BRAPI_TOKEN=seu_token
```

No Windows, use:

```bash
set BRAPI_TOKEN=seu_token
```

## Aviso importante

Esta ferramenta é educativa e não constitui recomendação de investimento. Os sinais técnicos devem ser usados com cautela e sempre em conjunto com análise macro e gestão de risco.
