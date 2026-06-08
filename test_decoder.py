import json

def processar_stream_binario(binario: str) -> str:
    resultado = ""
    data = binario
    i = 0

    while i < len(data):
        remaining = len(data) - i

        if remaining >= 7 and data[i:i + 7] == "0000000":
            resultado += " "
            i += 7
        elif remaining >= 3 and data[i:i + 3] == "000":
            # BUGGY CODE:
            if remaining < 7 or data[i:i + 7] != "0000000":
                resultado += "|"
                i += 3
            else:
                break
        elif remaining >= 3 and data[i:i + 3] == "111":
            resultado += "-"
            i += 3
        elif data[i] == "1":
            resultado += "."
            i += 1
        elif data[i] == "0":
            if remaining < 3:
                break
            i += 1
        else:
            i += 1
    return resultado

def processar_stream_binario_fixed(binario: str) -> str:
    resultado = ""
    data = binario
    i = 0

    while i < len(data):
        remaining = len(data) - i

        if remaining >= 7 and data[i:i + 7] == "0000000":
            resultado += " "
            i += 7
        elif remaining >= 3 and data[i:i + 3] == "000":
            # FIXED CODE:
            # Check if there are only zeros and less than 7 chars remaining
            # In that case, we must wait for more data to see if it becomes 0000000
            # How? If all characters up to min(remaining, 7) are "0", but we have < 7.
            # Easiest way: if "1" is not in data[i:i+7] and remaining < 7: break
            if "1" not in data[i:i+7] and remaining < 7:
                break
            resultado += "|"
            i += 3
        elif remaining >= 3 and data[i:i + 3] == "111":
            resultado += "-"
            i += 3
        elif data[i] == "1":
            resultado += "."
            i += 1
        elif data[i] == "0":
            if "1" not in data[i:i+3] and remaining < 3:
                break
            i += 1
        else:
            i += 1
    return resultado

print("Buggy:", processar_stream_binario("111000000"))
print("Fixed:", processar_stream_binario_fixed("111000000"))

