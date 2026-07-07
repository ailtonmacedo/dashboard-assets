"""
Painel diário de sinais técnicos para ETFs da B3.
Ativos: KDIF11, GOLD11, WRLD11, JURO11, FIXA11, USDB11

Requisitos:  pip install --upgrade yfinance pandas requests
Uso:         python dashboard_assets.py           (painel técnico diário)
             python dashboard_assets.py --corr    (+ análise de correlação)

Fontes de dados (em ordem de tentativa):
  1. Yahoo Finance via yf.download
  2. Yahoo Finance via Ticker().history (endpoint alternativo)
  3. brapi.dev (API brasileira; defina a variável de ambiente
     BRAPI_TOKEN com um token gratuito de https://brapi.dev
     para liberar o histórico de 3 meses)

AVISO: ferramenta educativa. Não constitui recomendação de investimento.
"""

import os
import sys

import pandas as pd
import requests
import yfinance as yf

TICKERS = ["KDIF11", "GOLD11", "WRLD11", "JURO11", "FIXA11", "USDB11"]
BRAPI_TOKEN = os.environ.get("BRAPI_TOKEN", "")

CONTEXTO = {"USD/BRL": "BRL=X", "IBOV": "^BVSP"}

PARES_ROLLING = [
    ("GOLD11", "IBOV"),
    ("WRLD11", "USD/BRL"),
    ("USDB11", "USD/BRL"),
    ("FIXA11", "IBOV"),
]
JANELA_ROLLING = 60


def checar_versao_yfinance():
    versao = getattr(yf, "__version__", "desconhecida")
    print(f"yfinance {versao}")
    partes = versao.split(".")
    try:
        if int(partes[0]) == 0 and int(partes[1]) < 2:
            print(">> Versão antiga detectada. Rode: pip install --upgrade yfinance")
    except (ValueError, IndexError):
        pass


def baixar_yahoo(ticker: str) -> pd.DataFrame:
    df = yf.download(
        f"{ticker}.SA", period="6mo", interval="1d", progress=False, auto_adjust=True
    )
    if df is not None and not df.empty:
        return df
    df = yf.Ticker(f"{ticker}.SA").history(period="6mo", auto_adjust=True)
    return df if df is not None else pd.DataFrame()


def baixar_brapi(ticker: str) -> pd.DataFrame:
    url = f"https://brapi.dev/api/quote/{ticker}"
    params = {"range": "3mo", "interval": "1d"}
    if BRAPI_TOKEN:
        params["token"] = BRAPI_TOKEN
    try:
        r = requests.get(url, params=params, timeout=15)
        dados = r.json()["results"][0].get("historicalDataPrice", [])
    except Exception:
        return pd.DataFrame()
    if not dados:
        return pd.DataFrame()
    df = pd.DataFrame(dados)
    df["date"] = pd.to_datetime(df["date"], unit="s")
    df = df.set_index("date").rename(columns={"close": "Close", "volume": "Volume"})
    return df[["Close", "Volume"]]


def obter_dados(ticker):
    df = baixar_yahoo(ticker)
    if not df.empty and len(df) >= 30:
        return df, "yahoo"
    df = baixar_brapi(ticker)
    if not df.empty and len(df) >= 30:
        return df, "brapi"
    return pd.DataFrame(), "-"


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100 - (100 / (1 + gain / loss))


def analisar(ticker: str) -> dict:
    df, fonte = obter_dados(ticker)
    if df.empty:
        return {"Ativo": ticker, "Fonte": "FALHOU", "Sinal técnico": "sem dados"}
    close = df["Close"].squeeze().astype(float)
    vol = (
        df["Volume"].squeeze().astype(float)
        if "Volume" in df
        else pd.Series(dtype=float)
    )

    mm9, mm21 = close.rolling(9).mean(), close.rolling(21).mean()
    rsi14 = rsi(close).iloc[-1]

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_hist = (ema12 - ema26 - (ema12 - ema26).ewm(span=9, adjust=False).mean()).iloc[
        -1
    ]

    mm20 = close.rolling(20).mean()
    desvio = close.rolling(20).std()
    banda_sup = (mm20 + 2 * desvio).iloc[-1]
    banda_inf = (mm20 - 2 * desvio).iloc[-1]
    preco = close.iloc[-1]

    vol_rel = float("nan")
    if len(vol) >= 21 and vol.rolling(21).mean().iloc[-1] > 0:
        vol_rel = vol.iloc[-1] / vol.rolling(21).mean().iloc[-1]

    pontos = 0
    pontos += 1 if mm9.iloc[-1] > mm21.iloc[-1] else -1
    pontos += 1 if macd_hist > 0 else -1
    if rsi14 < 30:
        pontos += 1
    elif rsi14 > 70:
        pontos -= 1
    if preco <= banda_inf:
        pontos += 1
    elif preco >= banda_sup:
        pontos -= 1

    sinal = "COMPRA" if pontos >= 2 else "VENDA" if pontos <= -2 else "NEUTRO"

    return {
        "Ativo": ticker,
        "Fonte": fonte,
        "Preço": round(float(preco), 2),
        "RSI14": round(float(rsi14), 1),
        "MM9>MM21": "sim" if mm9.iloc[-1] > mm21.iloc[-1] else "não",
        "MACD": "positivo" if macd_hist > 0 else "negativo",
        "Bollinger": (
            "banda inferior"
            if preco <= banda_inf
            else "banda superior"
            if preco >= banda_sup
            else "meio"
        ),
        "Vol. rel.": round(vol_rel, 2) if vol_rel == vol_rel else "-",
        "Pontos": pontos,
        "Sinal técnico": sinal,
    }


