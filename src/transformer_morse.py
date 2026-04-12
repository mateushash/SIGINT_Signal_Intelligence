import unicodedata
import re

MORSE = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..',
    'E': '.', 'F': '..-.', 'G': '--.', 'H': '....',
    'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
    'M': '--', 'N': '-.', 'O': '---', 'P': '.--.',
    'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-',
    'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
    'Y': '-.--', 'Z': '--..'
}


def limpar_texto(texto):
    texto = texto.upper()

    
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )

    
    texto = re.sub(r'[^A-Z ]', '', texto)

    return texto


def texto_para_morse(texto):
    texto = limpar_texto(texto)

    palavras = texto.split()
    resultado = []

    for palavra in palavras:
        letras = []
        for letra in palavra:
            if letra in MORSE:
                letras.append(MORSE[letra])
        resultado.append(' '.join(letras))

    return ' / '.join(resultado)


def morse_para_binario(morse):
    resultado = ""

    palavras = morse.split(" / ")

    for palavra in palavras:
        letras = palavra.split(" ")

        for letra in letras:
            for simbolo in letra:
                if simbolo == '.':
                    resultado += "1"
                elif simbolo == '-':
                    resultado += "111"

                resultado += "0"

            resultado += "000" 

        resultado += "0000000"  

    return resultado


texto = """Você me perguntou recentemente por que eu afirmo ter medo de você. Como de costume, não soube responder, em parte justamente por causa do medo que tenho de você, em parte porque na motivação desse medo intervêm tantos pormenores, que mal poderia reuni-los numa fala. E se aqui tento responder por escrito, será sem dúvida de um modo muito incompleto, porque, também ao escrever, o medo e suas consequências me inibem diante de você e porque a magnitude do assunto ultrapassa de longe minha memória e meu entendimento."""

morse = texto_para_morse(texto)
binario = morse_para_binario(morse)

print("MORSE:")
print(morse)

print("\nBINARIO (primeiros 300):")
print(binario[:300])