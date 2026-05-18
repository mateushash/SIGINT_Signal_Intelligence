import unicodedata
import re


def limpar_texto(texto: str) -> str:
    texto = texto.upper()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    texto = re.sub(r'[^A-Z ]', '', texto)
    return texto


def texto_para_cesar(texto: str, deslocamento: int = 3) -> str:
    texto = limpar_texto(texto)
    resultado = []
    for letra in texto:
        if letra == ' ':
            resultado.append(' ')
        elif 'A' <= letra <= 'Z':
            codigo = ord(letra) - ord('A')
            codigo = (codigo + deslocamento) % 26
            resultado.append(chr(codigo + ord('A')))
        else:
            resultado.append(letra)
    return ''.join(resultado)


def decifrar_cesar(texto: str, deslocamento: int = 3) -> str:
    texto = texto.upper()
    resultado = []
    for letra in texto:
        if letra == ' ':
            resultado.append(' ')
        elif 'A' <= letra <= 'Z':
            codigo = ord(letra) - ord('A')
            codigo = (codigo - deslocamento) % 26
            resultado.append(chr(codigo + ord('A')))
        else:
            resultado.append(letra)
    return ''.join(resultado)


if __name__ == '__main__':
    exemplo = 'SIGINT Teste de César'
    cifra = texto_para_cesar(exemplo)
    print('Texto original:', exemplo)
    print('Texto cifrado:', cifra)
    print('Texto decifrado:', decifrar_cesar(cifra))
