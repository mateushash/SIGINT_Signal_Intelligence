"""
validador.py — Validador de Palavras (v2.2 Super Fast & Huge Dictionary)
========================================================================
Serviço de validação e reconstrução de texto via DP e Dicionário Local.

Melhorias v2.2:
  - Carrega a base gigante de 1.8M de palavras (inclui conjugações e plurais).
  - Remoção de consultas externas de API dentro do loop da Programação Dinâmica (DP).
    Isso elimina o gargalo catastrófico de sleeps e rate limits, tornando a segmentação instantânea (< 1ms).
  - A API externa (Dicionário Aberto) é consultada apenas como fallback final para palavras segmentadas
    que por acaso não existam no dicionário gigante de 1.8M de palavras (super raro!).
  - Removido fallback da API em Inglês (evitando falsos positivos em sílabas lixo).
"""

import os
import time
import logging
import unicodedata
from collections import OrderedDict

import requests

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("sigint.validador")

HEADERS = {"User-Agent": "Criasdecrip/2.0 (projeto academico)"}

# ─── NORMALIZAÇÃO ─────────────────────────────────────────────────────────────

def normalizar(palavra: str) -> str:
    """Remove acentos e converte para minúsculas."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', palavra.lower())
        if unicodedata.category(c) != 'Mn'
    )


# ─── DICIONÁRIO DE PARTÍCULAS E PALAVRAS COMUNS ─────────────────────────────

PARTICULAS_VALIDAS: set[str] = {
    # Artigos e preposições
    "A", "O", "E", "UM", "UNS", "UMA", "UMAS",
    "DE", "DA", "DO", "DAS", "DOS",
    "EM", "NO", "NA", "NOS", "NAS",
    "AO", "AOS", "AS",
    "COM", "POR", "PARA", "SEM", "SOB", "SOBRE",
    "COMO", "QUE", "SE", "OU", "MAS", "MAIS", "MENOS",

    # Pronomes
    "EU", "TU", "ELE", "ELA", "NOS", "VOS", "ELES", "ELAS",
    "ME", "TE", "LHE", "LHES",
    "MEU", "TEU", "SEU", "SUA", "MINHA", "TUAS",
    "NOSSA", "NOSSO", "NOSSAS", "NOSSOS",
    "ESTE", "ESSA", "ESSE", "ISTO", "ISSO", "AQUI", "ALI", "LA",

    # Verbos comuns
    "SOU", "ES", "FOI", "ERA", "SAO", "SOMOS",
    "TEM", "VAI", "VEM", "VOU", "DAR", "DIZ", "FAZ",
    "SER", "TER", "IR", "VIR", "POR",
    "FUI", "FEZ", "DOU", "VIM",
    "HA", "JA", "SO", "ATE",
    "ESTA", "ESTOU", "ESTAMOS", "ESTAO",
    "PODE", "QUER", "SABE", "DEVE", "ACHA",
    "SORRIR", "SORRI", "SORRISO", "SORRINDO",
    "AMAR", "AMO", "AMA", "AMEI", "AMANDO", "AMADO",
    "CANTAR", "CANTO", "CANTEI", "CANTANDO",
    "VOAR", "VOO", "VOEI", "VOANDO",
    "CORRER", "CORRO", "CORRI", "CORRENDO",
    "SONHAR", "SONHO", "SONHEI", "SONHANDO",
    "LEMBRAR", "LEMBRO", "LEMBREI", "LEMBRANDO",
    "SENTIR", "SINTO", "SENTI", "SENTINDO",
    "QUERER", "QUERO", "QUIZ", "QUERENDO",
    "ESCREVER", "ESCREVO", "ESCREVI", "ESCREVENDO",
    "COLORIR", "COLORO", "COLORI", "COLORINDO",
    "TIRAR", "TIRO", "TIREI", "TIRANDO",
    "PASSAR", "PASSO", "PASSEI", "PASSANDO",
    "FICAR", "FICO", "FIQUEI", "FICANDO",
    "OLHAR", "OLHO", "OLHEI", "OLHANDO",
    "CHAMAR", "CHAMO", "CHAMEI", "CHAMANDO",
    "LEVAR", "LEVO", "LEVEI", "LEVANDO",
    "TRAZER", "TRAGO", "TROUXE", "TRAZENDO",
    "DORMIR", "DURMO", "DORMI", "DORMINDO",
    "PARTIR", "PARTO", "PARTI", "PARTINDO",
    "ABRIR", "ABRO", "ABRI", "ABRINDO",
    "FECHAR", "FECHO", "FECHEI", "FECHANDO",
    "DIZER", "DIGO", "DISSE", "DIZENDO",
    "FAZER", "FACO", "FIZ", "FAZENDO",
    "SABER", "SEI", "SOUBE", "SABENDO",
    "PODER", "POSSO", "PUDE", "PODENDO",
    "CABER", "CAIBO", "COUBE", "CABENDO",
    "CAIR", "CAI", "CAIU", "CAINDO",
    "SAIR", "SAIO", "SAIR", "SAINDO",
    "ENTRAR", "ENTRO", "ENTREI", "ENTRANDO",
    "TOMAR", "TOMO", "TOMEI", "TOMANDO",
    "COLOCAR", "COLOCO", "COLOQUEI", "COLOCANDO",
    "MOSTRAR", "MOSTRO", "MOSTREI", "MOSTRANDO",
    "FALAR", "FALO", "FALEI", "FALANDO",
    "USAR", "USO", "USEI", "USANDO",
    "PEGAR", "PEGO", "PEGUEI", "PEGANDO",
    "JOGAR", "JOGO", "JOGUEI", "JOGANDO",
    "QUER", "QUERO",
    "CONTAR", "CONTO", "CONTEI", "CONTANDO",
    "CRIAR", "CRIO", "CRIEI", "CRIANDO",
    "ESQUECER", "ESQUECO", "ESQUECI", "ESQUECENDO",
    "PROCURAR", "PROCURO", "PROCUREI", "PROCURANDO",
    "ENCONTRAR", "ENCONTRO", "ENCONTREI", "ENCONTRANDO",
    "AJUDAR", "AJUDO", "AJUDEI", "AJUDANDO",
    "MUDAR", "MUDO", "MUDEI", "MUDANDO",
    "PARAR", "PARO", "PAREI", "PARANDO",
    "CONTINUAR", "CONTINUO", "CONTINUEI", "CONTINUANDO",
    "ACABAR", "ACABO", "ACABEI", "ACABANDO",
    "GANHAR", "GANHO", "GANHEI", "GANHANDO",
    "PERDER", "PERCO", "PERDI", "PERDENDO",
    "BEBER", "BEBO", "BEBI", "BEBENDO",
    "COMER", "COMO", "COMI", "COMENDO",
    "DANÇAR", "DANCO", "DANCEI",
    "CAÇAR", "CACO", "CACEI",
    "SEGUIR", "SIGO", "SEGUI", "SEGUINDO",
    "MORAR", "MORO", "MOREI", "MORANDO",
    "TRAÇAR", "TRACO", "TRACEI", "TRACANDO",
    "CURAR", "CURO", "CUREI", "CURANDO",
    "AGONIZAR", "AGONICAR",

    # Palavras curtas comuns
    "BOA", "BOM", "MAL", "BEM", "MAU",
    "DIA", "PAI", "MAE", "CEU", "RIO", "MAR", "SOL", "LUA",
    "OLA", "OI", "SIM", "NAO", "FIM",
    "RE", "AR", "AH", "EI",
    "AI", "LA", "CA", "JA", "SO", "HA",
    "PRA", "PRO", "TRA", "NUM", "NEL",
    "COR", "VEZ", "LUZ", "PAZ", "CHA", "PO",
    "AMOR", "DEUS", "VIDA", "MEDO", "ACAO",
    "MARTE", "TERRA", "ZONA",

    # Gírias e contrações coloquiais brasileiras
    # (frequentes em músicas e textos informais — não constam no dicionário formal)
    "CE", "CÊ",           # 'cê = você
    "TO", "TÔ",           # 'to = estou
    "TA", "TÁ",           # 'tá = está
    "NE", "NÉ",           # né = não é
    "VE", "VÊ",           # vê
    "DA", "DÁ",           # dá
    "VAI", "VÁI",
    "POR", "POIS",
    "NUM", "NUMA",        # num/numa = em um/uma
    "PRO", "PRA",         # para o / para a
    "NESSA", "NESSE", "NISTO", "NISSO", "NAQUELE", "NAQUELA",
    "DELA", "DELE", "DELAS", "DELES",
    "NELA", "NELE", "NELAS", "NELES",
    "PRA", "POR",
    "TAVA", "TAVAM", "TIVE", "TIVEMOS", "TIVERAM",  # estar conjugado informal
    "TIVESSE", "ESTIVESSE",
    "SERIA", "SERIAM", "SERIA",
    "TINHA", "TINHAM", "TINHAMOS",
    "TINHA", "TINHA",
    "FOI", "FORAM", "FOMOS", "FOREM",
    "FORA", "FORAM",
    "PODE", "PODEM", "PODEMOS", "PODIAM", "PODIA",
    "QUER", "QUEREM", "QUEREMOS", "QUERIA", "QUERIAM",
    "SABE", "SABEM", "SABEMOS", "SABIA", "SABIAM",
    "FAZ", "FAZEM", "FAZEMOS", "FAZIA", "FAZIAM",
    "VEM", "VIM", "VIEMOS", "VIERAM",
    "VAI", "VOU", "VAMOS", "VAIS",
    "DAR", "DA", "DAO", "DEU", "DERAM", "DAVA",
    "VER", "VE", "VEJO", "VIU", "VIRAM", "VIA",
    "IR", "VOU", "FOI", "FORAM", "IA", "IRAO",
    "TER", "TENHO", "TEM", "TINHA", "TEVE",
    "ESTAR", "ESTOU", "ESTA", "ESTAVA", "ESTEVE",
    "SER", "SOU", "ERA", "FOI", "SEREI",
    "NESSA", "NESSE", "DESSA", "DESSE",
    "AQUELE", "AQUELA", "AQUELES", "AQUELAS",
    "QUAL", "QUAIS", "CUJO", "CUJA",

    # Palavras compostas / coloquiais / música popular brasileira
    "VAGALUMES", "VAGALUME",
    "MALHACAO", "EMBROMAR",
    "TRINTAO", "QUARENTAO",
    "BOATE", "BALADA", "PAGODE", "FORRÓ", "FORRO",
    "SAMBA", "BREGA", "AXEX",
    "CLARAO", "AURORA", "AMANHECER", "ANOITECER",
    "SAUDADE", "SAUDADES",
    "CANÇÃO", "CANCAO", "CANCOES",
    "MILHÃO", "MILHAO", "BILHAO", "TRILHAO",
    "CORAÇÃO", "CORACAO", "CORACOES",
    "EMOÇÃO", "EMOCAO", "EMOCOES",
    "PAIXÃO", "PAIXAO",
    "SOLIDÃO", "SOLIDAO",
    "TRAIÇÃO", "TRAICAO",
    "ILUSÃO", "ILUSAO",
    "DECEPÇÃO", "DEPCECAO",
    "OBRIGADO", "OBRIGADA",
    "FELIZ", "FELIZES",
    "TRISTE", "TRISTES",
    "ALEGRE", "ALEGRES", "ALEGRIA",
    "CHORAR", "CHORO", "CHOREI", "CHORANDO",
    "BRIGAR", "BRIGO", "BRIGUEI",
    "NAMORAR", "NAMORO", "NAMOREI",
    "ABRAÇAR", "ABRACO", "ABRACEI",
    "BEIJAR", "BEIJO", "BEIJEI",
    "CARINHO", "TERNURA",
    "AMIZADE", "AMIZADES",
    "MENTIRA", "MENTIRAS", "MENTIROSO",
    "VERDADE", "VERDADES",
    "REALIDADE", "REALIDADES",
    "IMPOSSIVEL", "POSSIVEL",
    "INCRIVEL", "INCREVEL",
    "TERRIVEL", "HORRIVEL",
    "MALDADE", "BONDADE",
    "SORRIDENTE", "FELIZMENTE",
    "SOZINHO", "SOZINHA", "JUNTOS", "JUNTAS",
    "DEVAGAR", "DEPRESSA", "RAPIDAMENTE",
    "SEMPRE", "NUNCA", "JAMAIS", "TALVEZ",
    "LONGE", "PERTO", "DENTRO", "FORA",
    "CIMA", "BAIXO", "FRENTE", "ATRAS",
    "LADO", "LADOS", "CANTO", "CANTOS",
    "VOLTA", "VOLTAS", "VOLTA",
    "OLHOS", "BOCA", "MAO", "MAOS",
    "BRACO", "BRACOS", "PES", "CABECA",
    "CORRER", "VENTO", "CHUVA", "NUVEM",
    "ESTRELA", "ESTRELAS", "COMETA",
    "IMENSIDAO", "INFINITO",
    "MUNDO", "MUNDOS", "UNIVERSO",
    "NOITE", "NOITES", "MANHA", "TARDE",
    "HORA", "HORAS", "MINUTO", "MINUTOS",
    "TEMPO", "TEMPOS", "ESPACO",
    "LUGAR", "LUGARES", "DESTINO",
    "CAMINHO", "CAMINHOS", "ESTRADA",
    "AGUA", "FOGO", "TERRA", "VENTO",
    "COR", "CORES", "COLORIDO",
    "MUSICA", "MELODIA", "RITMO", "LETRA",
    "INTEIRO", "INTEIRA", "COMPLETO", "COMPLETA",
    "NOVO", "NOVA", "NOVOS", "NOVAS",
    "VELHO", "VELHA", "ANTIGO", "ANTIGA",
    "PRIMEIRO", "PRIMEIRA", "ULTIMO", "ULTIMA",
    "UNICO", "UNICA", "ESPECIAL", "ESPECIAIS",
    "MESMO", "MESMA", "OUTROS", "OUTRAS",
    "QUALQUER", "NENHUM", "NENHUMA",
    "TANTO", "TANTA", "TANTOS", "TANTAS",
    "MUITO", "MUITA", "MUITOS", "MUITAS",
    "POUCO", "POUCA", "POUCOS", "POUCAS",
    "TODO", "TODA", "TODOS", "TODAS",
    "CADA", "ALGUM", "ALGUMA", "ALGUNS", "ALGUMAS",
    "MAIS", "MENOS",
    "DEMAIS", "EMBORA", "PORTANTO", "POREM", "ENTAO",
    "PORQUE", "POIS", "QUANDO", "ONDE", "COMO",
    "ENQUANTO", "DEPOIS", "ANTES", "AGORA", "LOGO",
    "AINDA", "APENAS", "SO", "SOMENTE", "TAMBEM",
    "JA", "NUNCA", "SEMPRE", "TUDO", "NADA",
    "ALGO", "ALGUEM", "NINGUEM",
}


# ─── CARREGAMENTO DO DICIONÁRIO ──────────────────────────────────────────────
PALAVRAS_PT: set[str] = set()
DIC_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "palavras.txt")

# Tamanho máximo de palavra no dicionário (para limitar DP)
MAX_WORD_LEN = 0


def carregar_dicionario():
    """Carrega o dicionário gigante de palavras em português."""
    global PALAVRAS_PT, MAX_WORD_LEN

    # Download do dicionário gigante se não existir
    if not os.path.exists(DIC_FILE):
        try:
            logger.info("Baixando dicionário gigante de 1.8M de palavras (AlfredoFilho/Palavras_PT-BR)...")
            r = requests.get(
                "https://raw.githubusercontent.com/AlfredoFilho/Palavras_PT-BR/master/Palavras_PT-BR.txt",
                timeout=45
            )
            r.raise_for_status()
            os.makedirs(os.path.dirname(DIC_FILE), exist_ok=True)
            with open(DIC_FILE, "w", encoding="utf-8") as f:
                f.write(r.text)
            logger.info("Dicionário gigante baixado com sucesso.")
        except Exception as e:
            logger.error(f"Falha ao baixar dicionário gigante: {e}")

    # Carrega arquivo local
    if os.path.exists(DIC_FILE):
        try:
            t0 = time.time()
            with open(DIC_FILE, "r", encoding="utf-8") as f:
                for w in f:
                    w = w.strip()
                    if not w or not w.replace("-", "").replace(".", "").isalpha():
                        continue

                    norm = normalizar(w).upper()

                    # Filtro inteligente
                    if len(norm) == 1 and norm not in {"A", "O", "E"}:
                        continue
                    if len(norm) == 2 and norm not in PARTICULAS_VALIDAS:
                        continue

                    PALAVRAS_PT.add(norm)

            logger.info(f"Dicionário carregado em {time.time() - t0:.2f}s: {len(PALAVRAS_PT)} palavras")
        except Exception as e:
            logger.error(f"Erro ao carregar dicionário: {e}")

    # Adiciona partículas conhecidas
    PALAVRAS_PT.update(PARTICULAS_VALIDAS)

    # Calcula tamanho máximo de palavra para otimizar DP
    MAX_WORD_LEN = max((len(w) for w in PALAVRAS_PT), default=25)
    MAX_WORD_LEN = min(MAX_WORD_LEN, 30)  # Cap para segurança
    logger.info(f"Tamanho máximo de palavra: {MAX_WORD_LEN}")


# Carrega na inicialização
carregar_dicionario()


# ─── CACHE PARA API EXTERNA ──────────────────────────────────────────────────

class LRUCache:
    """Cache LRU com tamanho máximo para evitar memory leak."""

    def __init__(self, maxsize: int = 4000):
        self._cache: OrderedDict[str, bool] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> bool | None:
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: bool):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        while len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)


_api_cache = LRUCache(maxsize=4000)

# Rate limiting
_last_api_call = 0.0
_API_MIN_INTERVAL = 0.1  # mínimo 100ms entre chamadas


def verificar_api(palavra: str) -> bool:
    """Verifica se uma palavra existe via API externa (Dicionário Aberto)."""
    global _last_api_call

    chave = normalizar(palavra)

    # Verifica cache
    cached = _api_cache.get(chave)
    if cached is not None:
        return cached

    # Rate limiting
    agora = time.time()
    espera = _API_MIN_INTERVAL - (agora - _last_api_call)
    if espera > 0:
        time.sleep(espera)
    _last_api_call = time.time()

    # Tenta Dicionário Aberto de Língua Portuguesa
    try:
        r = requests.get(
            f"https://api.dicionario-aberto.net/word/{chave}",
            headers=HEADERS,
            timeout=2
        )
        if r.status_code == 200:
            dados = r.json()
            valida = isinstance(dados, list) and len(dados) > 0 and not dados[0].get("deleted", 1)
            _api_cache.set(chave, valida)
            return valida
    except Exception:
        pass

    _api_cache.set(chave, False)
    return False


# ─── SEGMENTAÇÃO COM PROGRAMAÇÃO DINÂMICA ─────────────────────────────────────

def segmentar_local(texto: str) -> list[str]:
    """
    Segmenta texto contínuo em palavras usando DP.
    Prioriza: menor qtd de chars não reconhecidos, depois menor nº de palavras,
    e como desempate final prefere palavras mais longas (via word_len_bonus).
    """
    texto = normalizar(texto).upper().replace(" ", "")
    n = len(texto)
    if n == 0:
        return []

    max_len = min(MAX_WORD_LEN + 1, n + 1)

    # dp[i] = (unrec_chars, num_words, neg_matched_chars, split_point)
    # neg_matched_chars: negativo do total de chars reconhecidos — menor = mais chars reconhecidos
    INF = float('inf')
    dp: list[tuple[float, float, float, int]] = [(INF, INF, INF, -1)] * (n + 1)
    dp[n] = (0, 0, 0, n)

    for i in range(n - 1, -1, -1):
        best = (INF, INF, INF, -1)  # (unrec, words, neg_matched, split)

        for j in range(i + 1, min(i + max_len, n + 1)):
            chunk = texto[i:j]
            chunk_len = j - i

            if chunk in PALAVRAS_PT:
                unrec_cost = 0
                # Palavras de 1 char têm custo mais alto para desincentivar
                # splits em partículas isoladas quando uma palavra maior cabe
                word_cost = 3.0 if chunk_len == 1 else 1.0
                matched = chunk_len
            else:
                unrec_cost = chunk_len
                word_cost = 0.0  # não conta como "palavra" real
                matched = 0

            next_unrec, next_words, next_neg_match, _ = dp[j]
            total_unrec   = unrec_cost + next_unrec
            total_words   = word_cost  + next_words
            total_neg_match = (-matched) + next_neg_match  # mais negativo = mais chars cobertos

            # Desempate triplo: 1º menos chars ignorados, 2º menos palavras, 3º mais chars cobertos
            candidate = (total_unrec, total_words, total_neg_match, j)
            if candidate[:3] < best[:3]:
                best = candidate

        dp[i] = best

    # Reconstrói a segmentação
    resultado: list[str] = []
    curr = 0
    while curr < n:
        _, _, _, next_split = dp[curr]
        if next_split == -1:
            resultado.append(texto[curr:])
            break
        resultado.append(texto[curr:next_split])
        curr = next_split

    return resultado


# ─── VALIDAÇÃO FINAL ──────────────────────────────────────────────────────────

def validar_mensagem(texto_bruto: str) -> dict:
    """
    Valida e reconstrói texto decodificado.

    Estratégia de 3 camadas:
      1. Respeita espaços existentes como fronteiras de palavras (o worker já decodifica corretamente).
      2. Para cada token, busca direto no dicionário de 1.8M — O(1).
      3. Só aplica DP em tokens desconhecidos (sequências sem espaço que o worker colou).
    Isso evita o bug crítico de concatenar todo o texto e re-segmentar do zero.
    """
    inicio = time.time()
    texto_upper = texto_bruto.upper().strip()

    # ── Camada 1: divide nos espaços já presentes no texto ─────────────────────
    tokens_raw = texto_upper.split()
    palavras_segmentadas: list[str] = []

    if tokens_raw:
        for token in tokens_raw:
            token_norm = normalizar(token).upper()
            if token_norm in PALAVRAS_PT:
                # Token reconhecido diretamente → usa como está
                palavras_segmentadas.append(token_norm)
            elif len(token_norm) <= 2:
                # Token curto não encontrado → mantém (provável sigla/ruído)
                palavras_segmentadas.append(token_norm)
            else:
                # ── Camada 2 & 3: aplica DP só neste token isolado ──────────
                sub = segmentar_local(token)
                palavras_segmentadas.extend(sub)
    else:
        # Sem espaços: aplica DP no texto inteiro (fallback para pacotes colados)
        palavras_segmentadas = segmentar_local(texto_upper)

    # ── Validação final palavra a palavra ──────────────────────────────────────
    resultados: list[dict] = []
    for p in palavras_segmentadas:
        if not p:
            continue
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

    tempo_ms = round((time.time() - inicio) * 1000, 1)
    logger.info(
        f"Validação: {validas}/{total} palavras válidas "
        f"({score}%) em {tempo_ms}ms"
    )

    return {
        "texto_original": texto_bruto,
        "texto_reconstruido": texto_reconstruido,
        "palavras": resultados,
        "total_palavras": total,
        "palavras_validas": validas,
        "score_validacao": score,
        "tempo_ms": tempo_ms,
        "api_usada": "Dicionário Híbrido Gigante (DP + Local 1.8M + API v3)"
    }
