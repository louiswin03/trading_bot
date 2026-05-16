
import os
code_b64 = open('_code.b64').read()
import base64
code = base64.b64decode(code_b64).decode('utf-8')
with open('final_strategy_rank8_corrected.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('Written', len(code), 'bytes')
os.remove('_code.b64')
