from django.contrib import admin
from .models import User, UserAdress, PendingTransaction, DisassembledContractFunction, ContractStaticAnalysis

# Register your models here.
admin.site.register(User)
admin.site.register(UserAdress)
admin.site.register(PendingTransaction)

class DisassembledContractFunctionAdmin(admin.ModelAdmin):
    list_display = ('contract_address', 'function_name', 'function_code', 'solidity_code')
    search_fields = ('contract_address', 'function_name')

admin.site.register(DisassembledContractFunction, DisassembledContractFunctionAdmin)

class ContractStaticAnalysisAdmin(admin.ModelAdmin):
    list_display = ('contract_address', 'bytecode_hash')
    search_fields = ('contract_address', 'bytecode_hash')

admin.site.register(ContractStaticAnalysis, ContractStaticAnalysisAdmin)
