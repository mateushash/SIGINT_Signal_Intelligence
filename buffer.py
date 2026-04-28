from flask import Flask, request, jsonify
from flask_cors import CORS
from zdb import (
    criar_tabela, inserir_registro, marcar_enviado, atualizar_resultado,
    buscar_mensagens_para_central, buscar_status_geral, buscar_scores
)
import uuid
import pika
import json

RABBITMQ_HOST = "localhost"

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


def dividir_adaptativo(binario, limite=300):
    palavras = binario.split("0000000")
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


@app.route("/receber", methods=["POST"])
def receber():
    dados = request.json
    mensagem = dados["mensagem"]
    cifra = dados["cifra"]
    message_id = str(uuid.uuid4())

    partes = dividir_adaptativo(mensagem)
    print(f"\n[Buffer] Mensagem recebida com {len(partes)} pacotes")

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


if __name__ == "__main__":
    criar_tabela()
    print("[Buffer] ✅ Banco de dados pronto. Iniciando servidor na porta 5000...")
    app.run(port=5050, debug=False)