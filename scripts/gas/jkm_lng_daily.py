#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Daily JKM LNG — gás natural liquefeito asiático market report — ENERGY REPORTS visual standard."""
import os, sys, argparse, html, time, requests
from datetime import datetime, timezone, timedelta
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),"..",".."))
if ROOT not in sys.path: sys.path.insert(0,ROOT)
from providers.llm_client import LLMClient
from scripts.gas.tools import title_counter, send_to_telegram
BRT=timezone(timedelta(hours=-3))
TICKER="JKM=F"
KEY="daily_jkm_lng"
EMOJI="🌏"
ASSET="JKM LNG — gás natural liquefeito asiático"
UNIT="USD"

def today():
    return datetime.now(BRT).strftime("%d/%m/%Y")

def quote():
    """Retrieve daily Yahoo Finance chart data; fail gracefully and label unavailable."""
    try:
        url=f"https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}?range=1mo&interval=1d"
        r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=20); r.raise_for_status()
        j=r.json()["chart"]["result"][0]
        q=j["indicators"]["quote"][0]
        closes=[v for v in (q.get("close") or []) if v is not None]
        timestamps=j.get("timestamp") or []
        if not closes: return {"last":"N/D","change":"N/D","date":"N/D","ticker":TICKER}
        last=closes[-1]; prev=closes[-2] if len(closes)>1 else None
        chg=((last-prev)/prev*100) if prev else None
        stamp=timestamps[-1] if timestamps else None
        date=datetime.fromtimestamp(stamp,timezone.utc).strftime("%d/%m/%Y") if stamp else "N/D"
        return {"last":f"{last:.4f}","change":f"{chg:+.2f}%" if chg is not None else "N/D","date":date,"ticker":TICKER}
    except Exception as e:
        print(f"Quote fetch failed: {e}",flush=True)
        return {"last":"N/D","change":"N/D","date":"N/D","ticker":TICKER}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--preview",action="store_true")
    p.add_argument("--force",action="store_true")
    p.add_argument("--counter-path",default="data/counters.json")
    p.add_argument("--sent-path",default=None)
    p.add_argument("--provider",default=None)
    args=p.parse_args()
    sent_path=args.sent_path or f"data/sentinels/{KEY}.sent"
    today_tag=datetime.now(BRT).strftime("%Y-%m-%d")
    if not args.force and os.path.exists(sent_path):
        try:
            import json
            if json.load(open(sent_path,encoding="utf-8")).get("last_sent")==today_tag:
                print("Já enviado hoje (trava diária). Use --force para ignorar."); return
        except Exception: pass
    q=quote()
    context=f"Ativo: {ASSET}\nTicker: {TICKER}\nÚltimo valor: {q['last']} {UNIT}\nVariação diária: {q['change']}\nData da cotação: {q['date']}\nFonte: Yahoo Finance chart endpoint. Dados indisponíveis devem ser indicados como N/D.\n"
    system="Você é analista sênior de mercados de energia. Escreva em português brasileiro, conciso, sem inventar dados, eventos, preços, datas, probabilidades ou citações. Use N/D para informação não comprovada."
    prompt=f"""Produza relatório diário de {ASSET} no padrão visual ENERGY REPORTS, somente HTML compatível Telegram (<b>, <i>), sem markdown.
{EMOJI} <b>ENERGY REPORTS | {ASSET.upper()}</b>
📅 {today()} | Diário

━━━━━━━━━━━━━━━━━━
⚡ <b>PAINEL DE MERCADO</b>
• preço, unidade, variação, data da cotação
• indicadores disponíveis; indisponíveis como N/D

━━━━━━━━━━━━━━━━━━
🧭 <b>LEITURA EXECUTIVA</b>
3 bullets de viés, momentum e riscos, estritamente baseados em contexto.

━━━━━━━━━━━━━━━━━━
📊 <b>FUNDAMENTOS</b>
Oferta, demanda, estoques, curva, spreads e dados específicos do ativo. Diferencie dados e interpretação; não afirme informações não fornecidas.

━━━━━━━━━━━━━━━━━━
🌐 <b>MACRO & GEOPOLÍTICA</b>
Fatores macro e riscos relevantes, sem alegações factuais recentes não suportadas.

━━━━━━━━━━━━━━━━━━
🔎 <b>O QUE MONITORAR</b>
3 indicadores/eventos.

━━━━━━━━━━━━━━━━━━
🎯 <b>CENÁRIOS</b>
🟢 Altista | 🟡 Base | 🔴 Baixista — condições, não preços/probabilidades inventados.

━━━━━━━━━━━━━━━━━━
📝 <b>CONCLUSÃO</b>
Perspectiva curto/médio prazo e grau de confiança explicado.

━━━━━━━━━━━━━━━━━━
⚠️ <i>Relatório automatizado e informativo; não constitui recomendação de investimento.</i>
Contexto factual:
{context}
Conteúdo específico a cobrir: JKM LNG spot e futuros, LNG, importações asiáticas, clima, oferta, liquefação, fretes, spreads Henry Hub/TTF quando verificáveis
"""
    llm=LLMClient(provider=args.provider or None)
    t0=time.time(); body=llm.generate(system_prompt=system,user_prompt=prompt,temperature=0.35,max_tokens=1700); dt=time.time()-t0
    num=title_counter(args.counter_path,key=KEY)
    title=f"{EMOJI} {ASSET} — Relatório Diário — {today()} — Nº {num}"
    final=f"<b>{html.escape(title)}</b>\n\n{body.strip()}\n\n<i>LLM: {html.escape(str(llm.active_provider))} · {dt:.1f}s</i>"
    print(final,flush=True)
    send_to_telegram(final,preview=args.preview)
    if not args.preview:
        os.makedirs(os.path.dirname(sent_path) or '.',exist_ok=True)
        import json
        with open(sent_path,'w',encoding='utf-8') as fh:
            json.dump({'last_sent':today_tag},fh)

if __name__=="__main__": main()
