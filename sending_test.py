import sys
import os
import requests

# Adiciona o diretório src ao path para permitir imports
sys.path.append(os.path.join(os.getcwd(), 'src'))

from transformer_morse import texto_para_morse, morse_para_binario

texto = input("Digite a Mensagem:")

morse = texto_para_morse(texto)
binario = morse_para_binario(morse)

print("Enviando mensagem pro buffer...")
print(f"Tamanho binario: {len(binario)}")


response = requests.post("http://localhost:5050/receber", json={
    "mensagem": binario,
    "cifra": "&"   
})

print("\nResposta do buffer:")
print(response.json())