from django.db import migrations, models

def copy_month(apps, schema_editor):
    Paiement = apps.get_model("core", "Paiement")
    for p in Paiement.objects.all():
        # Si l'ancien champ était une date, on récupère le mois
        if hasattr(p, "mois_concerne") and p.mois_concerne:
            try:
                mois_num = p.mois_concerne.month
                p.mois_concerne_int = mois_num
                p.save()
            except Exception:
                # Si la valeur n'est pas exploitable, on met janvier par défaut
                p.mois_concerne_int = 1
                p.save()

class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_alter_paiement_mois_concerne"),  # ta dernière migration
    ]

    operations = [
        # 1. Ajouter un champ temporaire
        migrations.AddField(
            model_name="paiement",
            name="mois_concerne_int",
            field=models.IntegerField(null=True, blank=True),
        ),
        # 2. Copier les données de l'ancien champ vers le nouveau
        migrations.RunPython(copy_month),
        # 3. Supprimer l'ancien champ
        migrations.RemoveField(
            model_name="paiement",
            name="mois_concerne",
        ),
        # 4. Renommer le champ temporaire
        migrations.RenameField(
            model_name="paiement",
            old_name="mois_concerne_int",
            new_name="mois_concerne",
        ),
    ]
