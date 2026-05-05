#!/bin/bash
echo "==================================================="
echo "🚀 INICIANDO CRIASDECRIP COM ALTA DISPONIBILIDADE"
echo "==================================================="

# 1. Limpa processos antigos
pkill -f "python3 buffer.py"
pkill -f "python3 worker_rabbit.py"
pkill -f "python3 score_service.py"

# 2. Sobe o RabbitMQ (Docker)
docker-compose up -d

# 3. Inicia DOIS Buffers (Redundância)
echo "1️⃣  Iniciando Buffer Primário (Porta 5050)..."
python3 buffer.py 5050 > buffer_5050.log 2>&1 &
echo "2️⃣  Iniciando Buffer Secundário (Porta 5051)..."
python3 buffer.py 5051 > buffer_5051.log 2>&1 &

# 4. Inicia DOIS Workers (Distribuição de Carga)
echo "3️⃣  Iniciando 2 Workers em paralelo..."
python3 worker_rabbit.py > worker1.log 2>&1 &
python3 worker_rabbit.py > worker2.log 2>&1 &

# 5. Inicia o Serviço de Score
echo "4️⃣  Iniciando Serviço de Score..."
python3 score_service.py > score.log 2>&1 &

echo ""
echo "✅ SISTEMA DISTRIBUÍDO E REDUNDANTE ONLINE!"
echo "👉 Use a porta 5050 ou 5051. Se uma cair, a outra segura o tranco!"
echo "==================================================="
