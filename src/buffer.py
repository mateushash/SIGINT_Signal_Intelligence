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
from validador import validar_mensagem

RABBITMQ_HOST = "localhost"
SERVER_START_TIME = time.time()

app = Flask(__name__)
CORS(app)

respostas = {}


def publicar(fila: str, corpo: dict):
    """Cria uma conexão pika, publica e fecha. Thread-safe para o Flask."""
    try:
        conn = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=60)
        )
        ch = conn.channel()
        ch.queue_declare(queue=fila, durable=True)
        ch.basic_publish(
            exchange='',
            routing_key=fila,
            properties=pika.BasicProperties(delivery_mode=2),
            body=json.dumps(corpo)
        )
        conn.close()
        return True
    except Exception as e:
        print(f"[Buffer] ⚠️  Erro ao publicar em '{fila}': {e}")
        return False


def dividir_adaptativo(conteudo, cifra, limite=300):
    if cifra == "&":
        palavras = conteudo.split("0000000")
        partes = []
        atual = ""
        for palavra in palavras:
            bloco = palavra + "0000000"
            if len(bloco) > limite:
                for i in range(0, len(bloco), limite):
                    partes.append(bloco[i:i+limite])
                continue
            if len(atual) + len(bloco) <= limite:
                atual += bloco
            else:
                partes.append(atual)
                atual = bloco
        if atual:
            partes.append(atual)
        return partes

    # Para texto simples (César), divide em pedaços de tamanho fixo
    return [conteudo[i:i+limite] for i in range(0, len(conteudo), limite)]


@app.route("/receber", methods=["POST"])
def receber():
    dados = request.json
    mensagem = dados["mensagem"]
    cifra = dados["cifra"]
    message_id = str(uuid.uuid4())

    partes = dividir_adaptativo(mensagem, cifra)
    print(f"\n[Buffer] Mensagem recebida com {len(partes)} pacotes (cifra={cifra})")

    for i, p in enumerate(partes):
        id_registro = inserir_registro(message_id, i, len(partes), p, cifra)
        marcar_enviado(id_registro, "worker_rabbit")
        print(f"[Buffer] Enviando pacote {i+1}/{len(partes)} para fila...")

        mensagem_rabbit = {
            "id": id_registro,
            "message_id": message_id,
            "conteudo": p,
            "cifra": cifra,
            "ordem": i,
            "total": len(partes)
        }
        publicar("fila_processamento", mensagem_rabbit)

    return jsonify({"status": "ok", "pacotes": len(partes)})


@app.route("/retorno", methods=["POST"])
def retorno():
    dados = request.json
    id_pacote  = dados["id"]
    message_id = dados["message_id"]
    resultado  = dados["resultado"]
    ordem      = dados["ordem"]
    total      = dados["total"]

    atualizar_resultado(id_pacote, resultado)

    if message_id not in respostas:
        respostas[message_id] = {}
    respostas[message_id][ordem] = resultado

    if len(respostas[message_id]) == total:
        print(f"\n[Buffer] ✅ Todos os pacotes de msg={message_id[:8]}... processados!")
        respostas.pop(message_id)
        ok = publicar("fila_score", {"message_id": message_id})
        if ok:
            print("[Buffer] 📊 Publicado na fila_score para scoring.")

    return jsonify({"status": "ok"})


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


# ─── ENDPOINTS SEMANA 5 e 6 ────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def api_health():
    """Health check com uptime e status do RabbitMQ."""
    uptime_s = round(time.time() - SERVER_START_TIME, 1)
    rabbit_ok = False
    try:
        conn = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST, connection_attempts=1, retry_delay=0, socket_timeout=2)
        )
        conn.close()
        rabbit_ok = True
    except Exception:
        pass
    return jsonify({
        "status": "ok",
        "uptime_seconds": uptime_s,
        "rabbitmq": "online" if rabbit_ok else "offline",
        "porta": 5050,
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
    return jsonify({"status": "ok", "msg": "Banco de dados limpo com sucesso."})


@app.route("/api/mensagem/deletar/<message_id>", methods=["DELETE"])
def api_deletar_mensagem(message_id):
    """Remove uma mensagem específica do banco."""
    deletar_mensagem(message_id)
    return jsonify({"status": "ok", "msg": f"Mensagem {message_id} removida."})




@app.route("/api/validar/<message_id>", methods=["GET"])
def api_validar(message_id):
    """
    Valida o texto decodificado usando API de dicionario portugues.
    Tenta reconstruir espacos perdidos entre palavras grudadas.
    """
    pacotes = buscar_pacotes_da_mensagem(message_id)
    if not pacotes:
        return jsonify({"status": "erro", "msg": "Mensagem nao encontrada"}), 404

    texto_bruto = "".join([p.get("mensagem_decodificada") or "" for p in pacotes])
    if not texto_bruto.strip():
        return jsonify({"status": "erro", "msg": "Mensagem vazia ou ainda processando"}), 400

    resultado = validar_mensagem(texto_bruto)
    return jsonify({"status": "ok", "message_id": message_id, **resultado})

if __name__ == "__main__":
    import sys
    # Permite passar a porta via linha de comando: python3 buffer.py 5051
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 5050
    
    criar_tabela()
    print(f"[Buffer] ✅ Banco de dados pronto. Iniciando servidor na porta {porta}...")
    app.run(port=porta, debug=False, host='0.0.0.0')