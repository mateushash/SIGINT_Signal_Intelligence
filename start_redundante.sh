#!/bin/bash

echo "==================================================="
echo "INICIANDO CRIASDECRIP COM ALTA DISPONIBILIDADE"
echo "==================================================="

# 1. Limpa processos antigos
pkill -f "src/buffer.py"
pkill -f "src/worker_rabbit.py"
pkill -f "src/score_service.py"

# 2. Sobe o RabbitMQ (Docker)
docker-compose up -d

mkdir -p logs

# 3. Inicia DOIS Buffers (Redundância)
echo "1. Iniciando Buffer Primário (Porta 5050)..."
python3 src/buffer.py 5050 > logs/buffer_5050.log 2>&1 &
echo "2. Iniciando Buffer Secundário (Porta 5051)..."
python3 src/buffer.py 5051 > logs/buffer_5051.log 2>&1 &

# 4. Inicia DOIS Workers (Distribuição de Carga)
echo "3. Iniciando 2 Workers em paralelo..."
python3 src/worker_rabbit.py > logs/worker1.log 2>&1 &
python3 src/worker_rabbit.py > logs/worker2.log 2>&1 &

# 5. Inicia o Serviço de Score
echo "4. Iniciando Serviço de Score..."
python3 src/score_service.py > logs/score.log 2>&1 &

echo ""
echo "✅ SISTEMA DISTRIBUÍDO E REDUNDANTE ONLINE!"
echo "👉 Use a porta 5050 ou 5051. Se uma cair, a outra segura o tranco!"
echo "==================================================="
