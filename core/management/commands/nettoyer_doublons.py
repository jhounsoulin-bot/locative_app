from django.core.management.base import BaseCommand
from core.models import Paiement

class Command(BaseCommand):
    help = 'Nettoie les doublons de paiements avant migration'

    def handle(self, *args, **kwargs):
        self.stdout.write("Recherche de doublons...")
        
        tous_paiements = list(Paiement.objects.all().order_by('locataire', 'mois_concerne', 'date_paiement', 'id'))
        
        vus = {}
        a_supprimer = []
        
        for p in tous_paiements:
            # Utiliser l'année de date_paiement
            cle = (p.locataire_id, p.mois_concerne, p.date_paiement.year)
            
            if cle in vus:
                a_supprimer.append(p.id)
                self.stdout.write(f"Doublon trouvé : ID={p.id} - {p}")
            else:
                vus[cle] = p.id
        
        self.stdout.write(f"\nTotal de doublons à supprimer : {len(a_supprimer)}")
        
        if len(a_supprimer) > 0:
            Paiement.objects.filter(id__in=a_supprimer).delete()
            self.stdout.write(self.style.SUCCESS(f"✅ {len(a_supprimer)} doublons supprimés !"))
        else:
            self.stdout.write(self.style.SUCCESS("✅ Aucun doublon trouvé"))