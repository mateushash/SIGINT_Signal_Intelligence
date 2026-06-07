"""
worker_rabbit.py — Worker Service (v2 Hardened)
=================================================
Worker que consome da fila RabbitMQ 'fila_processamento'.
Decodifica binário → Morse → Texto (ou César → Texto)
e devolve o resultado ao buffer via HTTP.

Melhorias v2:
  - Buffers per-message (elimina race conditions)
  - Retry com backoff exponencial no HTTP POST
  - Cleanup automático de buffers antigos
  - Logging estruturado
  - Tratamento robusto de erros com requeue seletivo
"""

import pika
import json
import requests
import time
import logging
import os
from datetime import datetime

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("sigint.worker")

# ─── CONFIGURAÇÕES ────────────────────────────────────────────────────────────
RABBITMQ_HOST = os.getenv("SIGINT_RABBITMQ_HOST", "100.107.140.27")  # Tailscale IP da máquina do RabbitMQ
RABBITMQ_PORT = 5672
FILA_ENTRADA = "fila_processamento"
BUFFER_URL = os.getenv("SIGINT_BUFFER_URL", "http://100.107.140.27:5050/retorno")

# Retry config
MAX_RETRIES = 5
RETRY_BASE_DELAY = 0.5  # segundos

# ─── TABELA MORSE ─────────────────────────────────────────────────────────────
MORSE_REV: dict[str, str] = {
    '.-':   'A', '-...': 'B', '-.-.': 'C', '-..':  'D',
    '.':    'E', '..-.': 'F', '--.':  'G', '....': 'H',
    '..':   'I', '.---': 'J', '-.-':  'K', '.-..': 'L',
    '--':   'M', '-.':   'N', '---':  'O', '.--.': 'P',
    '--.-': 'Q', '.-.':  'R', '...':  'S', '-':    'T',
    '..-':  'U', '...-': 'V', '.--':  'W', '-..-': 'X',
    '-.--': 'Y', '--..': 'Z',
}

# ─── BUFFERS PER-MESSAGE (elimina race conditions) ───────────────────────────
_message_buffers: dict[str, dict] = {}
_BUFFER_TTL = 300  # 5 minutos TTL para limpeza


def _get_buffers(message_id: str) -> dict:
    """Retorna buffers dedicados para uma mensagem específica."""
    if message_id not in _message_buffers:
        _message_buffers[message_id] = {
            "binario": "",
            "morse": "",
            "resultados": {},
            "criado_em": time.time(),
        }
    return _message_buffers[message_id]


def _cleanup_buffers():
    """Remove buffers de mensagens antigas para evitar memory leak."""
    agora = time.time()
    expirados = [
        mid for mid, buf in _message_buffers.items()
        if agora - buf["criado_em"] > _BUFFER_TTL
    ]
    for mid in expirados:
        del _message_buffers[mid]
    if expirados:
        logger.info(f"Cleanup: {len(expirados)} buffers de mensagens expirados removidos")


def _release_buffers(message_id: str):
    """Libera buffers de uma mensagem após processamento completo."""
    _message_buffers.pop(message_id, None)


# ─── DECODIFICAÇÃO BINÁRIO → MORSE → TEXTO ──────────────────────────────────

