#!/bin/bash

BUFFER_ID=$1

if [ -z "$BUFFER_ID" ]; then
    echo "Uso: ./kill_buffer.sh <id_do_buffer>"
    echo "Exemplo: ./kill_buffer.sh 1"
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

echo "Procurando processo do Buffer $BUFFER_ID (porta $PORTA)..."
PID=$(lsof -ti:$PORTA)

if [ -z "$PID" ]; then
    echo "Nenhum Buffer $BUFFER_ID rodando."
else
    echo "Derrubando Buffer $BUFFER_ID (PID: $PID)..."
    kill -9 $PID
    echo "Buffer $BUFFER_ID derrubado com sucesso!"
fi
