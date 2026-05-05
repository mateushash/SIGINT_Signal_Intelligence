"""
score_service.py — Semana 3 e 4
=================================
Serviço de Score/Modelo.

Consome a fila RabbitMQ 'fila_score' (publicada pelo buffer.py quando
todos os pacotes de uma mensagem chegam processados) e calcula métricas
de qualidade da transmissão, salvando os resultados no banco SQLite.

Métricas calculadas:
  - score_integridade  : % de pacotes que chegaram sem erro (não contêm '?')
  - latencia_media_ms  : tempo médio (ms) entre ts_recebido e ts_processado
  - score_reconstrucao : % de caracteres decodificados que NÃO são '?'
  - total_pacotes      : quantidade de pacotes da mensagem
  - pacotes_ok         : pacotes que passaram sem caractere '?' no resultado

Como usar:
    python score_service.py

Pré-requisitos:
    - RabbitMQ rodando no Docker (porta 5672)
    - buffer.py rodando na porta 5000
    - pip install pika
"""

import pika
import json
import time
from zdb import salvar_score, buscar_pacotes_da_mensagem


# ─── CONFIGURAÇÕES ────────────────────────────────────────────────────────────
RABBITMQ_HOST = "localhost"
RABBITMQ_PORT = 5672
FILA_SCORE    = "fila_score"


# ─── CÁLCULO DO SCORE ─────────────────────────────────────────────────────────

def calcular_score(message_id: str) -> dict:
    """
    Busca os pacotes de uma mensagem no banco e calcula as métricas de
    qualidade da transmissão.

    Retorna um dicionário com todos os campos do score.
    """
    pacotes = buscar_pacotes_da_mensagem(message_id)

    if not pacotes:
        print(f"[Score] ⚠️  Nenhum pacote encontrado para message_id={message_id[:8]}...")
        return None

    total_pacotes   = len(pacotes)
    pacotes_ok      = 0
    latencias_ms    = []
    chars_ok        = 0
    chars_total     = 0

    for p in pacotes:
        resultado     = p.get("mensagem_decodificada") or ""
        ts_recebido   = p.get("ts_recebido")
        ts_processado = p.get("ts_processado")

        # ── Score de integridade ──────────────────────────────────────────────
        # Pacote OK = resultado não vazio e sem caractere '?' (símbolo inválido)
        if resultado and "?" not in resultado:
            pacotes_ok += 1

        # ── Score de reconstrução ─────────────────────────────────────────────
        for char in resultado:
            chars_total += 1
            if char != "?":
                chars_ok += 1

        # ── Latência ─────────────────────────────────────────────────────────
        if ts_recebido and ts_processado:
            from datetime import datetime
            fmt = "%Y-%m-%d %H:%M:%S"
            try:
                t0 = datetime.strptime(ts_recebido,   fmt)
                t1 = datetime.strptime(ts_processado, fmt)
                delta_ms = (t1 - t0).total_seconds() * 1000
                if delta_ms >= 0:
                    latencias_ms.append(delta_ms)
            except ValueError:
                pass  # timestamp malformado, ignora

    score_integridade  = round((pacotes_ok  / total_pacotes) * 100, 2) if total_pacotes else 0.0
    score_reconstrucao = round((chars_ok    / chars_total)   * 100, 2) if chars_total   else 0.0
    latencia_media_ms  = round(sum(latencias_ms) / len(latencias_ms),  2) if latencias_ms else 0.0

    return {
        "message_id":        message_id,
        "total_pacotes":     total_pacotes,
        "pacotes_ok":        pacotes_ok,
        "latencia_media_ms": latencia_media_ms,
        "score_integridade": score_integridade,
        "score_reconstrucao": score_reconstrucao,
    }


# ─── CALLBACK DO CONSUMER ─────────────────────────────────────────────────────

def processar_score(ch, method, properties, body):
    """Callback chamado pelo pika para cada mensagem na fila_score."""
    try:
        dados      = json.loads(body)
        message_id = dados["message_id"]

        print(f"\n[Score] ▶ Calculando score para msg={message_id[:8]}...")

        resultado = calcular_score(message_id)

        if resultado:
            salvar_score(resultado)
            print(f"[Score] ✅ Score salvo:")
            print(f"         Integridade  : {resultado['score_integridade']}%")
            print(f"         Reconstrução : {resultado['score_reconstrucao']}%")
            print(f"         Latência méd : {resultado['latencia_media_ms']} ms")
            print(f"         Pacotes OK   : {resultado['pacotes_ok']}/{resultado['total_pacotes']}")

        ch.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as e:
        print(f"[Score] ❌ Erro: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


# ─── LOOP PRINCIPAL ───────────────────────────────────────────────────────────

def iniciar_score_service():
    """Conecta ao RabbitMQ e começa a consumir a fila de scores."""
    while True:
        try:
            print("=" * 55)
            print("    SCORE SERVICE — INICIANDO CONSUMIDOR            ")
            print("=" * 55)
            print(f"[Score] Conectando ao RabbitMQ em {RABBITMQ_HOST}:{RABBITMQ_PORT}...")

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

            print(f"[Score] ✅ Aguardando mensagens na fila '{FILA_SCORE}'...")
            print("[Score] Pressione CTRL+C para encerrar.\n")
            canal.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            print("[Score] ⚠️  Falha na conexão. Tentando novamente em 5s...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n[Score] Encerrando...")
            break
        except Exception as e:
            print(f"[Score] ❌ Erro inesperado: {e}. Reconectando em 5s...")
            time.sleep(5)


if __name__ == "__main__":
    iniciar_score_service()
