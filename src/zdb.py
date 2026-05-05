import sqlite3
import os
from datetime import datetime

def conectar():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "data", "buffer.db")
    # check_same_thread=False evita erros do Flask ao acessar o banco
    return sqlite3.connect(db_path, check_same_thread=False)

def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()

    # Tabela principal de pacotes (Semana 1 e 2)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pacotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id TEXT,
        ordem INTEGER,
        total INTEGER,
        pedaco TEXT,
        worker TEXT,
        cifra TEXT,
        status TEXT, -- 'recebido', 'enviado_worker', 'processado', 'lido_central'
        mensagem_decodificada TEXT,
        ts_recebido TEXT,
        ts_enviado TEXT,
        ts_processado TEXT
    )
    """)

    # Tabela de scores/modelo (Semana 3 e 4)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id TEXT UNIQUE,
        total_pacotes INTEGER,
        pacotes_ok INTEGER,
        latencia_media_ms REAL,
        score_integridade REAL,
        score_reconstrucao REAL,
        ts_score TEXT
    )
    """)

    conn.commit()
    conn.close()

def inserir_registro(message_id, ordem, total, pedaco, cifra):
    conn = conectar()
    cursor = conn.cursor()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
    INSERT INTO pacotes (message_id, ordem, total, pedaco, cifra, status, ts_recebido)
    VALUES (?, ?, ?, ?, ?, 'recebido', ?)
    """, (message_id, ordem, total, pedaco, cifra, ts))
    
    id_pacote = cursor.lastrowid
    conn.commit()
    conn.close()
    return id_pacote

def marcar_enviado(id_pacote, worker):
    conn = conectar()
    cursor = conn.cursor()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
    UPDATE pacotes
    SET worker = ?, status = 'enviado_worker', ts_enviado = ?
    WHERE id = ?
    """, (worker, ts, id_pacote))
    conn.commit()
    conn.close() 

