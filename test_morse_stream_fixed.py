import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

MORSE_REV: dict[str, str] = {
    '.-':   'A', '-...': 'B', '-.-.': 'C', '-..':  'D',
    '.':    'E', '..-.': 'F', '--.':  'G', '....': 'H',
    '..':   'I', '.---': 'J', '-.-':  'K', '.-..': 'L',
    '--':   'M', '-.':   'N', '---':  'O', '.--.': 'P',
    '--.-': 'Q', '.-.':  'R', '...':  'S', '-':    'T',
    '..-':  'U', '...-': 'V', '.--':  'W', '-..-': 'X',
    '-.--': 'Y', '--..': 'Z',
}

_message_buffers = {}
def _get_buffers(message_id):
    if message_id not in _message_buffers:
        _message_buffers[message_id] = {"morse": ""}
    return _message_buffers[message_id]

def morse_stream_para_texto(morse_stream: str, message_id: str) -> str:
    buf = _get_buffers(message_id)
    buf["morse"] += morse_stream

    texto = buf["morse"]
    
    last_pipe = texto.rfind("|")
    last_space = texto.rfind(" ")
    last_complete_idx = max(last_pipe, last_space)
    
    if last_complete_idx == -1:
        return ""
        
    complete_part = texto[:last_complete_idx + 1]
    buf["morse"] = texto[last_complete_idx + 1:]
    
    partes = complete_part.split("|")
    resultado = ""
    
    for parte in partes:
        if " " in parte:
            subpartes = parte.split(" ")
            for j, sub in enumerate(subpartes):
                sub = sub.strip()
                if sub == "":
                    if j > 0:
                        resultado += " "
                    continue
                if sub in MORSE_REV:
                    resultado += MORSE_REV[sub]
                else:
                    resultado += "?"
                if j < len(subpartes) - 1:
                    resultado += " "
        else:
            parte = parte.strip()
            if parte == "":
                continue
            if parte in MORSE_REV:
                resultado += MORSE_REV[parte]
            else:
                resultado += "?"

    return resultado

print(repr(morse_stream_para_texto("..-|-- ", "1")))
print(repr(_message_buffers["1"]["morse"]))
print(repr(morse_stream_para_texto("...", "1")))
print(repr(_message_buffers["1"]["morse"]))
print(repr(morse_stream_para_texto("|", "1")))
print(repr(_message_buffers["1"]["morse"]))