def processar_stream_binario(binario: str, message_id: str) -> str:
    """
    Converte um fragmento de binário em morse parcial.
    Usa buffer per-message para lidar com fragmentos cortados.

    Protocolo binário:
      - '1'   = ponto morse (.)
      - '111' = traço morse (-)
      - '0'   = separador intra-símbolo
      - '000' = separador de letras (|)
      - '0000000' = separador de palavras (espaço)
    """
    buf = _get_buffers(message_id)
    buf["binario"] += binario

    resultado = ""
    data = buf["binario"]
    i = 0

    while i < len(data):
        remaining = len(data) - i

        # Separador de palavra (7 zeros) — precisa ter certeza que não é prefixo
        if remaining >= 7 and data[i:i + 7] == "0000000":
            resultado += " "
            i += 7
        # Separador de letra (3 zeros) — mas só se não é parte de 7 zeros
        elif remaining >= 3 and data[i:i + 3] == "000":
            # Verifica se não é prefixo de separador de palavra
            if remaining < 7 or data[i:i + 7] != "0000000":
                resultado += "|"
                i += 3
            else:
                # É prefixo de separador de palavra, mas precisamos de mais dados
                break
        # Traço morse (3 uns)
        elif remaining >= 3 and data[i:i + 3] == "111":
            resultado += "-"
            i += 3
        # Ponto morse (1 um)
        elif data[i] == "1":
            resultado += "."
            i += 1
        # Zero avulso (separador intra-símbolo)
        elif data[i] == "0":
            # Pode ser separador ou parte de um separador maior
            # Se temos menos de 3 chars restantes, pode ser incompleto
            if remaining < 3:
                break  # Guarda no buffer para o próximo pacote
            i += 1
        else:
            # Caractere inesperado, pula
            logger.warning(f"Caractere inesperado no binário: '{data[i]}' na pos {i}")
            i += 1

    # Guarda apenas o que não foi processado
    buf["binario"] = data[i:]
    return resultado


def morse_stream_para_texto(morse_stream: str, message_id: str) -> str:
    """
    Converte morse parcial em texto legível.
    '|' separa letras, ' ' separa palavras.
    """
    buf = _get_buffers(message_id)
    buf["morse"] += morse_stream

    partes = buf["morse"].split("|")
    resultado = ""

    # Processa todas as partes exceto a última (que pode estar incompleta)
    for parte in partes[:-1]:
        if " " in parte:
            # Pode ter espaços (separadores de palavra)
            subpartes = parte.split(" ")
            for j, sub in enumerate(subpartes):
                sub = sub.strip()
                if sub == "":
                    if j > 0:
                        resultado += " "
                    continue
                if sub in MORSE_REV:
                    resultado += MORSE_REV[sub]
                else:
                    resultado += "?"
                if j < len(subpartes) - 1:
                    resultado += " "
        else:
            parte = parte.strip()
            if parte == "":
                continue
            if parte in MORSE_REV:
                resultado += MORSE_REV[parte]
            else:
                resultado += "?"

    # Guarda o fragmento incompleto
    buf["morse"] = partes[-1]
    return resultado


def finalizar_morse(message_id: str) -> str:
    """Processa o que sobrou no buffer morse (último pacote)."""
    buf = _get_buffers(message_id)
    restante = buf["morse"].strip()
    resultado = ""

    if restante:
        if restante in MORSE_REV:
            resultado = MORSE_REV[restante]
        elif " " in restante:
            for sub in restante.split(" "):
                sub = sub.strip()
                if sub and sub in MORSE_REV:
                    resultado += MORSE_REV[sub]
                elif sub:
                    resultado += "?"
        elif restante:
            resultado = "?"
        buf["morse"] = ""

    return resultado


# ─── DECODIFICAÇÃO CÉSAR ──────────────────────────────────────────────────────

def decifrar_cesar(texto: str, deslocamento: int = 3) -> str:
    """Decifra texto cifrado com Cifra de César."""
    texto = texto.upper()
    resultado = []
    for letra in texto:
        if letra == " ":
            resultado.append(" ")
        elif "A" <= letra <= "Z":
            codigo = ord(letra) - ord("A")
            codigo = (codigo - deslocamento) % 26
            resultado.append(chr(codigo + ord("A")))
        else:
            resultado.append(letra)
    return "".join(resultado)


# ─── HTTP POST COM RETRY ─────────────────────────────────────────────────────

