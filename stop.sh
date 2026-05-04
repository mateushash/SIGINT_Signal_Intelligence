#!/bin/bash

echo "==================================================="
echo "🛑 PARANDO O SISTEMA CRIASDECRIP"
echo "==================================================="

echo "1️⃣  Parando os serviços Python (Buffer, Worker, Score)..."
pkill -f "buffer.py"
pkill -f "worker_rabbit.py"
pkill -f "score_service.py"

echo "2️⃣  Parando o RabbitMQ no Docker (para não consumir RAM)..."
docker stop rabbitmq > /dev/null 2>&1

echo "✅ Todos os serviços foram parados com sucesso."
echo "==================================================="
