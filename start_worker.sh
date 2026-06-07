#!/bin/bash

set -e

echo "==================================================="
echo "INICIANDO APENAS O WORKER"
echo "==================================================="

mkdir -p logs

: "${SIGINT_RABBITMQ_HOST:?Defina SIGINT_RABBITMQ_HOST com o IP Tailscale da máquina do RabbitMQ}"
: "${SIGINT_BUFFER_URL:?Defina SIGINT_BUFFER_URL com o endpoint /retorno do Buffer}"

nohup python3 -u src/worker_rabbit.py > logs/worker.log 2>&1 &
echo "✅ Worker iniciado em segundo plano"
echo "RabbitMQ: ${SIGINT_RABBITMQ_HOST}:5672"
echo "Buffer:   ${SIGINT_BUFFER_URL}"
