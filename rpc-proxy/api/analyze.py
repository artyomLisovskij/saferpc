from openai import OpenAI, DefaultHttpxClient
import httpx
import requests
from web3 import Web3
import os
from hexbytes import HexBytes
from eth_account import Account
import traceback
from .models import DisassembledContractFunction, PendingTransaction, ContractStaticAnalysis
import json
from hashlib import md5

socks_url = os.environ.get("SOCKS_URL")
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"), http_client=DefaultHttpxClient(proxy=socks_url)
)
w3 = Web3(Web3.HTTPProvider("http://hardhat-network:8545"))
API_URL = "http://gigahorse:8000/run"


def list_openai_models():
    models = client.models.list()
    return_list = []
    for mdl in models.data:
        return_list.append(mdl.id)
    return return_list

def call_openai_compile_contract(content: str, model: str = "gpt-4o-mini"):
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "Отвечай _только_ solidity-кодом без каких-либо описаний или пояснений. Ты - профессиональный solidity-разработчик, который анализирует взаимодействия между смарт-контрактами."
            },
            {
                "role": "user",
                "content":f"Собери из кусков solidity-кода единый смарт-контракт. \n Куски контракта: ```{content}```."
            }
        ]
    )
    return response.choices[0].message.content

def call_openai(content: str, model: str = "gpt-4o-mini"):
    result_content = f"Контракт: ```\n{content}\n```\n"

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "Отвечай _только_ кодом sequenceDiagram без каких-либо описаний или пояснений. Ты - профессиональный solidity-разработчик, который анализирует взаимодействия между смарт-контрактами."
            },
            {
                "role": "user",
                "content":f"Нарисуй sequenceDiagram взаимодействия пользователя с контрактом на основании solidity-кода.\n{result_content}."
            }
        ]
    )
    return response.choices[0].message.content

def call_openai_on_schemas(content: str, model: str = "gpt-4o-mini"):
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "Отвечай _только_ кодом sequenceDiagram без каких-либо описаний или пояснений. Ты - профессиональный бизнес-аналитик, который анализирует взаимодействия между смарт-контрактами на основании схем взаимодействий."
            },
            {
                "role": "user",
                "content":f"Нарисуй общую sequenceDiagram взаимодействия пользователя между несколькими смарт-контрактами согласно вызванной транзакции.\n{content}."
            }
        ]
    )
    return response.choices[0].message.content

def call_openai_one_function(content: str, model: str = "gpt-4o-mini"):
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Отвечай _только_ solidity-кодом без каких-либо описаний, пояснений, классов, `pragma` и `solidity` - только код функции без использования assembly, сохраняя адреса используемых storage-слотов. Ты - профессиональный разработчик смарт-контрактов и реверс-инженер EVM-байткода."
            },
            {
                "role": "user",
                "content":f"Напиши solidity-подобный псевдокод для дизассемблированной функции, не изменяя её название и названия аргументов и не добавляя f в начале названия функции. Конструкции вида CALLPRIVATE обозначают вызовы функции, указанной в скобках в первом аргументе, замени CALLPRIVATE на название функции, которое начинается обычно на 0x и находится в скобках в первом аргументе, и дополни такой вызов остальными аргументов вызова функции согласно конструкции CALLPRIVATE. Если название event'а, которое происходит в emit тебе точно известно, то замени хеш на название event'а в псевдокоде. Конструкция MLOAD загружает значение из storage-слота - учитывай это и обозначай в псевдокоде какой storage-слот .\n{content}."
            }
        ]
    )
    return response.choices[0].message.content

def run_gigahorse_command(cmd: str):
    payload = {
        "cmd": cmd
    }
    try:
        resp = requests.post(API_URL, json=payload, timeout=1000)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Ошибка при запросе к API: {e}")
        return

    data = resp.json()
    # print("Код возврата:", data["returncode"])
    # print("STDOUT:\n", data["stdout"])
    # print("STDERR:\n", data["stderr"])
    return data["stdout"]

