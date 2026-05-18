"""
worker_rabbit.py — Semana 3 e 4
================================
Worker REAL que consome da fila RabbitMQ 'fila_processamento'.
Decodifica binário → Morse → Texto e devolve o resultado ao buffer via HTTP.

Como usar:
    python worker_rabbit.py

Pré-requisitos:
    - RabbitMQ rodando no Docker (porta 5672)
    - Buffer (buffer.py) rodando na porta 5000
    - pip install pika requests
"""

import pika
import json
import requests
import time

# ─── CONFIGURAÇÕES ────────────────────────────────────────────────────────────
RABBITMQ_HOST  = "localhost"
RABBITMQ_PORT  = 5672
FILA_ENTRADA   = "fila_processamento"
BUFFER_URL     = "http://localhost:5050/retorno"

# ─── TABELA MORSE ─────────────────────────────────────────────────────────────
MORSE_REV = {
    '.-':   'A', '-...': 'B', '-.-.': 'C', '-..':  'D',
    '.':    'E', '..-.': 'F', '--.':  'G', '....': 'H',
    '..':   'I', '.---': 'J', '-.-':  'K', '.-..': 'L',
    '--':   'M', '-.':   'N', '---':  'O', '.--.': 'P',
    '--.-': 'Q', '.-.':  'R', '...':  'S', '-':    'T',
    '..-':  'U', '...-': 'V', '.--':  'W', '-..-': 'X',
    '-.--': 'Y', '--..': 'Z',
}

# Estado local do stream binário (persistido entre pacotes do mesmo worker)
_buffer_binario = ""
_buffer_morse   = ""


def resetar_buffers():
    """Reseta os buffers internos (chame ao iniciar uma nova mensagem)."""
    global _buffer_binario, _buffer_morse
    _buffer_binario = ""
    _buffer_morse   = ""


def processar_stream_binario(binario: str) -> str:
    """
    Converte um fragmento de binário em morse parcial (usa buffer global
    para lidar com fragmentos que cortam no meio de um símbolo).
    """
    global _buffer_binario
    _buffer_binario += binario

    resultado = ""
    i = 0
    while i < len(_buffer_binario):
        if _buffer_binario[i:i+7] == "0000000":   # separador de palavra
            resultado += " "
            i += 7
        elif _buffer_binario[i:i+3] == "000":      # separador de letra
            resultado += "|"
            i += 3
        elif _buffer_binario[i:i+3] == "111":      # traço morse
            resultado += "-"
            i += 3
        elif _buffer_binario[i] == "1":             # ponto morse
            resultado += "."
            i += 1
        else:                                       # zero avulso (separador de símbolo)
            i += 1

    _buffer_binario = _buffer_binario[i:]
    return resultado


def morse_stream_para_texto(morse_stream: str) -> str:
    """
    Converte morse parcial (com '|' como separador de letras e ' ' como
    separador de palavras) em texto legível.
    """
    global _buffer_morse
    _buffer_morse += morse_stream

    partes = _buffer_morse.split("|")
    resultado = ""

    for parte in partes[:-1]:           # a última parte pode estar incompleta
        if parte == " ":                # separador de palavra (espaço vindo do binário 0000000)
            resultado += " "
            continue
            
        parte = parte.strip()
        if parte == "":
            continue

        if parte in MORSE_REV:
            resultado += MORSE_REV[parte]
        else:
            resultado += "?"            # símbolo não reconhecido

    _buffer_morse = partes[-1]          # guarda o fragmento incompleto
    return resultado


def decifrar_cesar(texto: str, deslocamento: int = 3) -> str:
    texto = texto.upper()
    resultado = ""
    for letra in texto:
        if letra == " ":
            resultado += " "
        elif "A" <= letra <= "Z":
            codigo = ord(letra) - ord("A")
            codigo = (codigo - deslocamento) % 26
            resultado += chr(codigo + ord("A"))
        else:
            resultado += letra
    return resultado


def processar_mensagem(ch, method, properties, body):
    """
    Callback chamado pelo pika para cada mensagem consumida da fila.
    """
    global _buffer_binario, _buffer_morse

    try:
        dados = json.loads(body)
        id_pacote  = dados["id"]
        message_id = dados["message_id"]
        conteudo   = dados["conteudo"]
        cifra      = dados.get("cifra", "&")
        ordem      = dados["ordem"]
        total      = dados["total"]

        print(f"\n[Worker] ▶ Pacote {ordem+1}/{total} | msg={message_id[:8]}... | cifra={cifra}")

        # Se é o primeiro pacote de uma mensagem, reseta os buffers
        if ordem == 0:
            resetar_buffers()

        if cifra == "$":
            # 1. Descriptografa César diretamente do texto recebido
            texto = decifrar_cesar(conteudo)
            print(f"[Worker] ✅ Descriptografado César: '{texto}'")
        else:
            # 1. Binário → morse parcial
            morse_parcial = processar_stream_binario(conteudo)

            # 2. Morse parcial → texto
            texto = morse_stream_para_texto(morse_parcial)

            # Se é o último pacote, força a leitura do que ficou no buffer morse
            if ordem == total - 1:
                restante = _buffer_morse.strip()
                if restante and restante in MORSE_REV:
                    texto += MORSE_REV[restante]
                _buffer_morse = ""

            print(f"[Worker] ✅ Decodificado: '{texto}'")

        # 3. Devolve resultado ao Buffer via HTTP
        resposta = requests.post(BUFFER_URL, json={
            "id":         id_pacote,
            "message_id": message_id,
            "resultado":  texto,
            "ordem":      ordem,
            "total":      total,
        }, timeout=10)

        if resposta.status_code == 200:
            print(f"[Worker] 📤 Resultado enviado ao Buffer com sucesso.")
        else:
            print(f"[Worker] ⚠️  Buffer retornou {resposta.status_code}")

        # Confirma o processamento da mensagem para o RabbitMQ (ACK)
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[Worker] ❌ Erro ao processar pacote: {e}")
        # NACK sem requeue para não travar a fila em caso de erro permanente
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def iniciar_worker():
    """Conecta ao RabbitMQ e começa a consumir a fila de processamento."""
    while True:
        try:
            print("=" * 55)
            print("      WORKER RABBIT — INICIANDO CONSUMIDOR         ")
            print("=" * 55)
            print(f"[Worker] Conectando ao RabbitMQ em {RABBITMQ_HOST}:{RABBITMQ_PORT}...")

            conexao = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    port=RABBITMQ_PORT,
                    heartbeat=600,
                    blocked_connection_timeout=300,
                )
            )
            canal = conexao.channel()

            # Garante que a fila existe (idempotente)
            canal.queue_declare(queue=FILA_ENTRADA, durable=True)

            # Processa 1 mensagem por vez (fair dispatch)
            canal.basic_qos(prefetch_count=1)

            canal.basic_consume(
                queue=FILA_ENTRADA,
                on_message_callback=processar_mensagem,
            )

            print(f"[Worker] ✅ Conectado! Aguardando mensagens na fila '{FILA_ENTRADA}'...")
            print("[Worker] Pressione CTRL+C para encerrar.\n")

            canal.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            print("[Worker] ⚠️  Falha na conexão. Tentando novamente em 5s...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n[Worker] Encerrando...")
            break
        except Exception as e:
            print(f"[Worker] ❌ Erro inesperado: {e}. Reconectando em 5s...")
            time.sleep(5)


if __name__ == "__main__":
    iniciar_worker()
