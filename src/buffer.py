"""
buffer.py — Buffer Service (v2 Hardened)
=========================================
API Flask que recebe mensagens codificadas, fragmenta em pacotes,
publica no RabbitMQ e reúne os resultados dos workers.

Melhorias v2:
  - Connection pool pika (singleton thread-safe)
  - threading.Lock para dict respostas
  - TTL cleanup para mensagens órfãs
  - Validação de input
  - Retry na publicação
  - Logging estruturado
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from zdb import (
    criar_tabela, inserir_registro, marcar_enviado, atualizar_resultado,
    buscar_mensagens_para_central, buscar_status_geral, buscar_scores,
    buscar_pacotes_da_mensagem, buscar_estatisticas, buscar_mensagens_decodificadas,
    limpar_banco, deletar_mensagem
)
import uuid
import pika
import json
import time
import threading
import logging
from validador import validar_mensagem

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("sigint.buffer")

# ─── CONFIGURAÇÕES ────────────────────────────────────────────────────────────
RABBITMQ_HOST = "localhost"
SERVER_START_TIME = time.time()

app = Flask(__name__)
CORS(app)

# ─── ESTADO PROTEGIDO POR LOCK ───────────────────────────────────────────────
_respostas_lock = threading.Lock()
respostas: dict[str, dict[int, str]] = {}

# TTL para mensagens no dict respostas (5 minutos)
_respostas_ts: dict[str, float] = {}
RESPOSTAS_TTL = 300  # segundos


def _cleanup_respostas():
    """Remove entradas antigas do dict respostas para evitar memory leak."""
    agora = time.time()
    with _respostas_lock:
        expiradas = [
            mid for mid, ts in _respostas_ts.items()
            if agora - ts > RESPOSTAS_TTL
        ]
        for mid in expiradas:
            respostas.pop(mid, None)
            _respostas_ts.pop(mid, None)
            if expiradas:
                logger.warning(f"Limpeza TTL: {len(expiradas)} mensagens órfãs removidas")


# ─── PIKA CONNECTION POOL (Thread-Safe Singleton) ────────────────────────────
_pika_lock = threading.Lock()
_pika_conn: pika.BlockingConnection | None = None
_pika_channel = None


def _get_channel():
    """Retorna um canal pika reutilizável com reconexão automática."""
    global _pika_conn, _pika_channel
    with _pika_lock:
        try:
            if _pika_conn is None or _pika_conn.is_closed:
                _pika_conn = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        host=RABBITMQ_HOST,
                        heartbeat=120,
                        blocked_connection_timeout=60,
                    )
                )
                _pika_channel = _pika_conn.channel()
                _pika_channel.queue_declare(queue="fila_processamento", durable=True)
                _pika_channel.queue_declare(queue="fila_score", durable=True)
                logger.info("Conexão pika estabelecida (singleton)")

            if _pika_channel is None or _pika_channel.is_closed:
                _pika_channel = _pika_conn.channel()
                _pika_channel.queue_declare(queue="fila_processamento", durable=True)
                _pika_channel.queue_declare(queue="fila_score", durable=True)

            return _pika_channel
        except Exception as e:
            logger.error(f"Erro ao obter canal pika: {e}")
            _pika_conn = None
            _pika_channel = None
            raise


def publicar(fila: str, corpo: dict, max_retries: int = 3) -> bool:
    """Publica mensagem no RabbitMQ com retry automático."""
    for tentativa in range(max_retries):
        try:
            ch = _get_channel()
            ch.basic_publish(
                exchange='',
                routing_key=fila,
                properties=pika.BasicProperties(delivery_mode=2),
                body=json.dumps(corpo)
            )
            return True
        except Exception as e:
            logger.warning(f"Publicação falhou (tentativa {tentativa + 1}/{max_retries}): {e}")
            # Força reconexão
            global _pika_conn, _pika_channel
            with _pika_lock:
                _pika_conn = None
                _pika_channel = None
            if tentativa < max_retries - 1:
                time.sleep(0.5 * (tentativa + 1))

    logger.error(f"Falha definitiva ao publicar em '{fila}' após {max_retries} tentativas")
    return False


# ─── DIVISÃO DE MENSAGENS ────────────────────────────────────────────────────

def dividir_adaptativo(conteudo: str, cifra: str, limite: int = 300) -> list[str]:
    """
    Divide a mensagem em pacotes respeitando as fronteiras de palavras (morse)
    ou em tamanho fixo (César).
    """
    if not conteudo:
        return []

    if cifra == "&":
        # Para morse/binário: divide respeitando separadores de palavra (7 zeros)
        SEP = "0000000"
        palavras = conteudo.split(SEP)
        partes = []
        atual = ""

        for i, palavra in enumerate(palavras):
            if not palavra:
                continue

            # Só adiciona separador entre palavras (não no final)
            bloco = palavra + SEP if i < len(palavras) - 1 else palavra

            # Se um único bloco é maior que o limite, força divisão
            if len(bloco) > limite:
                if atual:
                    partes.append(atual)
                    atual = ""
                for j in range(0, len(bloco), limite):
                    partes.append(bloco[j:j + limite])
                continue

            if len(atual) + len(bloco) <= limite:
                atual += bloco
            else:
                if atual:
                    partes.append(atual)
                atual = bloco

        if atual:
            partes.append(atual)

        return partes if partes else [conteudo]

    # Para texto simples (César): divide respeitando fronteiras de palavras.
    # Cortar em bytes fixos causa colagem de palavras entre pacotes ("COREU" em vez de "COR EU").
    palavras_cesar = conteudo.split(" ")
    partes_cesar = []
    bloco_atual = ""
    for palavra in palavras_cesar:
        # Se adicionar essa palavra estoura o limite, fecha o bloco atual e começa um novo
        candidato = (bloco_atual + " " + palavra).strip() if bloco_atual else palavra
        if len(candidato) <= limite:
            bloco_atual = candidato
        else:
            if bloco_atual:
                partes_cesar.append(bloco_atual)
            # Palavra maior que o limite: força divisão (fallback)
            if len(palavra) > limite:
                for k in range(0, len(palavra), limite):
                    partes_cesar.append(palavra[k:k + limite])
                bloco_atual = ""
            else:
                bloco_atual = palavra
    if bloco_atual:
        partes_cesar.append(bloco_atual)
    return partes_cesar if partes_cesar else [conteudo]


# ─── ENDPOINTS PRINCIPAIS ────────────────────────────────────────────────────

@app.route("/receber", methods=["POST"])
def receber():
    """Recebe uma mensagem codificada, fragmenta e publica na fila."""
    dados = request.json

    # ── Validação de input ───────────────────────────────────────────────
    if not dados or not isinstance(dados, dict):
        return jsonify({"status": "erro", "msg": "Payload JSON inválido"}), 400

    mensagem = dados.get("mensagem", "")
    cifra = dados.get("cifra", "")

    if not mensagem or not isinstance(mensagem, str):
        return jsonify({"status": "erro", "msg": "Campo 'mensagem' vazio ou inválido"}), 400

    if cifra not in ("&", "$"):
        return jsonify({"status": "erro", "msg": "Campo 'cifra' deve ser '&' (morse) ou '$' (César)"}), 400

    message_id = str(uuid.uuid4())
    partes = dividir_adaptativo(mensagem, cifra)

    logger.info(f"Mensagem recebida: id={message_id[:8]}... pacotes={len(partes)} cifra={cifra}")

    for i, p in enumerate(partes):
        id_registro = inserir_registro(message_id, i, len(partes), p, cifra)
        marcar_enviado(id_registro, "worker_rabbit")

        mensagem_rabbit = {
            "id": id_registro,
            "message_id": message_id,
            "conteudo": p,
            "cifra": cifra,
            "ordem": i,
            "total": len(partes)
        }

        ok = publicar("fila_processamento", mensagem_rabbit)
        if not ok:
            logger.error(f"Falha ao publicar pacote {i + 1}/{len(partes)}")

    return jsonify({"status": "ok", "pacotes": len(partes), "message_id": message_id})


@app.route("/retorno", methods=["POST"])
def retorno():
    """Recebe o resultado processado de um pacote pelo worker."""
    dados = request.json

    if not dados or not isinstance(dados, dict):
        return jsonify({"status": "erro", "msg": "Payload inválido"}), 400

    id_pacote = dados.get("id")
    message_id = dados.get("message_id")
    resultado = dados.get("resultado", "")
    ordem = dados.get("ordem")
    total = dados.get("total")

    if None in (id_pacote, message_id, ordem, total):
        return jsonify({"status": "erro", "msg": "Campos obrigatórios faltando"}), 400

    atualizar_resultado(id_pacote, resultado)

    # ── Acumula resultados com lock ──────────────────────────────────────
    todos_prontos = False
    with _respostas_lock:
        if message_id not in respostas:
            respostas[message_id] = {}
            _respostas_ts[message_id] = time.time()

        respostas[message_id][ordem] = resultado

        if len(respostas[message_id]) == total:
            todos_prontos = True
            respostas.pop(message_id, None)
            _respostas_ts.pop(message_id, None)

    if todos_prontos:
        logger.info(f"✅ Todos os pacotes de msg={message_id[:8]}... processados!")
        ok = publicar("fila_score", {"message_id": message_id})
        if ok:
            logger.info(f"📊 Publicado na fila_score para scoring.")

    return jsonify({"status": "ok"})


# ─── ENDPOINTS DE CONSULTA ───────────────────────────────────────────────────

@app.route("/api/central", methods=["GET"])
def api_central():
    mensagens = buscar_mensagens_para_central()
    return jsonify({"status": "ok", "mensagens_decodificadas": mensagens})


@app.route("/api/status", methods=["GET"])
def api_status():
    pacotes = buscar_status_geral()
    return jsonify({"status": "ok", "pacotes": pacotes})


@app.route("/api/scores", methods=["GET"])
def api_scores():
    scores = buscar_scores()
    return jsonify({"status": "ok", "scores": scores})


@app.route("/api/health", methods=["GET"])
def api_health():
    """Health check com uptime e status do RabbitMQ."""
    uptime_s = round(time.time() - SERVER_START_TIME, 1)
    rabbit_ok = False
    try:
        conn = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=RABBITMQ_HOST,
                connection_attempts=1,
                retry_delay=0,
                socket_timeout=2
            )
        )
        conn.close()
        rabbit_ok = True
    except Exception:
        pass

    # Limpeza periódica de mensagens órfãs
    _cleanup_respostas()

    return jsonify({
        "status": "ok",
        "uptime_seconds": uptime_s,
        "rabbitmq": "online" if rabbit_ok else "offline",
        "porta": request.environ.get('SERVER_PORT', 5050),
    })


@app.route("/api/stats", methods=["GET"])
def api_stats():
    """Retorna estatísticas agregadas do sistema."""
    stats = buscar_estatisticas()
    return jsonify({"status": "ok", **stats})


@app.route("/api/mensagem/<message_id>", methods=["GET"])
def api_mensagem_detalhe(message_id):
    """Retorna todos os pacotes + score de uma mensagem específica."""
    pacotes = buscar_pacotes_da_mensagem(message_id)
    if not pacotes:
        return jsonify({"status": "erro", "msg": "Mensagem não encontrada"}), 404
    scores = buscar_scores()
    score = next((s for s in scores if s["message_id"] == message_id), None)
    texto = "".join([p.get("mensagem_decodificada") or "" for p in pacotes])
    return jsonify({
        "status": "ok",
        "message_id": message_id,
        "texto_completo": texto,
        "total_pacotes": len(pacotes),
        "pacotes": pacotes,
        "score": score,
    })


@app.route("/api/mensagens", methods=["GET"])
def api_mensagens():
    """Lista todas as mensagens decodificadas (sem alterar status)."""
    mensagens = buscar_mensagens_decodificadas()
    return jsonify({"status": "ok", "mensagens": mensagens})


@app.route("/api/exportar", methods=["GET"])
def api_exportar():
    """Exporta todos os dados (mensagens + scores) em JSON."""
    mensagens = buscar_mensagens_decodificadas()
    scores = buscar_scores()
    stats = buscar_estatisticas()
    return jsonify({
        "status": "ok",
        "exportado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "estatisticas": stats,
        "mensagens": mensagens,
        "scores": scores,
    })


@app.route("/api/limpar", methods=["POST"])
def api_limpar():
    """Limpa todo o banco de dados (reset)."""
    limpar_banco()
    with _respostas_lock:
        respostas.clear()
        _respostas_ts.clear()
    return jsonify({"status": "ok", "msg": "Banco de dados limpo com sucesso."})


@app.route("/api/mensagem/deletar/<message_id>", methods=["DELETE"])
def api_deletar_mensagem(message_id):
    """Remove uma mensagem específica do banco."""
    deletar_mensagem(message_id)
    return jsonify({"status": "ok", "msg": f"Mensagem {message_id} removida."})


@app.route("/api/validar/<message_id>", methods=["GET"])
def api_validar(message_id):
    """
    Valida o texto decodificado usando DP + dicionário português.
    Tenta reconstruir espaços perdidos entre palavras grudadas.
    """
    pacotes = buscar_pacotes_da_mensagem(message_id)
    if not pacotes:
        return jsonify({"status": "erro", "msg": "Mensagem não encontrada"}), 404

    # Junta pacotes com espaço para preservar fronteiras de palavras entre pacotes.
    # Sem o espaço, palavras do final/início de pacotes adjacentes se colam ("COREU" em vez de "COR EU").
    partes = [p.get("mensagem_decodificada") or "" for p in pacotes]
    texto_bruto = " ".join(parte.strip() for parte in partes if parte.strip())
    if not texto_bruto.strip():
        return jsonify({"status": "erro", "msg": "Mensagem vazia ou ainda processando"}), 400

    resultado = validar_mensagem(texto_bruto)
    return jsonify({"status": "ok", "message_id": message_id, **resultado})


# ─── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 5050

    criar_tabela()
    logger.info(f"✅ Banco de dados pronto. Iniciando servidor na porta {porta}...")
    app.run(port=porta, debug=False, host='0.0.0.0')