def get_implementation_address(address: str) -> bool:
    """
    Проверяет, есть ли в контракте по адресу `address` хранилище
    implementation согласно EIP-1967.
    """
    addr = w3.to_checksum_address(address)
    # вычисляем слот: keccak256("eip1967.proxy.implementation") - 1
    slot_raw = w3.keccak(text="eip1967.proxy.implementation")
    slot_int = int.from_bytes(slot_raw, "big") - 1
    slot = HexBytes(slot_int)

    # читаем storage по этому слоту
    impl_bytes = w3.eth.get_storage_at(addr, slot)
    impl_int = int.from_bytes(impl_bytes, "big")

    if impl_int == 0:
        # нет записи — вряд ли это EIP-1967 прокси
        return False

    # из последних 20 байт строим адрес реализации
    impl_addr = w3.to_checksum_address(impl_bytes[-20:].hex())
    # проверяем, что по этому адресу есть код
    code = w3.eth.get_code(impl_addr)
    if len(code) > 0:
        return code
    else:
        return False


def parse_contract_address(contract_address: str):
    # Приводим к checksum-формату
    checksum_addr = w3.to_checksum_address(contract_address)
    impl_addr = get_implementation_address(checksum_addr)
    if impl_addr:
        bytecode_bytes = w3.eth.get_code(impl_addr)
        bytecode_hex = bytecode_bytes.hex()
        # print("Bytecode of implementation:", bytecode_hex)
    else:
        bytecode_bytes = w3.eth.get_code(checksum_addr)
        bytecode_hex = bytecode_bytes.hex()
        # print("Bytecode:", bytecode_hex)
    return bytecode_hex

# def evm_disasm(bytecode: str):
#     from evmdasm import EvmBytecode

#     # 1. получаем байткод контракта (hex-строка без префикса 0x)
#     bytecode_hex = open("contract.bin").read().strip()
#     bc = EvmBytecode(bytecode_hex)
#     ops = bc.disassemble()  # список (offset, opcode, operands)

#     # 2. проходим по ops, ищем CALL-инструкции
#     call_graph = {}  # addr -> set(targets)
#     stack = []
#     for idx, (offset, op, operand) in enumerate(ops):
#         if op.startswith("PUSH"):
#             stack.append(int(operand,16))
#         elif op in ("CALL","DELEGATECALL","STATICCALL","CALLCODE"):
#             # по спецификации EVM, адрес для CALL лежит в стеке примерно на 2-й позиции сверху
#             if len(stack) >= 2:
#                 target = stack[-2]
#                 # если это 20-байтовая константа
#                 if target > 0 and target.bit_length() <= 160:
#                     addr = hex(target)
#                 else:
#                     addr = "UNKNOWN"
#             else:
#                 addr = "UNKNOWN"
#             call_graph.setdefault("this_contract", set()).add(addr)
#             stack.clear()  # сброс, чтобы упрощённо не усложнять анализ
#         else:
#             # для прочих операций можно симулировать изменение стека, но в упрощении пропустим
#             pass

#     print("Call-graph:", call_graph)

def evm_simulate_tx(signed_raw: str):
    from_address = Account.recover_transaction(signed_raw)
    print(from_address)
    rpc_w3 = Web3(Web3.HTTPProvider(os.environ.get('RPC_URL')))
    params = [{
        "forking": {
            "jsonRpcUrl": os.environ.get('RPC_URL'),
            "blockNumber": rpc_w3.eth.get_block_number() - 10
        }
    }]
    w3.manager.request_blocking("hardhat_reset", params)
    snapshot_id = w3.provider.make_request("evm_snapshot", [])
    related = set()
    try:
        tx_hash = w3.eth.send_raw_transaction(HexBytes(signed_raw))
        trace = w3.provider.make_request("debug_traceTransaction", [tx_hash, {}])
        # print("trace:", trace)
        for struct in trace["result"]["structLogs"]:
            op = struct["op"]
            if op in ("CALL","DELEGATECALL","STATICCALL"):
                # в простейшем случае адрес лежит в stack[-2] или stack[-3] после PUSH
                addr_hex = struct["stack"][-2][-40:]
                related.add("0x" + addr_hex.lower())

    except Exception as e:
        traceback.print_exc()
    finally:
        w3.provider.make_request("evm_revert", [snapshot_id])
        params = [{
            "forking": {
                "jsonRpcUrl": os.environ.get('RPC_URL'),
                "blockNumber": rpc_w3.eth.get_block_number() - 10
            }
        }]
        w3.manager.request_blocking("hardhat_reset", params)
    
    print("Взаимодействия с:", related)
    return related, trace