def enviar_resultado(payload: dict) -> bool:
    """Envia resultado ao buffer com retry e backoff exponencial."""
    for tentativa in range(MAX_RETRIES):
        try:
            resposta = requests.post(BUFFER_URL, json=payload, timeout=10)
            if resposta.status_code == 200:
                return True
            logger.warning(f"Buffer retornou {resposta.status_code} (tentativa {tentativa + 1})")
        except requests.exceptions.ConnectionError:
            logger.warning(f"Buffer offline (tentativa {tentativa + 1}/{MAX_RETRIES})")
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout ao enviar para buffer (tentativa {tentativa + 1}/{MAX_RETRIES})")
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar: {e}")

        if tentativa < MAX_RETRIES - 1:
            delay = RETRY_BASE_DELAY * (2 ** tentativa)
            logger.info(f"Aguardando {delay:.1f}s antes de retry...")
            time.sleep(delay)

    logger.error("Falha definitiva ao enviar resultado ao buffer")
    return False


# ─── CALLBACK PRINCIPAL ──────────────────────────────────────────────────────

def processar_mensagem(ch, method, properties, body):
    """Callback chamado pelo pika para cada mensagem consumida da fila."""
    try:
        dados = json.loads(body)
        id_pacote = dados["id"]
        message_id = dados["message_id"]
        conteudo = dados["conteudo"]
        cifra = dados.get("cifra", "&")
        ordem = dados["ordem"]
        total = dados["total"]

        logger.info(f"▶ Pacote {ordem + 1}/{total} | msg={message_id[:8]}... | cifra={cifra}")

        if cifra == "$":
            # Descriptografa César diretamente
            texto = decifrar_cesar(conteudo)
            logger.info(f"✅ César: '{texto[:60]}...'")
        else:
            # 1. Binário → morse parcial
            morse_parcial = processar_stream_binario(conteudo, message_id)

            # 2. Morse parcial → texto
            texto = morse_stream_para_texto(morse_parcial, message_id)

            # 3. Se é o último pacote, força leitura do buffer residual
            if ordem == total - 1:
                texto += finalizar_morse(message_id)
                _release_buffers(message_id)

            logger.info(f"✅ Morse: '{texto[:60]}...'")

        # 4. Envia resultado ao buffer com retry
        payload = {
            "id": id_pacote,
            "message_id": message_id,
            "resultado": texto,
            "ordem": ordem,
            "total": total,
        }

        sucesso = enviar_resultado(payload)
        if sucesso:
            logger.info("📤 Resultado enviado ao Buffer com sucesso.")
            ch.basic_ack(delivery_tag=method.delivery_tag)
        else:
            # Requeue para tentar novamente depois (erro transiente)
            logger.error("Falha ao enviar ao buffer — requeue da mensagem")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    except json.JSONDecodeError as e:
        logger.error(f"JSON inválido na fila: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except KeyError as e:
        logger.error(f"Campo obrigatório ausente no payload: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"❌ Erro ao processar pacote: {e}", exc_info=True)
        # Requeue em caso de erro inesperado (pode ser transiente)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    # Limpeza periódica de buffers antigos
    if time.time() % 60 < 2:
        _cleanup_buffers()


# ─── LOOP PRINCIPAL ──────────────────────────────────────────────────────────

def iniciar_worker():
    """Conecta ao RabbitMQ e começa a consumir a fila de processamento."""
    while True:
        try:
            logger.info("=" * 55)
            logger.info("      WORKER RABBIT — INICIANDO CONSUMIDOR         ")
            logger.info("=" * 55)
            logger.info(f"Conectando ao RabbitMQ em {RABBITMQ_HOST}:{RABBITMQ_PORT}...")

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

            logger.info(f"✅ Conectado! Aguardando mensagens na fila '{FILA_ENTRADA}'...")
            logger.info("Pressione CTRL+C para encerrar.")

            canal.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            logger.warning("⚠️  Falha na conexão com RabbitMQ. Tentando novamente em 5s...")
            time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Encerrando worker...")
            break
        except Exception as e:
            logger.error(f"❌ Erro inesperado: {e}. Reconectando em 5s...", exc_info=True)
            time.sleep(5)


if __name__ == "__main__":
    iniciar_worker()
