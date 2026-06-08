import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from src.transformer_morse import texto_para_morse, morse_para_binario
from src.buffer import dividir_adaptativo

phrase = "FOMOS SEQUESTRADOS POR UM SOLDADO ALEMAO"
morse = texto_para_morse(phrase)
binario = morse_para_binario(morse)

partes = dividir_adaptativo(binario, "&")
for i, p in enumerate(partes):
    print(f"Packet {i+1}: length {len(p)}")

# Also let's print the words
SEP = "0000000"
palavras = binario.split(SEP)
for i, palavra in enumerate(palavras):
    bloco = palavra + SEP if i < len(palavras) - 1 else palavra
    print(f"Word {i+1} length: {len(bloco)}")