def analyze_transaction(signed_raw: str, from_address: str, to_address: str, trace: str = None, pending_transaction: PendingTransaction = None):
    if not trace:
        related_contracts, trace = evm_simulate_tx(signed_raw)
        if pending_transaction:
            pending_transaction.trace = json.dumps(trace)
            pending_transaction.save()
    else:
        trace = json.loads(trace)
        related_contracts = set()
        for struct in trace["result"]["structLogs"]:
            op = struct["op"]
            if op in ("CALL","DELEGATECALL","STATICCALL"):
                # в простейшем случае адрес лежит в stack[-2] или stack[-3] после PUSH
                addr_hex = struct["stack"][-2][-40:]
                related_contracts.add("0x" + addr_hex.lower())
    static_analysis_output = {}
    schemas = {}
    for related_address in related_contracts:
        parsed_contract = parse_contract_address(related_address)
        bytecode_hash = md5(parsed_contract.encode()).hexdigest()
        contract_static_analysis = ContractStaticAnalysis.objects.filter(bytecode_hash=bytecode_hash, contract_address=related_address).first()
        if not contract_static_analysis:
            run_gigahorse_command(f"cd /app && > {related_address}.hex && echo '{parsed_contract}' >> {related_address}.hex && /opt/gigahorse/gigahorse-toolchain/gigahorse.py {related_address}.hex")
            run_gigahorse_command(f"cd /app/.temp/{related_address}/out && python3 /opt/gigahorse/gigahorse-toolchain/clients/visualizeout.py")
            raw_disassembled = run_gigahorse_command(f"cat /app/.temp/{related_address}/out/contract.tac")
            ContractStaticAnalysis.objects.create(
                contract_address=related_address,
                raw=raw_disassembled,
                bytecode_hash=bytecode_hash
            )
        else:
            raw_disassembled = contract_static_analysis.raw
        static_analysis_output[related_address] = {}
        functions_dict = {}
        current = []
        in_func = False
        # print(static_analysis_output[related_address]["raw"])
        function_name = ''
        for line in raw_disassembled.split("\n"):
            # Начало новой функции
            if not in_func and '{' in line:
                function_name = line
                in_func = True
                current = []

            if in_func:
                current.append(line)
                if '}' in line:
                    functions_dict[function_name] = ''.join(current)
                    in_func = False
        static_analysis_output[related_address]["functions"] = functions_dict
        static_analysis_output[related_address]["decoded_functions"] = []
        for function_name, function_code in static_analysis_output[related_address]["functions"].items():
            function_exists = DisassembledContractFunction.objects.filter(function_name=function_name, contract_address=related_address).first()
            if not function_exists:
                print(function_name)
                llm_response = call_openai_one_function(function_code, "o4-mini")
                DisassembledContractFunction.objects.create(
                    function_name=function_name,
                    contract_address=related_address,
                    function_code=llm_response,
                    solidity_code=function_code
                )
            else:
                llm_response = function_exists.function_code
            static_analysis_output[related_address]["decoded_functions"].append(llm_response)
        total_decoded_functions = ""
        for func in static_analysis_output[related_address]["decoded_functions"]:
            total_decoded_functions += f"{func}\n"
        
        compiled_contract = call_openai_compile_contract(total_decoded_functions, "gpt-4o-mini")
        schemas[related_address] = call_openai(compiled_contract, "o4-mini-high")
    result_content = ""
    print(schemas)
    for key, value in schemas.items():
        result_content += f"Диаграма контракта {key}: ```\n{value}\n```\n"
    result_content += f"Trace транзакции пользователя: ```\n{trace['result']['structLogs']}\n```\n"
    openai_response = call_openai_on_schemas(result_content, "gpt-4o-mini")
    return openai_response, schemas, static_analysis_output, trace



