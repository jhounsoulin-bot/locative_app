from django.core.management.base import BaseCommand
from core.models import Paiement
from django.db import transaction

class Command(BaseCommand):
    help = 'Nettoie les doublons de paiements avant migration'

    def handle(self, *args, **kwargs):
        self.stdout.write("Recherche de doublons...")
        
        # ✅ IMPORTANT : On utilise date_paiement.year au lieu du champ annee
        # car le champ annee n'existe pas encore en production
        tous_paiements = list(Paiement.objects.all().order_by('locataire', 'mois_concerne', 'date_paiement', 'id'))
        
        vus = {}
        a_supprimer = []
        
        for p in tous_paiements:
            # ✅ Créer une clé basée sur l'année EXTRAITE de date_paiement
            try:
                annee_paiement = p.date_paiement.year if p.date_paiement else None
                cle = (p.locataire_id, p.mois_concerne, annee_paiement)
                
                if cle in vus:
                    a_supprimer.append(p.id)
                    self.stdout.write(self.style.WARNING(
                        f"Doublon trouvé : ID={p.id} | "
                        f"Locataire={p.locataire_id} | "
                        f"Mois={p.mois_concerne} | "
                        f"Année={annee_paiement}"
                    ))
                else:
                    vus[cle] = p.id
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Erreur sur paiement ID={p.id}: {e}"))
                continue
        
        if not a_supprimer:
            self.stdout.write(self.style.SUCCESS("✅ Aucun doublon trouvé !"))
            return
        
        self.stdout.write(self.style.WARNING(f"⚠️  {len(a_supprimer)} doublons trouvés"))
        
        # Supprimer les doublons dans une transaction
        with transaction.atomic():
            compteur = 0
            for paiement_id in a_supprimer:
                try:
                    paiement = Paiement.objects.get(id=paiement_id)
                    self.stdout.write(f"Suppression : ID={paiement.id}")
                    paiement.delete()
                    compteur += 1
                except Paiement.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"Paiement ID={paiement_id} déjà supprimé"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Erreur lors de la suppression de ID={paiement_id}: {e}"))
        
        self.stdout.write(self.style.SUCCESS(f"✅ {compteur} doublons supprimés avec succès"))