from django.db import migrations, models

def reset_mois_concerne(apps, schema_editor):
    Paiement = apps.get_model("core", "Paiement")
    for p in Paiement.objects.all():
        # On remet à None pour éviter le cast
        p.mois_concerne = None
        p.save()

class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_force_mois_concerne_integer"),
    ]

    operations = [
        migrations.RunPython(reset_mois_concerne),
        migrations.AlterField(
            model_name="paiement",
            name="mois_concerne",
            field=models.IntegerField(null=True, blank=True, default=0),
        ),
    ]
