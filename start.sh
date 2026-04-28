#!/bin/bash

# Cores para o terminal
GREEN='\033[0;32m'
BLUE='\033[0;34m'
ORANGE='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${ORANGE}===================================================${NC}"
echo -e "${ORANGE}🚀 INICIANDO O SISTEMA CRIASDECRIP (Semana 1 a 4)${NC}"
echo -e "${ORANGE}===================================================${NC}"

echo -e "${BLUE}1️⃣  Iniciando RabbitMQ no Docker...${NC}"
docker start rabbitmq > /dev/null 2>&1 || docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management > /dev/null 2>&1

echo -e "${BLUE}⏳ Aguardando RabbitMQ estabilizar (Pode levar alguns segundos)...${NC}"
# Loop de verificação de porta (espera real em vez de sleep cego)
for i in {1..20}; do
    if nc -z localhost 5672 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ RabbitMQ está online!${NC}"
        break
    fi
    if [ $i -eq 20 ]; then
        echo -e "${RED}❌ RabbitMQ demorou demais. Verifique se o Docker Desktop está aberto!${NC}"
        exit 1
    fi
    sleep 1
done

echo -e "${BLUE}2️⃣  Limpando processos antigos do Python...${NC}"
pkill -f "buffer.py"
pkill -f "worker_rabbit.py"
pkill -f "score_service.py"
sleep 1

echo -e "${BLUE}3️⃣  Iniciando serviços em segundo plano...${NC}"
python3 buffer.py > buffer.log 2>&1 &
echo -e "   [OK] Buffer (Porta 5050)"
python3 worker_rabbit.py > worker.log 2>&1 &
echo -e "   [OK] Worker (RabbitMQ Consumer)"
python3 score_service.py > score.log 2>&1 &
echo -e "   [OK] Score Service (Evaluator)"

echo -e "\n${GREEN}✅ TUDO PRONTO! O SISTEMA ESTÁ VOANDO!${NC}\n"
echo -e "👉 ${BLUE}Dashboard:${NC} Abra o arquivo ${ORANGE}painel.html${NC} no Chrome/Live Server"
echo -e "👉 ${BLUE}Enviar Teste:${NC} Rode 'python3 sending_test.py' para testar"
echo -e "👉 ${BLUE}Parar:${NC} Rode './stop.sh'"
echo -e "${ORANGE}===================================================${NC}"
