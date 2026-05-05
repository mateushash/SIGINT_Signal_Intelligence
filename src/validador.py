"""
validador.py — Semana 5 e 6
============================
Serviço de Validação de Palavras via DP e Dicionário Local.
Otimizado para evitar fragmentação e reconhecer verbos comuns.
"""

import os
import time
import requests
import unicodedata

HEADERS = {"User-Agent": "Criasdecrip/1.0 (projeto academico)"}

def normalizar(palavra: str) -> str:
    """Remove acentos e converte para minúsculas."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', palavra.lower())
        if unicodedata.category(c) != 'Mn'
    )

# ─── CONFIGURAÇÃO DE RUÍDO LINGUÍSTICO ──────────────────────────────────────
PARTICULAS_VALIDAS = {
    "A","O","E","UM","UNS","UMA","UMAS","DE","DA","DO","DAS","DOS","EM","NO","NA","NOS","NAS",
    "AO","AOS","COMO","QUE","SE","OU","MAS","MAIS","POR","PARA","COM","SOU","FOI","ERA","TEM","VAI",
    "SER","TER","IR","VIR","DAR","DIZ","FAZ","BOA","BOM","MAL","BEM","DIA","PAI","MAE","CEU","RIO",
    "EU","TU","ELE","ELA","NOS","VOS","MEU","TEU","SEU","NOSSA","NOSSO","VOSSAS","VOSSOS","OLA","OI","SIM","NAO",
    "ATE","SOB","SAO","ESTA","TEMOS","TIVE","PODE","PUDO","QUER","VAI","VEM","DOU","FUI","FOI","ERA","ESTA"
}

PALAVRAS_PT = set()
DIC_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "palavras.txt")

def carregar_dicionario():
    global PALAVRAS_PT
    if not os.path.exists(DIC_FILE):
        try:
            r = requests.get("https://raw.githubusercontent.com/pythonprobr/palavras/master/palavras.txt")
            with open(DIC_FILE, "wb") as f: f.write(r.content)
        except: pass
    
    if os.path.exists(DIC_FILE):
        try:
            with open(DIC_FILE, "r", encoding="utf-8") as f:
                for w in f:
                    w = w.strip()
                    if w.isalpha():
                        norm = normalizar(w).upper()
                        if len(norm) == 1 and norm not in {"A", "O", "E"}:
                            continue
                        if len(norm) <= 3 and norm not in PARTICULAS_VALIDAS:
                            continue
                        PALAVRAS_PT.add(norm)
        except: pass

    # EXPANSÃO DE VERBOS E PALAVRAS COMUNS (Conserta o fatiamento)
    PALAVRAS_PT.update(PARTICULAS_VALIDAS)
    PALAVRAS_PT.update({
        "FUI", "FOI", "FOMOS", "FORAM", "FIZ", "FEZ", "FIZEMOS", "FIZERAM",
        "TENHO", "TEM", "TEMOS", "TENHAM", "HOJE", "ONTEM", "AMANHA",
        "JOGAR", "BOLA", "FUTEBOL", "PROVA", "ESCOLA", "AMIGO", "GENTE",
        "TESTANDO", "TESTE", "TESTAR", "TESTA", "ESTOU", "ESTA", "ESTAMOS",
        "ESTAO", "FAZENDO", "COMENDO", "VENDO", "LENDO", "DORMINDO",
        "BRASIL", "PORTUGUES", "SISTEMA", "CODIGO", "MENSAGEM", "PACIFICO"
    })

carregar_dicionario()

# ─── CACHE PARA CHAMADAS À API ────────────────────────────────────────────────
_cache = {}

def verificar_api(palavra: str) -> bool:
    chave = normalizar(palavra)
    if chave in _cache: return _cache[chave]
    try:
        r = requests.get(f"https://api.dicionario-aberto.net/word/{chave}", headers=HEADERS, timeout=2)
        if r.status_code == 200:
            dados = r.json()
            valida = isinstance(dados, list) and len(dados) > 0 and not dados[0].get("deleted", 1)
            _cache[chave] = valida
            return valida
    except: pass
    try:
        r = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{chave}", headers=HEADERS, timeout=1)
        valida = r.status_code == 200
        _cache[chave] = valida
        return valida
    except:
        _cache[chave] = False
        return False

# ─── SEGMENTAÇÃO COM PROGRAMAÇÃO DINÂMICA ─────────────────────────────────────
def segmentar_local(texto: str) -> list[str]:
    texto = normalizar(texto).upper().replace(" ", "")
    n = len(texto)
    if n == 0: return []

    dp = [(float('inf'), float('inf'), -1)] * (n + 1)
    dp[n] = (0, 0, n)

    for i in range(n - 1, -1, -1):
        best_unrec = float('inf')
        best_words = float('inf')
        best_split = -1

        for j in range(i + 1, min(i + 26, n + 1)):
            chunk = texto[i:j]
            unrec_cost = 0 if chunk in PALAVRAS_PT else len(chunk)
            
            next_unrec, next_words, _ = dp[j]
            total_unrec = unrec_cost + next_unrec
            total_words = 1 + next_words

            if total_unrec < best_unrec or (total_unrec == best_unrec and total_words < best_words):
                best_unrec = total_unrec
                best_words = total_words
                best_split = j

        dp[i] = (best_unrec, best_words, best_split)

    resultado = []
    curr = 0
    while curr < n:
        _, _, next_split = dp[curr]
        resultado.append(texto[curr:next_split])
        curr = next_split
    return resultado

# ─── VALIDAÇÃO FINAL ──────────────────────────────────────────────────────────
def validar_mensagem(texto_bruto: str) -> dict:
    inicio = time.time()
    texto_limpo = texto_bruto.upper().strip().replace(" ", "")

    palavras_segmentadas = segmentar_local(texto_limpo)
    resultados = []
    
    for p in palavras_segmentadas:
        chave = normalizar(p).upper()
        if chave in PALAVRAS_PT:
            valida = True
        else:
            valida = verificar_api(p)
        resultados.append({"palavra": p, "valida": valida})

    texto_reconstruido = " ".join(r["palavra"] for r in resultados)
    total = len(resultados)
    validas = sum(1 for r in resultados if r["valida"])
    score = round((validas / total) * 100, 1) if total else 0.0
    
    return {
        "texto_original": texto_bruto,
        "texto_reconstruido": texto_reconstruido,
        "palavras": resultados,
        "total_palavras": total,
        "palavras_validas": validas,
        "score_validacao": score,
        "tempo_ms": round((time.time() - inicio) * 1000, 1),
        "api_usada": "Dicionário Híbrido (DP + Local + API)"
    }
