from flask import Flask, request, jsonify
from zdb import *
from datetime import datetime  
import uuid
import pika
import json

#Configura conexão com o RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.queue_declare(queue='fila_processamento')

WORKER_URL = "http://localhost:5001/processar"

app = Flask(__name__)

respostas = {}


#Funcao para dividir em pacotes quando alcanca o limite apenas.
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

#Funcao de receber a mensagem pelo sending test, incorporar no BD os pacotes, enviando-os pro workjer
@app.route("/receber", methods=["POST"])
def receber():

    dados = request.json

    mensagem = dados["mensagem"]
    cifra = dados["cifra"]

    message_id = str(uuid.uuid4())  
    

    partes = dividir_adaptativo(mensagem)

    print(f"\nMensagem recebida com {len(partes)} pacotes\n")

    for i, p in enumerate(partes):
       
        id_registro = inserir_registro(message_id, i, len(partes), p, cifra)

        print(f"Enviando pacote {i+1}/{len(partes)}")

        try:
            marcar_enviado(id_registro, "worker1")

            
            mensagem = {
                "id": id_registro,
                "message_id": message_id,
                "conteudo": p,
                "cifra": cifra,
                "ordem": i,
                "total": len(partes)
            }

            channel.basic_publish(
                exchange='',
                routing_key='fila_processamento',
                body=json.dumps(mensagem)
            )
        except:
            print("Erro ao enviar para fila")

    return jsonify({
    "status": "ok",
    "pacotes": len(partes)
})

#Funcao retorno do worker, marcando como recebido o pacote na linha no BD.
@app.route("/retorno", methods=["POST"])
def retorno():
    dados = request.json

    id_pacote = dados["id"]
    message_id = dados["message_id"]
    resultado = dados["resultado"]
    ordem = dados["ordem"]
    total = dados["total"]

    print(f"Recebido retorno pacote {ordem+1}/{total}")
    print(f"DEBUG pacote {ordem}: '{resultado}'")

    atualizar_resultado(id_pacote, resultado)
    
    if message_id not in respostas:
        respostas[message_id] = {}

    respostas[message_id][ordem] = resultado

    if len(respostas[message_id]) == total:
        print("\n TODOS PACOTES PROCESSADOS!")

        mensagem_final = ""

        for i in range(total):
            mensagem_final += respostas[message_id][i] + " "

        print("\nMensagem final:")
        print(mensagem_final)


        respostas.pop(message_id)

    return {"status": "ok"}

#Adicap a central pra realizar apenas a operacao de ler as mensagens decodificadas
@app.route("/api/central", methods=["GET"])
def api_central():
    # Chama la no zdb
    mensagens = buscar_mensagens_para_central()
    return jsonify({"status": "ok", "mensagens_decodificadas": mensagens})

if __name__ == "__main__":
    criar_tabela()
    app.run(port=5000)