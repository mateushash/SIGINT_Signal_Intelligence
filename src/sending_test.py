from transformer_morse import texto_para_morse, morse_para_binario
import requests


texto = """Você me perguntou recentemente por que eu afirmo ter medo de você. Como de costume, não soube responder, em parte justamente por causa do medo que tenho de você, em parte porque na motivação desse medo intervêm tantos pormenores, que mal poderia reuni-los numa fala. E se aqui tento responder por escrito, será sem dúvida de um modo muito incompleto, porque, também ao escrever, o medo e suas consequências me inibem diante de você e porque a magnitude do assunto ultrapassa de longe minha memória e meu entendimento."""

'''
Caso maior :
    Você me perguntou recentemente por que eu afirmo ter medo de você. Como de costume, não soube responder, em parte justamente por causa do medo que tenho de você, em parte porque na motivação desse medo intervêm tantos pormenores, que mal poderia reuni-los numa fala. E se aqui tento responder por escrito, será sem dúvida de um modo muito incompleto, porque, também ao escrever, o medo e suas consequências me inibem diante de você e porque a magnitude do assunto ultrapassa de longe minha memória e meu entendimento.

Caso curto:
    A otimização prematura é a raiz de todo mal
'''

morse = texto_para_morse(texto)
binario = morse_para_binario(morse)

print("Enviando mensagem pro buffer...")
print(f"Tamanho binario: {len(binario)}")

#Atua como listener e envia pro Buffer para que comece os processos
response = requests.post("http://localhost:5000/receber", json={
    "mensagem": binario,
    "cifra": "&"   
})

print("\nResposta do buffer:")
print(response.json())