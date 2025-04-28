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
    raw_transaction = models.CharField(max_length=255)
    data = models.JSONField()
    confirmed = models.BooleanField(default=False)
    pending = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    
