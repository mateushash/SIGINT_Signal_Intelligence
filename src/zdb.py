"""
zdb.py — Database Layer (v2 Hardened)
======================================
Módulo de acesso ao SQLite com:
  - WAL mode para concorrência
  - Connection pool thread-local
  - Índices otimizados
  - Retry automático em caso de lock
  - Context manager para transações seguras
  - Logging estruturado
"""

import sqlite3
import os
import time
import threading
import logging
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger("sigint.db")

# ─── CONFIGURAÇÃO ─────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "buffer.db")

MAX_RETRIES = 5
RETRY_DELAY = 0.1  # segundos (com backoff)

# Thread-local storage para conexões
_thread_local = threading.local()
_db_lock = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    """Retorna uma conexão thread-local reutilizável com WAL mode."""
    conn = getattr(_thread_local, "connection", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA cache_size=-8000")  # 8MB cache
        conn.row_factory = sqlite3.Row
        _thread_local.connection = conn
    return conn


@contextmanager
def _transacao():
    """Context manager para transações com retry automático em caso de lock."""
    conn = _get_connection()
    tentativas = 0
    while True:
        try:
            yield conn
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and tentativas < MAX_RETRIES:
                tentativas += 1
                delay = RETRY_DELAY * (2 ** tentativas)
                logger.warning(f"DB locked, retry {tentativas}/{MAX_RETRIES} em {delay:.2f}s")
                time.sleep(delay)
            else:
                conn.rollback()
                logger.error(f"Erro de banco: {e}")
                raise
        except Exception as e:
            conn.rollback()
            logger.error(f"Erro de banco: {e}")
            raise


@contextmanager
def _leitura():
    """Context manager para consultas read-only (sem commit)."""
    conn = _get_connection()
    try:
        yield conn
    except Exception as e:
        logger.error(f"Erro na leitura: {e}")
        raise


# ─── INICIALIZAÇÃO ────────────────────────────────────────────────────────────

def criar_tabela():
    """Cria as tabelas e índices necessários (idempotente)."""
    with _transacao() as conn:
        cursor = conn.cursor()

        # Tabela principal de pacotes
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pacotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT NOT NULL,
            ordem INTEGER NOT NULL,
            total INTEGER NOT NULL,
            pedaco TEXT,
            worker TEXT,
            cifra TEXT,
            status TEXT DEFAULT 'recebido',
            mensagem_decodificada TEXT,
            ts_recebido TEXT,
            ts_enviado TEXT,
            ts_processado TEXT
        )
        """)

        # Tabela de scores
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE NOT NULL,
            total_pacotes INTEGER,
            pacotes_ok INTEGER,
            latencia_media_ms REAL,
            score_integridade REAL,
            score_reconstrucao REAL,
            ts_score TEXT
        )
        """)

        # ── Índices para performance ──────────────────────────────────────────
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pacotes_message_id
            ON pacotes(message_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pacotes_status
            ON pacotes(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pacotes_msg_ordem
            ON pacotes(message_id, ordem)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scores_message_id
            ON scores(message_id)
        """)

    logger.info("Tabelas e índices criados/verificados com sucesso.")


# ─── CRUD DE PACOTES ──────────────────────────────────────────────────────────

def inserir_registro(message_id: str, ordem: int, total: int, pedaco: str, cifra: str) -> int:
    """Insere um novo pacote e retorna seu ID."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _transacao() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO pacotes (message_id, ordem, total, pedaco, cifra, status, ts_recebido)
        VALUES (?, ?, ?, ?, ?, 'recebido', ?)
        """, (message_id, ordem, total, pedaco, cifra, ts))
        id_pacote = cursor.lastrowid
    logger.debug(f"Pacote inserido: id={id_pacote} msg={message_id[:8]}... ordem={ordem}")
    return id_pacote


def marcar_enviado(id_pacote: int, worker: str):
    """Atualiza o status para 'enviado_worker'."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _transacao() as conn:
        conn.cursor().execute("""
        UPDATE pacotes
        SET worker = ?, status = 'enviado_worker', ts_enviado = ?
        WHERE id = ?
        """, (worker, ts, id_pacote))


def atualizar_resultado(id_pacote: int, resultado: str):
    """Salva o texto decodificado e marca como 'processado'."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _transacao() as conn:
        conn.cursor().execute("""
        UPDATE pacotes
        SET mensagem_decodificada = ?, status = 'processado', ts_processado = ?
        WHERE id = ?
        """, (resultado, ts, id_pacote))
    logger.debug(f"Pacote {id_pacote} processado: '{resultado[:50]}...'")


# ─── CONSULTAS ────────────────────────────────────────────────────────────────

def buscar_mensagens_para_central() -> list:
    """Busca mensagens completamente processadas e marca como lidas pela Central."""
    with _transacao() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT message_id, COUNT(*) as qtd, total
            FROM pacotes
            WHERE status = 'processado'
            GROUP BY message_id
            HAVING qtd = total
        """)
        prontos = cursor.fetchall()

        mensagens_finais = []
        for msg in prontos:
            msg_id = msg["message_id"]

            cursor.execute("""
                SELECT id, ordem, mensagem_decodificada
                FROM pacotes
                WHERE message_id = ?
                ORDER BY ordem ASC
            """, (msg_id,))
            pacotes = cursor.fetchall()

            texto_completo = "".join([p["mensagem_decodificada"] for p in pacotes if p["mensagem_decodificada"]])

            mensagens_finais.append({
                "message_id": msg_id,
                "texto": texto_completo
            })

            # Marca todos os pacotes como lidos
            cursor.execute("""
                UPDATE pacotes SET status = 'lido_central'
                WHERE message_id = ? AND status = 'processado'
            """, (msg_id,))

    return mensagens_finais


def buscar_status_geral() -> list:
    """Retorna os últimos 50 pacotes para o monitor em tempo real."""
    with _leitura() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT message_id, ordem, total, status, mensagem_decodificada, pedaco
            FROM pacotes
            ORDER BY id DESC LIMIT 50
        """)
        linhas = cursor.fetchall()

    return [
        {
            "message_id": p["message_id"],
            "ordem": p["ordem"],
            "total": p["total"],
            "status": p["status"],
            "texto": p["mensagem_decodificada"] or "",
            "morse": p["pedaco"] or ""
        }
        for p in linhas
    ]


def buscar_pacotes_da_mensagem(message_id: str) -> list:
    """Retorna todos os pacotes de uma mensagem específica, em ordem."""
    with _leitura() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, ordem, total, mensagem_decodificada, ts_recebido, ts_processado, pedaco
            FROM pacotes
            WHERE message_id = ?
            ORDER BY ordem ASC
        """, (message_id,))
        linhas = cursor.fetchall()

    return [
        {
            "id":                    p["id"],
            "ordem":                 p["ordem"],
            "total":                 p["total"],
            "mensagem_decodificada": p["mensagem_decodificada"],
            "ts_recebido":           p["ts_recebido"],
            "ts_processado":         p["ts_processado"],
            "morse":                 p["pedaco"] or ""
        }
        for p in linhas
    ]