def cor_sinal(sinal):
    return {
        "COMPRA": ("#EAF3DE", "#27500A"),
        "VENDA": ("#FCEBEB", "#791F1F"),
        "NEUTRO": ("#F1EFE8", "#444441"),
        "sem dados": ("#F1EFE8", "#888780"),
    }.get(sinal, ("#F1EFE8", "#444441"))


def gerar_html(resultados, caminho="painel_etfs.html"):
    data = pd.Timestamp.today().strftime("%d/%m/%Y")
    linhas = ""
    for r in resultados:
        sinal = r.get("Sinal técnico", "sem dados")
        bg, fg = cor_sinal(sinal)
        if "Preço" not in r:
            linhas += (
                f'<tr><td class="tk">{r["Ativo"]}</td>'
                f'<td colspan="7" style="color:#888780;">sem dados — '
                f"ver checklist no terminal</td>"
                f'<td><span class="pill" style="background:{bg};color:{fg};">'
                f"{sinal}</span></td></tr>"
            )
            continue
        rsi_cor = (
            "#791F1F"
            if r["RSI14"] > 70
            else "#27500A"
            if r["RSI14"] < 30
            else "#444441"
        )
        vol = r["Vol. rel."]
        vol_peso = "500" if isinstance(vol, (int, float)) and vol >= 1.5 else "400"
        linhas += (
            f"<tr>"
            f'<td class="tk">{r["Ativo"]}</td>'
            f"<td>R$ {r['Preço']:.2f}</td>"
            f'<td style="color:{rsi_cor};font-weight:500;">{r["RSI14"]}</td>'
            f"<td>{'↑' if r['MM9>MM21'] == 'sim' else '↓'} {r['MM9>MM21']}</td>"
            f"<td>{r['MACD']}</td>"
            f"<td>{r['Bollinger']}</td>"
            f'<td style="font-weight:{vol_peso};">{vol}</td>'
            f'<td style="text-align:center;">{r["Pontos"]:+d}</td>'
            f'<td><span class="pill" style="background:{bg};color:{fg};">{sinal}</span></td>'
            f"</tr>"
        )

    html = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Painel ETFs — {data}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#faf9f5;
         color:#1a1a18; margin:0; padding:32px; }}
  .wrap {{ max-width:900px; margin:0 auto; }}
  h1 {{ font-size:20px; font-weight:500; margin:0 0 4px; }}
  .sub {{ color:#6b6a63; font-size:13px; margin:0 0 20px; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:12px;
           overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,0.06); font-size:14px; }}
  th {{ text-align:left; padding:12px 14px; background:#f1efe8; font-weight:500;
        color:#444441; font-size:12px; text-transform:uppercase; letter-spacing:0.03em; }}
  td {{ padding:12px 14px; border-top:0.5px solid #eceae2; }}
  .tk {{ font-weight:500; }}
  .pill {{ padding:4px 12px; border-radius:20px; font-size:13px; font-weight:500;
           white-space:nowrap; }}
  .nota {{ color:#6b6a63; font-size:12px; margin-top:16px; line-height:1.6; }}
  .legenda {{ background:#fff; border-radius:12px; padding:20px 24px; margin-top:20px;
              box-shadow:0 1px 3px rgba(0,0,0,0.06); }}
  .legenda h2 {{ font-size:14px; font-weight:500; margin:0 0 14px; color:#1a1a18; }}
  .legenda dl {{ margin:0; display:grid; grid-template-columns:auto 1fr; gap:10px 16px; }}
  .legenda dt {{ font-weight:500; color:#185FA5; font-size:13px; white-space:nowrap; }}
  .legenda dd {{ margin:0; color:#444441; font-size:13px; line-height:1.5; }}
</style></head><body><div class="wrap">
<h1>Painel técnico dos ETFs</h1>
<p class="sub">{data} · fonte: Yahoo Finance / brapi.dev</p>
<table>
<thead><tr><th>Ativo</th><th>Preço</th><th>RSI 14</th><th>MM 9x21</th><th>MACD</th>
<th>Bollinger</th><th>Vol. rel.</th><th>Pontos</th><th>Sinal</th></tr></thead>
<tbody>{linhas}</tbody></table>
<div class="legenda">
<h2>O que cada coluna significa</h2>
<dl>
<dt>RSI 14</dt><dd>Força do movimento nos últimos 14 dias, de 0 a 100. Acima de 70 = sobrecomprado (esticado, cuidado para comprar). Abaixo de 30 = sobrevendido (possível pechincha).</dd>
<dt>MM 9x21</dt><dd>Cruzamento das médias móveis de 9 e 21 dias. &uarr; sim = média curta acima da longa (tendência de alta). &darr; não = média curta abaixo (tendência de baixa).</dd>
<dt>MACD</dt><dd>Mede se a tendência está ganhando ou perdendo força. Positivo = momento comprador. Negativo = momento vendedor.</dd>
<dt>Bollinger</dt><dd>Onde o preço está dentro da faixa normal de oscilação. Banda inferior = preço baixo (possível compra). Banda superior = preço alto (possível realização). Meio = dentro do normal.</dd>
<dt>Vol. rel.</dt><dd>Volume do dia dividido pela média de 21 dias. Acima de 1,5 (em negrito) = movimento com força atrás, confirma rompimentos. Abaixo de 1 = movimento fraco, sinal menos confiável.</dd>
<dt>Pontos</dt><dd>Soma dos quatro indicadores, de &minus;4 a +4. A partir de +2 vira COMPRA, a partir de &minus;2 vira VENDA, no meio fica NEUTRO.</dd>
</dl>
</div>
<p class="nota">RSI em vermelho = sobrecomprado (&gt;70), verde = sobrevendido (&lt;30).
Volume relativo em negrito quando &ge; 1,5x a média (rompimento com força).
Pontuação de &minus;4 a +4: cruze sempre com o viés macro antes de decidir.<br>
Ferramenta educativa — não é recomendação de investimento.</p>
</div></body></html>"""

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(html)
    return os.path.abspath(caminho)


def coletar_series_fechamento():
    import numpy as np

    series = {}
    for tk in TICKERS:
        df, _ = obter_dados(tk)
        if not df.empty:
            series[tk] = df["Close"].squeeze().astype(float)
    for nome, ysym in CONTEXTO.items():
        try:
            d = yf.download(
                ysym, period="6mo", interval="1d", progress=False, auto_adjust=True
            )
            if d is not None and not d.empty:
                series[nome] = d["Close"].squeeze().astype(float)
        except Exception:
            print(f"  aviso: não consegui baixar {nome} ({ysym})")
    precos = pd.DataFrame(series).sort_index()
    retornos = np.log(precos / precos.shift(1)).dropna(how="all")
    return precos, retornos


def gerar_heatmap(retornos, caminho="asset_correlation.png", mostrar=False):
    import matplotlib
    import numpy as np

    if not mostrar:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    corr = retornos.corr()
    fig = plt.figure(figsize=(9, 8.8))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    sns.heatmap(
        corr,
        mask=mask,
        annot=True,
        fmt=".2f",
        cmap="RdBu_r",
        vmin=-1,
        vmax=1,
        center=0,
        square=True,
        linewidths=0.5,
        cbar_kws={"shrink": 0.8, "label": "Correlação de Pearson"},
        annot_kws={"size": 10},
    )
    plt.title("Correlação entre retornos diários (log)", fontsize=13, pad=14)

    legenda = (
        "Como ler:  perto de +1 (azul) = os dois sobem e caem juntos, pouca "
        "diversificação  •  perto de −1 (vermelho) = um sobe quando o outro "
        "cai, se protegem mutuamente  •  perto de 0 = movem-se de forma "
        "independente"
    )
    fig.text(
        0.5,
        0.02,
        legenda,
        ha="center",
        va="bottom",
        fontsize=8.5,
        color="#444441",
        wrap=True,
        bbox={
            "boxstyle": "round,pad=0.5",
            "facecolor": "#F1EFE8",
            "edgecolor": "#D3D1C7",
            "linewidth": 0.5,
        },
    )
    plt.tight_layout(rect=(0, 0.07, 1, 1))
    plt.savefig(caminho, dpi=130, bbox_inches="tight")
    print(f"  heatmap salvo: {os.path.abspath(caminho)}")
    if mostrar:
        plt.show()
    plt.close()
    return corr


def gerar_rolling(retornos, caminho="rolling_asset_correlation.png", mostrar=False):
    import matplotlib

    if not mostrar:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pares_validos = [
        (a, b)
        for a, b in PARES_ROLLING
        if a in retornos.columns and b in retornos.columns
    ]
    if not pares_validos:
        print("  correlação móvel: nenhum par disponível (faltam dados de contexto)")
        return

    fig = plt.figure(figsize=(11, 6.6))
    for a, b in pares_validos:
        roll = retornos[a].rolling(JANELA_ROLLING).corr(retornos[b])
        plt.plot(roll.index, roll, label=f"{a} × {b}", linewidth=1.6)
    plt.axhline(0, color="#888", linewidth=0.8, linestyle="--")
    plt.axhspan(0.5, 1, color="#EAF3DE", alpha=0.35, zorder=0)
    plt.axhspan(-1, -0.5, color="#FCEBEB", alpha=0.35, zorder=0)
    plt.ylim(-1, 1)
    plt.title(f"Correlação móvel de {JANELA_ROLLING} dias", fontsize=13, pad=12)
    plt.ylabel("Correlação")
    plt.legend(loc="upper left", fontsize=9, framealpha=0.9)
    plt.grid(alpha=0.2)

    legenda = (
        "Como ler:  cada linha é a correlação entre o par nos últimos "
        f"{JANELA_ROLLING} dias, recalculada a cada dia  •  faixa verde "
        "(> 0,5) = andam fortemente juntos nesse período  •  faixa "
        "vermelha (< −0,5) = se protegem mutuamente  •  linha cruzando "
        "o zero = mudança de regime na relação entre os ativos"
    )
    fig.text(
        0.5,
        0.015,
        legenda,
        ha="center",
        va="bottom",
        fontsize=8.5,
        color="#444441",
        wrap=True,
        bbox={
            "boxstyle": "round,pad=0.5",
            "facecolor": "#F1EFE8",
            "edgecolor": "#D3D1C7",
            "linewidth": 0.5,
        },
    )
    plt.tight_layout(rect=(0, 0.09, 1, 1))
    plt.savefig(caminho, dpi=130, bbox_inches="tight")
    print(f"  correlação móvel salva: {os.path.abspath(caminho)}")
    if mostrar:
        plt.show()
    plt.close()


def analise_correlacao(mostrar=False):
    print("\nColetando séries para correlação (ETFs + USD/BRL + Ibovespa)...")
    precos, retornos = coletar_series_fechamento()
    if retornos.shape[1] < 2 or retornos.shape[0] < 30:
        print("  dados insuficientes para correlação.")
        return
    print(f"  {retornos.shape[1]} séries, {retornos.shape[0]} dias em comum.")
    corr = gerar_heatmap(retornos, mostrar=mostrar)
    gerar_rolling(retornos, mostrar=mostrar)
    print("\nMatriz de correlação (retornos log):")
    print(corr.round(2).to_string())


def main():
    checar_versao_yfinance()
    resultados = [analisar(t) for t in TICKERS]
    tabela = pd.DataFrame(resultados)
    print("\nPainel técnico —", pd.Timestamp.today().strftime("%d/%m/%Y"))
    print(tabela.to_string(index=False))

    caminho = gerar_html(resultados)
    print(f"\nPainel visual gerado: {caminho}")
    try:
        import webbrowser

        webbrowser.open(f"file://{caminho}")
        print("Abrindo no navegador...")
    except Exception:
        print("Abra o arquivo acima no navegador.")
    if (tabela.get("Fonte") == "FALHOU").any():
        print(
            "\nAlguns ativos falharam. Checklist:"
            "\n 1. pip install --upgrade yfinance  (causa mais comum)"
            "\n 2. Crie um token gratuito em https://brapi.dev e rode:"
            "\n    export BRAPI_TOKEN=seu_token   (Linux/Mac)"
            "\n    set BRAPI_TOKEN=seu_token      (Windows)"
            "\n 3. Teste a conexão: o Yahoo pode bloquear redes"
            "\n    corporativas ou VPNs temporariamente."
        )
    print(
        "\nLembrete: cruze com o viés macro (DI futuro, NTN-B, Treasury 10a,"
        "\nUSD/BRL, spreads de crédito) antes de qualquer decisão."
        "\nFerramenta educativa — não é recomendação de investimento."
    )

    if "--corr" in sys.argv:
        analise_correlacao(mostrar="--show" in sys.argv)


if __name__ == "__main__":
    main()
