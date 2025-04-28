from ninja import NinjaAPI, Schema, Body
import requests
import json
from .models import PendingTransaction, User, UserAdress
import os
from .simulate import simulate_transaction
from typing import Any
from web3.auto import Web3


api = NinjaAPI(title="RPC Proxy API", version="1.0.0")
TX_METHODS = {
    "eth_sendRawTransaction",
    "eth_sendTransaction",
    "personal_sendTransaction"
}

@api.get("/")
def root(request):
    return {"message": "Welcome to the RPC Proxy API"}


@api.get("/health")
def health(request):
    return {"status": "ok"}


@api.post("/")
def process_rpc(request):
    """
    Обрабатывает RPC запросы
    """
    try:
        # Для работы с FastAPI получаем тело запроса напрямую из переданных данных
        body_bytes = request.body
        body = json.loads(body_bytes)
    except:
        # В случае ошибки пробуем получить из атрибута
        body = request.json()
    # Обрабатываем запрос как batch, если это массив
    is_batch = isinstance(body, list)
    requests_from_body = body if is_batch else [body]
    
    responses = []
    
    for req in requests_from_body:
        method = req.get("method")
        # Проверяем, является ли метод методом отправки транзакции
        if method == "eth_getTransactionReceipt":
            existed_tx = PendingTransaction.objects.filter(transaction_id=req.get("params")[0]).first()
            if existed_tx and not existed_tx.pending and not existed_tx.confirmed:
                responses.append({
                    "id": req.get("id"),
                    "jsonrpc": "2.0",
                    "value": {
                        "code": -32000,
                        "message": "nonce too low"
                    },
                    "error": {
                        "code": -32000,
                        "message": "nonce too low"
                    }
                })
                continue
        if method in TX_METHODS:
            # Создаем новую транзакцию через наш API
            existed_tx = PendingTransaction.objects.filter(raw_transaction=req.get("params")[0]).first()
            if existed_tx:
                if existed_tx.confirmed and not existed_tx.pending:
                    responses.append({
                        "id": req.get("id"),
                        "jsonrpc": "2.0",
                        "result": existed_tx.transaction_id
                    })
                elif not existed_tx.confirmed and not existed_tx.pending:
                    responses.append({
                        "jsonrpc": "2.0",
                        "value": {
                            "code": -32000,
                            "message": "nonce too low"
                        },
                        "error": {
                            "code": -32000,
                            "message": "nonce too low"
                        },
                        "id": req.get("id")
                    })
                continue
            else:
                result, tx_hash, from_address = simulate_transaction(req.get("params")[0])
            address = UserAdress.objects.get(address=from_address)
            pending_transaction = PendingTransaction.objects.filter(transaction_id=tx_hash).first()
            if not pending_transaction:
                transaction_object = PendingTransaction.objects.create(
                    raw_data=req,
                    address=address,
                    data=result,
                    raw_transaction=req.get("params")[0],
                    transaction_id=tx_hash
                )
                requests.post(
                    "http://telegram-bot:8000/notify-transaction",
                    json={
                        "chat_id": address.user.chat_id,
                        "tx_id": transaction_object.id
                    }
                )
            # Формируем ответ клиенту
            responses.append({
                "id": req.get("id"),
                "jsonrpc": req.get("jsonrpc", "2.0"),
                "result": tx_hash
            })
            
        else:
            # Проксируем запрос к Ethereum ноде в асинхронном режиме
            try:
                ethereum_response = requests.post(
                    os.environ.get('ETHEREUM_RPC_URL'),
                    json=req,
                    headers={"Content-Type": "application/json"}
                )
                if ethereum_response.status_code == 200:
                    responses.append(ethereum_response.json())
                else:
                    error_msg = f"Ethereum node returned error: {ethereum_response.text}"
                    responses.append({
                        "id": req.get("id"),
                        "jsonrpc": req.get("jsonrpc", "2.0"),
                        "error": {
                            "code": ethereum_response.status_code,
                            "message": error_msg
                        }
                    })
            except Exception as e:
                error_msg = f"Internal error: {str(e)}"
                responses.append({
                    "id": req.get("id"),
                    "jsonrpc": req.get("jsonrpc", "2.0"),
                    "error": {
                        "code": -32603,
                        "message": error_msg
                    }
                })
    
    # Возвращаем результат в соответствующем формате (batch или single)
    return responses if is_batch else responses[0] 

class NewUserInput(Schema):
    user_id: str | None = None
    chat_id: str | None = None

