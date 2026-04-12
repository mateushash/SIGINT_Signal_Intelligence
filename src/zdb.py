import sqlite3
from datetime import datetime

def conectar():
    # check_same_thread=False evita erros do Flask ao acessar o banco
    return sqlite3.connect("buffer.db", check_same_thread=False)

#tabela padrao
def criar_tabela():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS pacotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id TEXT,  
        ordem INTEGER,
        total INTEGER,
        pedaco TEXT,
        worker TEXT,
        cifra TEXT,
        status TEXT, -- Estados: 'recebido', 'enviado_worker', 'processado', 'lido_central'
        mensagem_decodificada TEXT,
        ts_recebido TEXT,
        ts_enviado TEXT,
        ts_processado TEXT
    )
    """)
    conn.commit()
    conn.close()

#atualiza quando recebe do "listener"
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

#atualiza quando enviou pro worker
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

#atualizaa quando recebeu do worker
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

#funcao para tratamento 1 da central
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