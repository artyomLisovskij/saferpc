from django.contrib import admin
from .models import User, UserAdress, PendingTransaction

# Register your models here.
admin.site.register(User)
admin.site.register(UserAdress)
admin.site.register(PendingTransaction)

