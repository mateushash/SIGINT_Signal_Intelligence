#!/bin/bash

echo "==================================================="
echo "🛑 PARANDO O SISTEMA CRIASDECRIP"
echo "==================================================="

echo "1. Parando os serviços Python (Buffer, Worker, Score)..."
pkill -f "src/buffer.py"
pkill -f "src/worker_rabbit.py"
pkill -f "src/score_service.py"

echo -e "${BLUE}2. Parando RabbitMQ e Load Balancer no Docker...${NC}"
docker stop rabbitmq > /dev/null 2>&1
docker stop sigint_nginx_lb > /dev/null 2>&1
docker rm sigint_nginx_lb > /dev/null 2>&1

echo "✅ Todos os serviços foram parados com sucesso."
echo "==================================================="
