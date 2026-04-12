import pika
import json
import requests

BUFFER_URL = "http://localhost:5000/retorno"

#conexo pelo RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.queue_declare(queue='fila_processamento')

#Tabela de conversao
MORSE = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..',
    'E': '.', 'F': '..-.', 'G': '--.', 'H': '....',
    'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
    'M': '--', 'N': '-.', 'O': '---', 'P': '.--.',
    'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
    'Y': '-.--', 'Z': '--..'
}

#Inverter a tabela de cima para decodificar
MORSE_REV = {v: k for k, v in MORSE.items()}

#acumulo de dados durante o processo
buffers_binario = {}
buffers_morse = {}
pacotes_buffer = {}
proxima_ordem_esperada = {}

#conversao do binario para o morse, todas palavras juntas 
def processar_stream(message_id, binario):
    if message_id not in buffers_binario:
        buffers_binario[message_id] = ""

    buffer_binario = buffers_binario[message_id]
    buffer_binario += binario

    resultado = ""
    i = 0

    while i < len(buffer_binario):

        if buffer_binario[i:i+7] == "0000000":
            resultado += " "
            i += 7

        elif buffer_binario[i:i+3] == "000":
            resultado += "|"
            i += 3

        elif buffer_binario[i:i+3] == "111":
            resultado += "-"
            i += 3

        elif buffer_binario[i] == "1":
            resultado += "."
            i += 1

        else:
            i += 1

    buffers_binario[message_id] = buffer_binario[i:]

    return resultado



#uno pacote por vez
channel.basic_qos(prefetch_count=1)

#validacao do processo toda vez que uma mensagem chega na fila
def callback(ch, method, properties, body):
    #averiguar o recebido
    try:
        dados = json.loads(body)
    except Exception as e:
        print("Erro ao decodificar JSON:", e)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return
    #Extracao ded ados
    try:
        id = dados["id"]
        message_id = dados["message_id"]
        conteudo = dados["conteudo"]
        ordem = dados["ordem"]
        total = dados["total"]
    except KeyError as e:
        print("Campo faltando:", e)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    print(f"Worker recebeu pacote {ordem+1}/{total}")

    #sequencia de ifs caso seja a primeira vez que esteja no processo, averiguar ordem no geral
    if message_id not in buffers_morse:
        buffers_morse[message_id] = ""

    if message_id not in pacotes_buffer:
        pacotes_buffer[message_id] = {}

    if message_id not in proxima_ordem_esperada:
        proxima_ordem_esperada[message_id] = 0

    pacotes_buffer[message_id][ordem] = conteudo    

    # processa na ordem correta os pacotes
    while True:
        ordem_esperada = proxima_ordem_esperada[message_id]

        if ordem_esperada in pacotes_buffer[message_id]:
            conteudo_ordem = pacotes_buffer[message_id].pop(ordem_esperada)

            morse_parcial = processar_stream(message_id, conteudo_ordem)
            buffers_morse[message_id] += morse_parcial

            proxima_ordem_esperada[message_id] += 1
        else:
            break

    texto = ""  
#Morse para texto, tudo junto
    texto_novo = ""  

    partes = buffers_morse[message_id].split("|")

    for p in partes[:-1]:
        p = p.strip()

        if p == "":
            continue

        if p in MORSE_REV:
            letra = MORSE_REV[p]
            texto += letra
            texto_novo += letra   
        elif p == "/":
            texto += " "

    buffers_morse[message_id] = partes[-1]

    print("Decodificado:", texto)

    sucesso = True

    #Atualiza via http
    try:
        requests.post(BUFFER_URL, json={
            "id": id,
            "message_id": message_id,
            "resultado": texto_novo,  
            "ordem": ordem,
            "total": total
        }, timeout=5)
    except Exception as e:
        print("Erro ao enviar retorno:", e)
        sucesso = False

    #tranca o pacote na fila com Rabbit ate que ele seja processado
    if sucesso:
        ch.basic_ack(delivery_tag=method.delivery_tag)

    #Limpa acumulo de dados daquele message_id
    if proxima_ordem_esperada[message_id] == total:
        buffers_binario.pop(message_id, None)
        buffers_morse.pop(message_id, None)
        pacotes_buffer.pop(message_id, None)
        proxima_ordem_esperada.pop(message_id, None)    

#Trava o worker quando executado em um processo de aguardo infinito
channel.basic_consume(
    queue='fila_processamento',
    on_message_callback=callback,
    auto_ack=False
)

print("Worker aguardando mensagens...")
channel.start_consuming()