def atualizar_resultado(id_pacote, resultado):
    conn = conectar()
    cursor = conn.cursor()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
    UPDATE pacotes
    SET mensagem_decodificada = ?, status = 'processado', ts_processado = ?
    WHERE id = ?
    """, (resultado, ts, id_pacote))
    conn.commit()
    conn.close()

def buscar_mensagens_para_central():
    conn = conectar()
    cursor = conn.cursor()
    
    # Busca apenas os message_id onde TODOS os pacotes já foram 'processados'
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
        msg_id = msg[0]
        
        # Puxa os pacotes daquela mensagem ESPECIFICAMENTE na ordem correta
        cursor.execute("""
            SELECT id, ordem, mensagem_decodificada 
            FROM pacotes
            WHERE message_id = ?
            ORDER BY ordem ASC
        """, (msg_id,))
        pacotes = cursor.fetchall()

        # Monta a frase final juntando tudo
        texto_completo = "".join([p[2] for p in pacotes if p[2]])
        
        mensagens_finais.append({
            "message_id": msg_id,
            "texto": texto_completo
        })

        # Atualiza o status de todos os pacotes dessa mensagem para mostrar que a Central já leu
        for p in pacotes:
            cursor.execute("""
                UPDATE pacotes
                SET status = 'lido_central'
                WHERE id = ?
            """, (p[0],))

    conn.commit()
    conn.close()
    
    return mensagens_finais

def buscar_status_geral():
    conn = conectar()
    cursor = conn.cursor()
    # Puxa os últimos 50 pacotes para ver o progresso ao vivo no Frontend
    cursor.execute("""
        SELECT message_id, ordem, total, status, mensagem_decodificada, pedaco
        FROM pacotes
        ORDER BY id DESC LIMIT 50
    """)
    linhas = cursor.fetchall()
    conn.close()

    lista = []
    for p in linhas:
        lista.append({
            "message_id": p[0],
            "ordem": p[1],
            "total": p[2],
            "status": p[3],
            "texto": p[4] or "",
            "morse": p[5] or ""
        })
    return lista


# ─── FUNÇÕES DE SCORE/MODELO (Semana 3 e 4) ───────────────────────────────────

def buscar_pacotes_da_mensagem(message_id: str) -> list:
    """Retorna todos os pacotes de uma mensagem específica, em ordem."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, ordem, total, mensagem_decodificada, ts_recebido, ts_processado, pedaco
        FROM pacotes
        WHERE message_id = ?
        ORDER BY ordem ASC
    """, (message_id,))
    linhas = cursor.fetchall()
    conn.close()

    return [
        {
            "id":                    p[0],
            "ordem":                 p[1],
            "total":                 p[2],
            "mensagem_decodificada": p[3],
            "ts_recebido":           p[4],
            "ts_processado":         p[5],
            "morse":                 p[6] or ""
        }
        for p in linhas
    ]


def salvar_score(dados: dict):
    """Salva (ou atualiza) o score de uma mensagem no banco."""
    conn = conectar()
    cursor = conn.cursor()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
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
    conn.commit()
    conn.close()


def buscar_scores() -> list:
    """Retorna os últimos 20 scores calculados, do mais recente ao mais antigo."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT message_id, total_pacotes, pacotes_ok, latencia_media_ms,
               score_integridade, score_reconstrucao, ts_score
        FROM scores
        ORDER BY id DESC LIMIT 20
    """)
    linhas = cursor.fetchall()
    conn.close()

    return [
        {
            "message_id":         p[0],
            "total_pacotes":      p[1],
            "pacotes_ok":         p[2],
            "latencia_media_ms":  p[3],
            "score_integridade":  p[4],
            "score_reconstrucao": p[5],
            "ts_score":           p[6],
        }
        for p in linhas
    ]


# ─── FUNÇÕES SEMANA 5 e 6 ──────────────────────────────────────────────────────

def buscar_estatisticas() -> dict:
    """Retorna estatísticas agregadas do sistema."""
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM pacotes")
    total_pacotes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(DISTINCT message_id) FROM pacotes")
    total_mensagens = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM pacotes WHERE status = 'processado' OR status = 'lido_central'")
    pacotes_processados = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM pacotes WHERE status = 'recebido' OR status = 'enviado_worker'")
    pacotes_pendentes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM scores")
    total_scores = cursor.fetchone()[0]

    cursor.execute("SELECT AVG(score_integridade), AVG(score_reconstrucao), AVG(latencia_media_ms) FROM scores")
    medias = cursor.fetchone()

    conn.close()

    return {
        "total_pacotes": total_pacotes,
        "total_mensagens": total_mensagens,
        "pacotes_processados": pacotes_processados,
        "pacotes_pendentes": pacotes_pendentes,
        "total_scores": total_scores,
        "media_integridade": round(medias[0] or 0, 2),
        "media_reconstrucao": round(medias[1] or 0, 2),
        "media_latencia_ms": round(medias[2] or 0, 2),
    }


def buscar_mensagens_decodificadas() -> list:
    """Lista todas as mensagens completas sem alterar o status (read-only)."""
    conn = conectar()
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
        msg_id = msg[0]
        cursor.execute("""
            SELECT mensagem_decodificada FROM pacotes
            WHERE message_id = ? ORDER BY ordem ASC
        """, (msg_id,))
        pacotes = cursor.fetchall()
        texto = "".join([p[0] for p in pacotes if p[0]])
        mensagens.append({
            "message_id": msg_id,
            "texto": texto,
            "total_pacotes": msg[2],
            "ts_recebido": msg[3],
        })

    conn.close()
    return mensagens


def limpar_banco():
    """Remove todos os dados das tabelas pacotes e scores."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pacotes")
    cursor.execute("DELETE FROM scores")
    conn.commit()
    conn.close()


def deletar_mensagem(message_id: str):
    """Remove todos os pacotes e o score de uma mensagem específica."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pacotes WHERE message_id = ?", (message_id,))
    cursor.execute("DELETE FROM scores WHERE message_id = ?", (message_id,))
    conn.commit()
    conn.close()
