import sys
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

def test_full_phrase(phrase, chunk_size):
    morse = texto_para_morse(phrase)
    binario = morse_para_binario(morse)

    chunks = [binario[i:i+chunk_size] for i in range(0, len(binario), chunk_size)]

    texto_result = ""
    buf = {"binario": "", "morse": ""}
    for idx, chunk in enumerate(chunks):
        morse_parcial = processar_stream_binario_fixed(chunk, buf)
        
        buf["morse"] += morse_parcial
        partes = buf["morse"].split("|")
        texto = ""

        for parte in partes[:-1]:
            if " " in parte:
                subpartes = parte.split(" ")
                for j, sub in enumerate(subpartes):
                    sub = sub.strip()
                    if sub == "":
                        if j > 0:
                            texto += " "
                        continue
                    if sub in wr.MORSE_REV:
                        texto += wr.MORSE_REV[sub]
                    else:
                        texto += "?"
                    if j < len(subpartes) - 1:
                        texto += " "
            else:
                parte = parte.strip()
                if parte == "":
                    continue
                if parte in wr.MORSE_REV:
                    texto += wr.MORSE_REV[parte]
                else:
                    texto += "?"

        buf["morse"] = partes[-1]
        texto_result += texto
        
        if idx == len(chunks) - 1:
            restante = buf["morse"].strip()
            if restante:
                if restante in wr.MORSE_REV:
                    texto_result += wr.MORSE_REV[restante]
                elif " " in restante:
                    for sub in restante.split(" "):
                        sub = sub.strip()
                        if sub and sub in wr.MORSE_REV:
                            texto_result += wr.MORSE_REV[sub]
                        elif sub:
                            texto_result += "?"
                elif restante:
                    texto_result += "?"

    if "U M" in texto_result:
        print(f"Failed at chunk size {chunk_size}: {texto_result}")
        return False
    return True

phrase = "FOMOS SEQUESTRADOS POR UM SOLDADO ALEMAO"
failed = False
for i in range(1, 100):
    if not test_full_phrase(phrase, i):
        failed = True

if not failed:
    print("All chunk sizes passed!")

