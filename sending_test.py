import sys
import os
import requests

# Adiciona o diretório src de forma absoluta e prioritária ao path
_script_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.join(_script_dir, 'src')
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from src.transformer_morse import texto_para_morse, morse_para_binario
from src.transformer_cesar import texto_para_cesar


print("Modo de envio:")
print("1 - Morse")
print("2 - Cifra de César")
modo = input("Escolha 1 ou 2: ").strip()
while modo not in ("1", "2"):
    modo = input("Escolha 1 ou 2: ").strip()

texto = input("Digite a Mensagem:")

if modo == "1":
    morse = texto_para_morse(texto)
    mensagem = morse_para_binario(morse)
    cifra = "&"
    print("Transformando para MORSE...")
elif modo == "2":
    mensagem = texto_para_cesar(texto)
    cifra = "$"
    print("Transformando para Cifra de César...")

print("Enviando mensagem pro buffer...")
print(f"Tamanho da mensagem: {len(mensagem)}")

response = requests.post("http://localhost:5050/receber", json={
    "mensagem": mensagem,
    "cifra": cifra
})

print("\nResposta do buffer:")
print(response.json())