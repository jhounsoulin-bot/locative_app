from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from decimal import Decimal


class AdminCompte(models.Model):
    username = models.CharField(max_length=100, unique=True)
    password = models.CharField(max_length=255)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return self.username


# ── Hiérarchie géographique ──

class Commune(models.Model):
    nom = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nom

    class Meta:
        ordering = ['nom']


class Arrondissement(models.Model):
    nom     = models.CharField(max_length=100)
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE, related_name='arrondissements')

    def __str__(self):
        return f"{self.nom} ({self.commune.nom})"

    class Meta:
        ordering = ['commune__nom', 'nom']
        unique_together = ['nom', 'commune']


class Quartier(models.Model):
    nom            = models.CharField(max_length=100)
    arrondissement = models.ForeignKey(Arrondissement, on_delete=models.CASCADE, related_name='quartiers')

    def __str__(self):
        return f"{self.nom} — {self.arrondissement.nom}"

    class Meta:
        ordering = ['arrondissement__nom', 'nom']
        unique_together = ['nom', 'arrondissement']


class Zone(models.Model):
    nom      = models.CharField(max_length=100)
    quartier = models.ForeignKey(Quartier, on_delete=models.CASCADE, related_name='zones')

    def __str__(self):
        return f"{self.nom} — {self.quartier.nom}"

    class Meta:
        ordering = ['quartier__nom', 'nom']
        unique_together = ['nom', 'quartier']


# ── Terrain (bloc avant morcellement) ──

class Terrain(models.Model):
    reference            = models.CharField(max_length=50, unique=True)
    zone                 = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='terrains')
    superficie_ha        = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="Superficie (ha)")
    nb_parcelles_prevues = models.IntegerField(default=0, verbose_name="Nb parcelles prévues")
    plan                 = models.FileField(upload_to='plans/terrains/', blank=True, null=True)
    description          = models.TextField(blank=True)
    created_at           = models.DateTimeField(auto_now_add=True)

    @property
    def superficie_m2(self):
        return self.superficie_ha * Decimal('10000')

    @property
    def nb_parcelles_reelles(self):
        return self.parcelles.count()

    @property
    def superficie_disponible_m2(self):
        return sum(
            p.superficie_m2 for p in self.parcelles.filter(statut='disponible')
        )

    @property
    def superficie_vendue_m2(self):
        return sum(
            p.superficie_m2 for p in self.parcelles.filter(statut='vendue')
        )

    def __str__(self):
        return f"{self.reference} — {self.zone}"

    class Meta:
        ordering = ['zone__nom', 'reference']


# ── Parcelle (morceau du terrain) ──

class Parcelle(models.Model):
    STATUT_CHOICES = [
        ('disponible', 'Disponible'),
        ('reservee',   'Réservée'),
        ('vendue',     'Vendue'),
    ]

    reference    = models.CharField(max_length=50, unique=True)
    terrain      = models.ForeignKey(Terrain, on_delete=models.CASCADE, related_name='parcelles')
    superficie_m2 = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Superficie (m²)")
    prix_total   = models.DecimalField(max_digits=15, decimal_places=2)
    plan         = models.FileField(upload_to='plans/parcelles/', blank=True, null=True)
    statut       = models.CharField(max_length=20, choices=STATUT_CHOICES, default='disponible')
    created_at   = models.DateTimeField(auto_now_add=True)

    @property
    def superficie_ha(self):
        return self.superficie_m2 / Decimal('10000')

    @property
    def zone(self):
        return self.terrain.zone

    @property
    def quartier(self):
        return self.terrain.zone.quartier

    @property
    def arrondissement(self):
        return self.terrain.zone.quartier.arrondissement

    @property
    def commune(self):
        return self.terrain.zone.quartier.arrondissement.commune

    def __str__(self):
        return f"{self.reference} ({self.statut})"

    class Meta:
        ordering = ['terrain__zone__nom', 'reference']


# ── Acheteur ──

class Acheteur(models.Model):
    nom       = models.CharField(max_length=150)
    telephone = models.CharField(max_length=30)
    email     = models.EmailField(blank=True)
    adresse   = models.TextField(blank=True)

    def __str__(self):
        return self.nom

    class Meta:
        ordering = ['nom']


# ── Vente ──

class Vente(models.Model):
    MODE_CHOICES = [
        ('comptant',  'Comptant'),
        ('echelonne', 'Échelonné'),
    ]

    parcelle      = models.OneToOneField(Parcelle, on_delete=models.CASCADE, related_name='vente')
    acheteur      = models.ForeignKey(Acheteur, on_delete=models.CASCADE, related_name='ventes')
    date_vente    = models.DateField()
    mode_paiement = models.CharField(max_length=20, choices=MODE_CHOICES)
    remarque      = models.TextField(blank=True)

    @property
    def montant_verse(self):
        return sum(t.montant for t in self.tranches.all()) or Decimal('0')

    @property
    def solde_restant(self):
        return self.parcelle.prix_total - self.montant_verse

    @property
    def est_solde(self):
        return self.solde_restant <= 0

    def __str__(self):
        return f"Vente {self.parcelle.reference} → {self.acheteur.nom}"

    class Meta:
        ordering = ['-date_vente']


# ── Tranche de paiement ──

class Tranche(models.Model):
    vente         = models.ForeignKey(Vente, on_delete=models.CASCADE, related_name='tranches')
    montant       = models.DecimalField(max_digits=15, decimal_places=2)
    date_paiement = models.DateField()
    remarque      = models.TextField(blank=True)

    def __str__(self):
        return f"{self.vente.parcelle.reference} — {self.montant} FCFA"

    class Meta:
        ordering = ['date_paiement']