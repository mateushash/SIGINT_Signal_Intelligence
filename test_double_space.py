import sys
from src.transformer_morse import texto_para_morse, morse_para_binario
import src.worker_rabbit as wr

def test_no_chunking(phrase):
    morse = texto_para_morse(phrase)
    binario = morse_para_binario(morse)

    # Use the original buggy code to see if it also produces double spaces
    # when chunking is not an issue (i.e. single chunk)
    morse_parcial = wr.processar_stream_binario(binario, "test")
    texto = wr.morse_stream_para_texto(morse_parcial, "test")
    texto += wr.finalizar_morse("test")

    print(f"Phrase: {phrase}")
    print(f"Result: {texto}")

test_no_chunking("O JOVEM")

