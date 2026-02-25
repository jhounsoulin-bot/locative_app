from django.db import models
from django.contrib.auth.hashers import make_password, check_password


class AdminCompte(models.Model):
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "Compte Admin"

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
        related_name="locataires",
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
        verbose_name="Propriétaire"
    )
    locataire = models.ForeignKey(
        Locataire,
        on_delete=models.CASCADE,
        related_name="paiements",
        verbose_name="Locataire"
    )
    date_paiement = models.DateField(verbose_name="Date de paiement")
    mois_concerne = models.IntegerField(
        choices=MOIS_CHOICES,
        verbose_name="Mois concerné",
        null=True,
        blank=True
    )
    annee = models.IntegerField(verbose_name="Année", null=True, blank=True)
    montant = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Montant")
    paye_en_avance = models.BooleanField(default=False, verbose_name="Payé en avance")
    
    def save(self, *args, **kwargs):
        # Remplir automatiquement l'année depuis date_paiement
        if self.date_paiement and not self.annee:
            self.annee = self.date_paiement.year
        super().save(*args, **kwargs)
    
    class Meta:  # ✅ Même indentation que def save
        constraints = [
            models.UniqueConstraint(
                fields=['locataire', 'mois_concerne', 'annee'],
                name='unique_paiement_locataire_mois_annee',
            )
        ]

    def __str__(self):  # ✅ Même indentation que class Meta
        mois_label = dict(self.MOIS_CHOICES).get(self.mois_concerne, "Mois inconnu")
        return f"{self.locataire.nom} - {self.montant} FCFA ({mois_label} {self.annee or self.date_paiement.year})"