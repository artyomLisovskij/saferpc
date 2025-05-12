from eth_account import Account
from web3 import Web3
from hexbytes import HexBytes
from eth_utils import to_int, to_hex, event_abi_to_log_topic
from eth_account.typed_transactions.typed_transaction import TypedTransaction
import traceback
from web3._utils.events import get_event_data
import os


def simulate_transaction(signed_raw):
    w3 = Web3(Web3.HTTPProvider("http://hardhat-network:8545", request_kwargs={"timeout": 100_000}))
    transfer_abi = {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "from",    "type": "address"},
            {"indexed": True,  "name": "to",      "type": "address"},
            {"indexed": False, "name": "value",   "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    }
    approval_abi = {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "name": "owner",   "type": "address"},
            {"indexed": True,  "name": "spender", "type": "address"},
            {"indexed": False, "name": "value",   "type": "uint256"},
        ],
        "name": "Approval",
        "type": "event",
    }
    event_abis = [transfer_abi, approval_abi]
    topic_map = {
        event_abi_to_log_topic(abi).hex(): abi
        for abi in event_abis
    }
    # print("topic_map")
    # print(topic_map)
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
    result = {}
    tx_hash_hex = ''
    try:
        tx_hash = w3.eth.send_raw_transaction(HexBytes(signed_raw))
        print("0x" + tx_hash.hex())
        tx_hash_hex = tx_hash.hex()

        tx: dict = w3.eth.get_transaction(tx_hash)
        # print(tx)
        result = {
            "tx_hash":      tx_hash_hex,
            "from":         tx["from"],
            "to":           tx["to"],
            "value":        tx["value"],
            "gas":          tx["gas"],
            "gasPrice":     tx.get("gasPrice") or tx.get("maxFeePerGas"),
            "input":        "0x" + tx["input"].hex(),
            "type":         tx["type"],
            "nonce":        tx["nonce"],
            "chainId":      tx["chainId"],
            "logs":         []
        }
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        for log in receipt.logs:
            topics = []
            for topic in log["topics"]:
                if isinstance(topic, bytes):
                    topic = topic.hex()
                topics.append(topic)

            adding = {
                "logIndex": log["logIndex"],
                "address":   log["address"],
                "topics":    topics,
                "data":      log["data"].hex(),
            }
            t0 = log["topics"][0]
            if isinstance(t0, bytes):
                t0 = t0.hex()
            abi = topic_map.get(t0.lower())
            print([key for key in topic_map.keys()])
            print(t0)
            if abi:
                ev = get_event_data(w3.codec, abi, log)
                adding["decoded"] = {
                    "event": ev.event,
                    "args":  dict(ev.args),
                }
            result["logs"].append(adding)
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
    # print("eth_call result:", result)
    return result, "0x" + tx_hash_hex, from_address