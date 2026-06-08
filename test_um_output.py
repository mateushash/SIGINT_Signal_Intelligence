import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
from src.transformer_morse import texto_para_morse, morse_para_binario
import src.worker_rabbit as wr

def processar_stream_binario_fixed(binario: str, buf: dict) -> str:
    buf["binario"] += binario

    resultado = ""
    data = buf["binario"]
    i = 0

    while i < len(data):
        remaining = len(data) - i

        if remaining >= 7 and data[i:i + 7] == "0000000":
            resultado += " "
            i += 7
        elif remaining >= 3 and data[i:i + 3] == "000":
            if "1" not in data[i:i+7] and remaining < 7:
                break
            resultado += "|"
            i += 3
        elif remaining >= 3 and data[i:i + 3] == "111":
            resultado += "-"
            i += 3
        elif data[i] == "1":
            if "0" not in data[i:i+3] and remaining < 3:
                break
            resultado += "."
            i += 1
        elif data[i] == "0":
            if "1" not in data[i:i+3] and remaining < 3:
                break
            i += 1
        else:
            i += 1

    buf["binario"] = data[i:]
    return resultado

phrase = "UM"
morse = texto_para_morse(phrase)
binario = morse_para_binario(morse)

# Process the whole thing at once
buf = {"binario": ""}
res = processar_stream_binario_fixed(binario, buf)
print("Binary len:", len(binario))
print("Res:", repr(res))
print("Buf binario:", repr(buf["binario"]))

