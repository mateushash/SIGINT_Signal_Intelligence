#!/bin/bash

# Cores para o terminal
GREEN='\033[0;32m'
BLUE='\033[0;34m'
ORANGE='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${ORANGE}===================================================${NC}"
echo -e "${ORANGE}INICIANDO O SISTEMA CRIASDECRIP (Semana 1 a 6)${NC}"
echo -e "${ORANGE}===================================================${NC}"

echo -e "${BLUE}1. Iniciando RabbitMQ no Docker...${NC}"
docker start rabbitmq || docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

echo -e "${BLUE}⏳ Aguardando RabbitMQ estabilizar...${NC}"
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

echo -e "${BLUE}1.5. Iniciando Load Balancer (Nginx) no Docker...${NC}"
docker start sigint_nginx_lb 2>/dev/null || docker run -d --name sigint_nginx_lb -p 8080:8080 -v "$(pwd)/nginx_lb.conf:/etc/nginx/nginx.conf:ro" nginx:alpine

echo -e "${BLUE}2. Limpando processos antigos do Python...${NC}"
pkill -f "src/buffer.py"
pkill -f "src/worker_rabbit.py"
pkill -f "src/score_service.py"
sleep 1

echo -e "${BLUE}3. Iniciando serviços em segundo plano...${NC}"
python3 -u src/buffer.py 5050 > logs/buffer_5050.log 2>&1 &
python3 -u src/buffer.py 5051 > logs/buffer_5051.log 2>&1 &
python3 -u src/buffer.py 5052 > logs/buffer_5052.log 2>&1 &
echo -e "   [OK] Buffers (Portas 5050, 5051 e 5052 - Failover Ativo)"
python3 -u src/worker_rabbit.py > logs/worker.log 2>&1 &
echo -e "   [OK] Worker (RabbitMQ Consumer)"
python3 -u src/score_service.py > logs/score.log 2>&1 &
echo -e "   [OK] Score Service (Evaluator)"

echo -e "\n${GREEN}✅ TUDO PRONTO! O SISTEMA ESTÁ VOANDO!${NC}\n"
echo -e "👉 ${BLUE}Dashboard:${NC} Abra o arquivo ${ORANGE}web/painel.html${NC}"
echo -e "👉 ${BLUE}Enviar Teste:${NC} Rode 'python3 sending_test.py'"
echo -e "👉 ${BLUE}Parar:${NC} Rode './stop.sh'"
echo -e "${ORANGE}===================================================${NC}"