# ─── FUNÇÕES DE SCORE ─────────────────────────────────────────────────────────

def salvar_score(dados: dict):
    """Salva (ou atualiza) o score de uma mensagem no banco."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _transacao() as conn:
        conn.cursor().execute("""
            INSERT INTO scores
                (message_id, total_pacotes, pacotes_ok, latencia_media_ms,
                 score_integridade, score_reconstrucao, ts_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                total_pacotes      = excluded.total_pacotes,
                pacotes_ok         = excluded.pacotes_ok,
                latencia_media_ms  = excluded.latencia_media_ms,
                score_integridade  = excluded.score_integridade,
                score_reconstrucao = excluded.score_reconstrucao,
                ts_score           = excluded.ts_score
        """, (
            dados["message_id"],
            dados["total_pacotes"],
            dados["pacotes_ok"],
            dados["latencia_media_ms"],
            dados["score_integridade"],
            dados["score_reconstrucao"],
            ts,
        ))
    logger.info(f"Score salvo para msg={dados['message_id'][:8]}... integ={dados['score_integridade']}%")


def buscar_scores() -> list:
    """Retorna os últimos 20 scores calculados."""
    with _leitura() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT message_id, total_pacotes, pacotes_ok, latencia_media_ms,
                   score_integridade, score_reconstrucao, ts_score
            FROM scores
            ORDER BY id DESC LIMIT 20
        """)
        linhas = cursor.fetchall()

    return [
        {
            "message_id":         p["message_id"],
            "total_pacotes":      p["total_pacotes"],
            "pacotes_ok":         p["pacotes_ok"],
            "latencia_media_ms":  p["latencia_media_ms"],
            "score_integridade":  p["score_integridade"],
            "score_reconstrucao": p["score_reconstrucao"],
            "ts_score":           p["ts_score"],
        }
        for p in linhas
    ]