class NewUserOutput(Schema):
    status: str
    message: str | None = None
    user_id: str | None = None

@api.post("/new_user", response=NewUserOutput)
def new_user(request, payload: NewUserInput):
    try:
        user = User.objects.get_or_create(telegram_id=payload.user_id, chat_id=payload.chat_id)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@api.post("/get_user_id", response=NewUserOutput)
def get_user_id(request, payload: NewUserInput):
    try:
        user = User.objects.get(telegram_id=payload.user_id)
        return {"status": "success", "user_id": user.telegram_id}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class AddAddressInput(Schema):
    user_id: str
    address: str

class AddAddressOutput(Schema):
    status: str
    message: str | None = None

@api.post("/add_address", response=AddAddressOutput)
def add_address(request, payload: AddAddressInput):
    try:
        user = User.objects.get(telegram_id=payload.user_id)
        UserAdress.objects.create(user=user, address=payload.address)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class RemoveAddressInput(Schema):
    user_id: str
    address: str

class RemoveAddressOutput(Schema):
    status: str
    message: str | None = None

@api.post("/remove_address", response=RemoveAddressOutput)
def remove_address(request, payload: RemoveAddressInput):
    try:
        user = User.objects.get(telegram_id=payload.user_id)
        address = UserAdress.objects.get(user=user, address=payload.address)
        address.delete()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class GetUserAddressesInput(Schema):
    user_id: str

class GetUserAddressesOutput(Schema):
    status: str
    addresses: list[str] | None = None
    message: str | None = None

@api.post("/get_user_addresses", response=GetUserAddressesOutput)
def get_user_addresses(request, payload: GetUserAddressesInput):
    try:
        user = User.objects.get(telegram_id=payload.user_id)
        addresses = UserAdress.objects.filter(user=user)
        return {"status": "success", "addresses": list(addresses.values_list('address', flat=True))}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class GetPendingTransactionsInput(Schema):
    user_id: str

class GetPendingTransactionsOutput(Schema):
    status: str
    transactions: list[str] | None = None
    message: str | None = None

@api.post("/get_pending_transactions", response=GetPendingTransactionsOutput)
def get_pending_transactions(request, payload: GetPendingTransactionsInput):
    try:
        pending_transactions = PendingTransaction.objects.filter(user__telegram_id=payload.user_id, pending=True)
        return {"status": "success", "transactions": list(pending_transactions.values_list('id', flat=True))}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class GetTransactionInput(Schema):
    tx_id: Any

class GetTransactionOutput(Schema):
    status: str
    transaction: dict
    pending: bool
    confirmed: bool
    message: str | None = None

@api.post("/get_transaction", response=GetTransactionOutput)
def get_transaction(request, payload: GetTransactionInput):
    try:
        transaction = PendingTransaction.objects.get(id=payload.tx_id)
        return {"status": "success", "transaction": transaction.data, "pending": transaction.pending, "confirmed": transaction.confirmed}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class ConfirmTransactionInput(Schema):
    tx_id: str

class ConfirmTransactionOutput(Schema):
    status: str
    message: str | None = None

@api.post("/confirm-transaction", response=ConfirmTransactionOutput)
def confirm_transaction(request, payload: ConfirmTransactionInput):
    try:
        transaction = PendingTransaction.objects.get(id=payload.tx_id)
        transaction.confirmed = True
        transaction.pending = False
        transaction.save()
        # send web3 raw transaction
        requests.post(
            os.environ.get('ETHEREUM_RPC_URL'),
            json=transaction.raw_data,
            headers={"Content-Type": "application/json"}
        )
        rpc_w3 = Web3(Web3.HTTPProvider(os.environ.get('ETHEREUM_RPC_URL')))
        block_number = rpc_w3.eth.get_block_number()
        params = [{
            "forking": {
                "jsonRpcUrl": os.environ.get('ETHEREUM_RPC_URL'),
                "blockNumber": block_number
            }
        }]
        w3 = Web3(Web3.HTTPProvider("http://hardhat-network:8545", request_kwargs={"timeout": 100}))
        w3.manager.request_blocking("hardhat_reset", params)
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class RejectTransactionInput(Schema):
    tx_id: str

class RejectTransactionOutput(Schema):
    status: str
    message: str | None = None

@api.post("/reject-transaction", response=RejectTransactionOutput)
def reject_transaction(request, payload: RejectTransactionInput):
    try:
        transaction = PendingTransaction.objects.get(id=payload.tx_id)
        transaction.pending = False
        transaction.confirmed = False
        transaction.save()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}






