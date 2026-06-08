import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from src.transformer_morse import texto_para_morse, morse_para_binario
from src.buffer import dividir_adaptativo
import src.worker_rabbit as wr

phrase = "FOMOS SEQUESTRADOS POR UM SOLDADO ALEMAO"
morse = texto_para_morse(phrase)
binario = morse_para_binario(morse)
partes = dividir_adaptativo(binario, "&")

print("Packet 1 binary length:", len(partes[0]))
print("Packet 1 binary ends with:", partes[0][-10:])

# Simulate worker processing Packet 1
# Since it's a new message, we use a new message_id
message_id = "test_msg_id"

# Process Packet 1
morse_parcial = wr.processar_stream_binario(partes[0], message_id)
print("Morse parcial P1:", morse_parcial)
texto_p1 = wr.morse_stream_para_texto(morse_parcial, message_id)
print("Texto P1:", repr(texto_p1))

# Process Packet 2
morse_parcial2 = wr.processar_stream_binario(partes[1], message_id)
print("Morse parcial P2:", morse_parcial2)
texto_p2 = wr.morse_stream_para_texto(morse_parcial2, message_id)
# Simulate finalizing (since total packets = 2)
texto_p2 += wr.finalizar_morse(message_id)
print("Texto P2:", repr(texto_p2))