# ─── FUNÇÕES DE ESTATÍSTICAS ─────────────────────────────────────────────────

def buscar_estatisticas() -> dict:
    """Retorna estatísticas agregadas do sistema."""
    with _leitura() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as cnt FROM pacotes")
        total_pacotes = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(DISTINCT message_id) as cnt FROM pacotes")
        total_mensagens = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM pacotes WHERE status IN ('processado', 'lido_central')")
        pacotes_processados = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM pacotes WHERE status IN ('recebido', 'enviado_worker')")
        pacotes_pendentes = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM scores")
        total_scores = cursor.fetchone()["cnt"]

        cursor.execute("SELECT AVG(score_integridade) as ai, AVG(score_reconstrucao) as ar, AVG(latencia_media_ms) as al FROM scores")
        medias = cursor.fetchone()

    return {
        "total_pacotes": total_pacotes,
        "total_mensagens": total_mensagens,
        "pacotes_processados": pacotes_processados,
        "pacotes_pendentes": pacotes_pendentes,
        "total_scores": total_scores,
        "media_integridade": round(medias["ai"] or 0, 2),
        "media_reconstrucao": round(medias["ar"] or 0, 2),
        "media_latencia_ms": round(medias["al"] or 0, 2),
    }


def buscar_mensagens_decodificadas() -> list:
    """Lista todas as mensagens completas (read-only)."""
    with _leitura() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT message_id, COUNT(*) as qtd, total, MIN(ts_recebido) as primeiro
            FROM pacotes
            WHERE status IN ('processado', 'lido_central')
            GROUP BY message_id
            HAVING qtd = total
            ORDER BY primeiro DESC
        """)
        prontos = cursor.fetchall()

        mensagens = []
        for msg in prontos:
            msg_id = msg["message_id"]
            cursor.execute("""
                SELECT mensagem_decodificada FROM pacotes
                WHERE message_id = ? ORDER BY ordem ASC
            """, (msg_id,))
            pacotes = cursor.fetchall()
            texto = "".join([p["mensagem_decodificada"] for p in pacotes if p["mensagem_decodificada"]])
            mensagens.append({
                "message_id": msg_id,
                "texto": texto,
                "total_pacotes": msg["total"],
                "ts_recebido": msg["primeiro"],
            })

    return mensagens


# ─── OPERAÇÕES DESTRUTIVAS ────────────────────────────────────────────────────

def limpar_banco():
    """Remove todos os dados das tabelas pacotes e scores."""
    with _transacao() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pacotes")
        cursor.execute("DELETE FROM scores")
    logger.warning("Banco de dados limpo completamente.")


def deletar_mensagem(message_id: str):
    """Remove todos os pacotes e o score de uma mensagem específica."""
    with _transacao() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pacotes WHERE message_id = ?", (message_id,))
        cursor.execute("DELETE FROM scores WHERE message_id = ?", (message_id,))
    logger.info(f"Mensagem {message_id[:8]}... deletada.")
