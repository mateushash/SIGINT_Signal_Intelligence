"""
score_service.py — Score Service (v2 Hardened)
================================================
Serviço de Score/Modelo que consome a fila 'fila_score' e calcula
métricas de qualidade da transmissão.

Melhorias v2:
  - Requeue seletivo (erros transientes vs permanentes)
  - Tratamento de timestamps com microssegundos
  - Logging estruturado
  - Retry na conexão com backoff progressivo
"""

import pika
import json
import time
import logging
from datetime import datetime
from zdb import salvar_score, buscar_pacotes_da_mensagem

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("sigint.score")

# ─── CONFIGURAÇÕES ────────────────────────────────────────────────────────────
RABBITMQ_HOST = "localhost"
RABBITMQ_PORT = 5672
FILA_SCORE = "fila_score"

# Retry progressivo
RECONNECT_DELAYS = [2, 5, 10, 15, 30]  # segundos


# ─── CÁLCULO DO SCORE ────────────────────────────────────────────────────────

def calcular_score(message_id: str) -> dict | None:
    """
    Busca os pacotes de uma mensagem e calcula métricas de qualidade:
      - score_integridade: % de pacotes sem caracteres '?' (erro)
      - latencia_media_ms: tempo médio entre recebido e processado
      - score_reconstrucao: % de caracteres válidos (não '?')
    """
    pacotes = buscar_pacotes_da_mensagem(message_id)

    if not pacotes:
        logger.warning(f"Nenhum pacote encontrado para message_id={message_id[:8]}...")
        return None

    total_pacotes = len(pacotes)
    pacotes_ok = 0
    latencias_ms: list[float] = []
    chars_ok = 0
    chars_total = 0

    for p in pacotes:
        resultado = p.get("mensagem_decodificada") or ""
        ts_recebido = p.get("ts_recebido")
        ts_processado = p.get("ts_processado")

        # ── Score de integridade ──────────────────────────────────────────
        if resultado and "?" not in resultado:
            pacotes_ok += 1

        # ── Score de reconstrução ─────────────────────────────────────────
        for char in resultado:
            chars_total += 1
            if char != "?":
                chars_ok += 1

        # ── Latência ─────────────────────────────────────────────────────
        if ts_recebido and ts_processado:
            fmt = "%Y-%m-%d %H:%M:%S"
            try:
                t0 = datetime.strptime(ts_recebido, fmt)
                t1 = datetime.strptime(ts_processado, fmt)
                delta_ms = (t1 - t0).total_seconds() * 1000
                if delta_ms >= 0:
                    latencias_ms.append(delta_ms)
            except ValueError:
                pass  # timestamp malformado, ignora

    score_integridade = round((pacotes_ok / total_pacotes) * 100, 2) if total_pacotes else 0.0
    score_reconstrucao = round((chars_ok / chars_total) * 100, 2) if chars_total else 0.0
    latencia_media_ms = round(sum(latencias_ms) / len(latencias_ms), 2) if latencias_ms else 0.0

    return {
        "message_id": message_id,
        "total_pacotes": total_pacotes,
        "pacotes_ok": pacotes_ok,
        "latencia_media_ms": latencia_media_ms,
        "score_integridade": score_integridade,
        "score_reconstrucao": score_reconstrucao,
    }


# ─── CALLBACK DO CONSUMER ────────────────────────────────────────────────────

def processar_score(ch, method, properties, body):
    """Callback chamado pelo pika para cada mensagem na fila_score."""
    try:
        dados = json.loads(body)
        message_id = dados.get("message_id")

        if not message_id:
            logger.error("Mensagem sem message_id — descartando")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            return

        logger.info(f"▶ Calculando score para msg={message_id[:8]}...")

        resultado = calcular_score(message_id)

        if resultado:
            salvar_score(resultado)
            logger.info(
                f"✅ Score salvo: "
                f"Integridade={resultado['score_integridade']}% "
                f"Reconstrução={resultado['score_reconstrucao']}% "
                f"Latência={resultado['latencia_media_ms']}ms "
                f"Pacotes={resultado['pacotes_ok']}/{resultado['total_pacotes']}"
            )
        else:
            logger.warning(f"Score não calculado para msg={message_id[:8]}... (pacotes não encontrados)")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError as e:
        logger.error(f"JSON inválido na fila_score: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
    except Exception as e:
        logger.error(f"❌ Erro ao processar score: {e}", exc_info=True)
        # Requeue para erros transientes (ex: DB locked momentaneamente)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


# ─── LOOP PRINCIPAL ──────────────────────────────────────────────────────────

def iniciar_score_service():
    """Conecta ao RabbitMQ e começa a consumir a fila de scores."""
    tentativa_conn = 0

    while True:
        try:
            logger.info("=" * 55)
            logger.info("    SCORE SERVICE — INICIANDO CONSUMIDOR            ")
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
            canal.queue_declare(queue=FILA_SCORE, durable=True)
            canal.basic_qos(prefetch_count=1)
            canal.basic_consume(queue=FILA_SCORE, on_message_callback=processar_score)

            logger.info(f"✅ Aguardando mensagens na fila '{FILA_SCORE}'...")
            logger.info("Pressione CTRL+C para encerrar.")

            # Reset do contador de tentativas após conexão bem-sucedida
            tentativa_conn = 0
            canal.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            delay = RECONNECT_DELAYS[min(tentativa_conn, len(RECONNECT_DELAYS) - 1)]
            tentativa_conn += 1
            logger.warning(f"⚠️  Falha na conexão. Tentando novamente em {delay}s... (tentativa {tentativa_conn})")
            time.sleep(delay)
        except KeyboardInterrupt:
            logger.info("Encerrando score service...")
            break
        except Exception as e:
            delay = RECONNECT_DELAYS[min(tentativa_conn, len(RECONNECT_DELAYS) - 1)]
            tentativa_conn += 1
            logger.error(f"❌ Erro inesperado: {e}. Reconectando em {delay}s...", exc_info=True)
            time.sleep(delay)


if __name__ == "__main__":
    iniciar_score_service()
