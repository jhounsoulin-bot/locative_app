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
    locataire = models.ForeignKey(Locataire, on_delete=models.CASCADE)
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    date_paiement = models.DateField()
    mois_concerne = models.DateField()  # le mois du loyer payé
    en_avance = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.locataire.nom} - {self.montant} ({self.date_paiement})"
