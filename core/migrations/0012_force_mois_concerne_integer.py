from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("core", "0011_alter_paiement_mois_concerne"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paiement",
            name="mois_concerne",
            field=models.IntegerField(null=True, blank=True, default=0),
        ),
    ]
