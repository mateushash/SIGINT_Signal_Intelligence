import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from src.transformer_morse import texto_para_morse, morse_para_binario
import src.worker_rabbit as wr
from src.buffer import dividir_adaptativo

phrase = "FOMOS SEQUESTRADOS POR UM SOLDADO ALEMAO"
morse = texto_para_morse(phrase)
binario = morse_para_binario(morse)

partes = dividir_adaptativo(binario, "&")

message_id = "test_msg_id_2"

morse_parcial1 = wr.processar_stream_binario(partes[0], message_id)
texto_p1 = wr.morse_stream_para_texto(morse_parcial1, message_id)

morse_parcial2 = wr.processar_stream_binario(partes[1], message_id)
texto_p2 = wr.morse_stream_para_texto(morse_parcial2, message_id)
texto_p2 += wr.finalizar_morse(message_id)

print(repr(texto_p1))
print(repr(texto_p2))
