from django.db import models


class Ville(models.Model):
    nom = models.CharField(max_length=100)

    def __str__(self):
        return self.nom


class Proprietaire(models.Model):
    nom = models.CharField(max_length=100)
    numero = models.CharField(max_length=20, default="0000000000")  # ✅ valeur par défaut

    def __str__(self):
        return self.nom


class Locataire(models.Model):
    nom = models.CharField(max_length=100)
    numero = models.CharField(max_length=20, default="0000000000")
    loyer_mensuel = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # ✅ ajouté
    proprietaire = models.ForeignKey(Proprietaire, on_delete=models.CASCADE)

    def __str__(self):
        return self.nom



class Paiement(models.Model):
    proprietaire = models.ForeignKey(
    "Proprietaire",
    on_delete=models.CASCADE,
    related_name="paiements",
    verbose_name="Propriétaire",
    null=True,   # ✅ autorise vide en base
    blank=True   # ✅ autorise vide dans les formulaires
)
    locataire = models.ForeignKey(
        "Locataire",
        on_delete=models.CASCADE,
        related_name="paiements",
        verbose_name="Locataire"
    )
    date_paiement = models.DateField(verbose_name="Date de paiement")
    mois_concerne = models.DateField(verbose_name="Mois concerné")
    montant = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant")
    paye_en_avance = models.BooleanField(default=False, verbose_name="Payé en avance")

    def __str__(self):
        return f"{self.locataire.nom} - {self.montant} ({self.date_paiement})"



