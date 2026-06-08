#!/bin/bash

BUFFER_ID=$1

if [ -z "$BUFFER_ID" ]; then
    echo "Uso: ./start_buffer.sh <id_do_buffer>"
    echo "Exemplo: ./start_buffer.sh 1"
    echo "IDs disponíveis: 1 (Porta 5050), 2 (Porta 5051), 3 (Porta 5052)"
    exit 1
fi

case $BUFFER_ID in
    1) PORTA=5050 ;;
    2) PORTA=5051 ;;
    3) PORTA=5052 ;;
    *) 
        echo "ID de buffer inválido. Escolha 1, 2 ou 3."
        exit 1
        ;;
esac

echo "Verificando se já existe algo rodando na porta $PORTA..."
if lsof -Pi :$PORTA -sTCP:LISTEN -t >/dev/null ; then
    echo "❌ Erro: Já existe um processo rodando na porta $PORTA."
    exit 1
fi

echo "Iniciando Buffer $BUFFER_ID (porta $PORTA) em segundo plano..."
python3 -u src/buffer.py $PORTA > logs/buffer_${PORTA}.log 2>&1 &

echo "✅ Buffer $BUFFER_ID reiniciado com sucesso! Confira o painel."
