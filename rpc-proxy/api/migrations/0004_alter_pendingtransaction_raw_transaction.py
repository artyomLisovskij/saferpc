# Generated by Django 5.2 on 2025-04-28 16:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_pendingtransaction_raw_transaction'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pendingtransaction',
            name='raw_transaction',
            field=models.CharField(max_length=4096),
        ),
    ]
