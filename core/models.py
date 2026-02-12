from django.db import models

class Ville(models.Model):
    nom = models.CharField(max_length=100)

    def __str__(self):
        return self.nom


class Proprietaire(models.Model):
    nom = models.CharField(max_length=100)
    numero = models.CharField(max_length=20, default="0000000000")

    def __str__(self):
        return self.nom


class Locataire(models.Model):
    nom = models.CharField(max_length=100)
    numero = models.CharField(max_length=20, default="0000000000")
    loyer_mensuel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    proprietaire = models.ForeignKey(
        Proprietaire,
        on_delete=models.CASCADE,
        related_name="locataires",   # ✅ accès via proprietaire.locataires.all()
        verbose_name="Propriétaire"
    )

    def __str__(self):
        return f"{self.nom} ({self.proprietaire.nom})"


class Paiement(models.Model):
    MOIS_CHOICES = [
        (1, "Janvier"),
        (2, "Février"),
        (3, "Mars"),
        (4, "Avril"),
        (5, "Mai"),
        (6, "Juin"),
        (7, "Juillet"),
        (8, "Août"),
        (9, "Septembre"),
        (10, "Octobre"),
        (11, "Novembre"),
        (12, "Décembre"),
    ]

    proprietaire = models.ForeignKey(
        Proprietaire,
        on_delete=models.CASCADE,
        related_name="paiements",
        verbose_name="Propriétaire",
        null=True,
        blank=True
    )
    locataire = models.ForeignKey(
        Locataire,
        on_delete=models.CASCADE,
        related_name="paiements",
        verbose_name="Locataire"
    )
    date_paiement = models.DateField(verbose_name="Date de paiement")
    mois_concerne = models.DateField(null=True, blank=True)
    montant = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant")
    paye_en_avance = models.BooleanField(default=False, verbose_name="Payé en avance")

    def __str__(self):
        mois_label = dict(self.MOIS_CHOICES).get(self.mois_concerne.month, "") if self.mois_concerne else ""
        return f"{self.locataire.nom} - {self.montant} FCFA ({mois_label} {self.date_paiement.year})"
