from django.db import models

# Create your models here.
class User(models.Model):
    telegram_id = models.CharField(max_length=255)
    chat_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class UserAdress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    address = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
class PendingTransaction(models.Model):
    address = models.ForeignKey(UserAdress, on_delete=models.CASCADE)
    transaction_id = models.CharField(max_length=255, unique=True)
    raw_data = models.JSONField()
    raw_transaction = models.CharField(max_length=4096)
    data = models.JSONField()
    confirmed = models.BooleanField(default=False)
    pending = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    analyze_result = models.TextField(blank=True)
    schemas = models.TextField(blank=True)
    static_analysis_output = models.TextField(blank=True)
    trace = models.TextField(blank=True)

class DisassembledContractFunction(models.Model):
    contract_address = models.CharField(max_length=255)
    function_name = models.CharField(max_length=255)
    function_code = models.TextField()
    solidity_code = models.TextField()

class ContractStaticAnalysis(models.Model):
    contract_address = models.CharField(max_length=255)
    raw = models.TextField(blank=True)
    bytecode_hash = models.CharField(max_length=255)
