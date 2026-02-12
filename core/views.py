from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape   # ✅ ajout du paysage
from reportlab.lib.units import cm
from decimal import Decimal
from .models import Proprietaire, Locataire, Paiement
from .forms import ProprietaireForm, LocataireForm, PaiementForm
from django.views.decorators.cache import cache_page




def dashboard(request):
    return render(request, "core/dashboard.html")


# Liste des mois en français
MOIS_FR = [
    "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
]

# -------------------------
# FACTURE PDF PAR PROPRIÉTAIRE
# -------------------------
def facture_proprietaire(request, proprietaire_id):
    proprietaire = Proprietaire.objects.get(id=proprietaire_id)
    paiements = Paiement.objects.filter(locataire__proprietaire=proprietaire)

    total_loyers_locataires = sum([l.loyer_mensuel for l in proprietaire.locataire_set.all()])
    total_recu = sum([p.montant for p in paiements])
    loyer_restant = total_loyers_locataires - total_recu
    commission = total_recu * Decimal('0.1')

    mois_facture = ""
    if paiements.exists():
        mois_num = paiements.first().mois_concerne.month
        mois_facture = MOIS_FR[mois_num]

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="facture_{proprietaire.nom}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Titre
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, height - 50, "FACTURE MENSUELLE NIVAL IMPACT")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, height - 70, f"Mois de la facture : {mois_facture}")

    # Tableau infos principales
    info_y = height - 120
    row_height = 20
    col_x = [2 * cm, 10 * cm]
    col_widths = [8 * cm, 8 * cm]

    infos = [
        ("Propriétaire", proprietaire.nom),
        ("Montant total loyers locataires", f"{total_loyers_locataires:.2f}"),  # ✅ formatage
        ("Total loyers reçus", f"{total_recu:.2f}"),
        ("Loyer restant (impayés)", f"{loyer_restant:.2f}"),
        ("Commission entreprise", f"{commission:.2f}")
    ]

    p.setFont("Helvetica", 11)
    for label, value in infos:
        p.rect(col_x[0], info_y, col_widths[0], row_height, stroke=1, fill=0)
        p.rect(col_x[1], info_y, col_widths[1], row_height, stroke=1, fill=0)
        p.drawString(col_x[0] + 5, info_y + 5, label)
        p.drawString(col_x[1] + 5, info_y + 5, value)
        info_y -= row_height

    # Tableau des locataires
    y_start = info_y - 40
    row_height = 20
    col_x = [2 * cm, 9 * cm, 14 * cm]
    col_widths = [7 * cm, 5 * cm, 5 * cm]

    p.setFont("Helvetica-Bold", 12)
    headers = ["Locataire", "Montant payé", "Statut"]
    for i, header in enumerate(headers):
        p.rect(col_x[i], y_start, col_widths[i], row_height, stroke=1, fill=0)
        p.drawCentredString(col_x[i] + col_widths[i]/2, y_start + 5, header)

    y = y_start - row_height
    p.setFont("Helvetica", 11)
    for locataire in proprietaire.locataire_set.all():
        paiement = paiements.filter(locataire=locataire).first()
        montant = paiement.montant if paiement else Decimal('0.00')
        statut = "Payé" if paiement else "Impayé"

        p.rect(col_x[0], y, col_widths[0], row_height, stroke=1, fill=0)
        p.rect(col_x[1], y, col_widths[1], row_height, stroke=1, fill=0)
        p.rect(col_x[2], y, col_widths[2], row_height, stroke=1, fill=0)

        p.drawString(col_x[0] + 5, y + 5, locataire.nom)
        p.drawString(col_x[1] + 5, y + 5, f"{montant:.2f}")   # ✅ formatage
        p.drawString(col_x[2] + 5, y + 5, statut)
        y -= row_height

    # Signatures
    signature_y = y - 40
    p.setFont("Helvetica", 12)
    p.drawString(2 * cm, signature_y, "Signature du gestionnaire")
    p.drawString(width - 7 * cm, signature_y, "Signature du propriétaire")

    p.showPage()
    p.save()
    return response


# -------------------------
# DASHBOARD HTML
# -------------------------
def dashboard(request):
    mois = request.GET.get("mois")
    proprietaire_id = request.GET.get("proprietaire")

    if proprietaire_id:
        proprietaire = Proprietaire.objects.get(id=proprietaire_id)
        locataires_qs = proprietaire.locataire_set.all()
        paiements = Paiement.objects.filter(locataire__proprietaire=proprietaire)
    else:
        proprietaire = None
        locataires_qs = Locataire.objects.all()
        paiements = Paiement.objects.all()

    if mois:
        paiements = paiements.filter(mois_concerne__month=int(mois))

    proprietaires_count = Proprietaire.objects.count()
    locataires_count = locataires_qs.count()

    total_loyers_locataires = sum([l.loyer_mensuel for l in locataires_qs])
    total_recu = sum([p.montant for p in paiements])
    loyer_restant = total_loyers_locataires - total_recu
    commission_totale = total_recu * Decimal('0.1')

    locataires_payes = paiements.values_list("locataire", flat=True).distinct().count()
    locataires_impayes = locataires_count - locataires_payes

    # Préparer une liste de locataires avec paiement et statut
    locataires_data = []
    for locataire in locataires_qs:
        paiement = paiements.filter(locataire=locataire).first()
        montant = paiement.montant if paiement else Decimal('0.00')
        statut = "Payé" if paiement else "Impayé"
        locataires_data.append({
            "nom": locataire.nom,
            "montant": montant,
            "statut": statut
        })

    context = {
        "proprietaires_count": proprietaires_count,
        "locataires_count": locataires_count,
        "total_loyers_locataires": total_loyers_locataires,
        "total_recu": total_recu,
        "loyer_restant": loyer_restant,
        "commission_totale": commission_totale,
        "locataires_payes": locataires_payes,
        "locataires_impayes": locataires_impayes,
        "mois": mois,
        "proprietaire": proprietaire,
        "proprietaires": Proprietaire.objects.all(),
        "locataires_data": locataires_data,  # ✅ nouvelle variable
    }
    return render(request, "core/dashboard.html", context)


# -------------------------
# DASHBOARD PDF
# -------------------------
def dashboard_pdf(request):
    mois = request.GET.get("mois")
    proprietaire_id = request.GET.get("proprietaire")

    # Filtrer par propriétaire si sélectionné
    if proprietaire_id:
        proprietaire = Proprietaire.objects.get(id=proprietaire_id)
        locataires_qs = proprietaire.locataire_set.all()
        paiements = Paiement.objects.filter(locataire__proprietaire=proprietaire)
    else:
        proprietaire = None
        locataires_qs = Locataire.objects.all()
        paiements = Paiement.objects.all()

    # Filtrer par mois si sélectionné
    if mois:
        paiements = paiements.filter(mois_concerne__month=int(mois))

    # Calculs principaux
    total_loyers_locataires = sum([l.loyer_mensuel for l in locataires_qs])
    total_recu = sum([p.montant for p in paiements])
    loyer_restant = total_loyers_locataires - total_recu
    commission_totale = total_recu * Decimal('0.1')

    locataires_payes = paiements.values_list("locataire", flat=True).distinct().count()
    locataires_impayes = locataires_qs.count() - locataires_payes

    # Déterminer le mois en français
    mois_facture = ""
    if mois:
        mois_facture = MOIS_FR[int(mois)]

    # Réponse PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="dashboard.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Titre
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width/2, height-50, "RAPPORT GLOBAL LOCATIF")

    # Mois affiché si sélectionné
    if mois_facture:
        p.setFont("Helvetica", 12)
        p.drawCentredString(width/2, height-70, f"Mois : {mois_facture}")

    # Contenu du rapport
    y = height-110
    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Nombre de propriétaires : {Proprietaire.objects.count()}")
    y -= 20
    p.drawString(50, y, f"Nombre de locataires : {locataires_qs.count()}")
    y -= 20
    p.drawString(50, y, f"Montant total loyers locataires : {total_loyers_locataires}")
    y -= 20
    p.drawString(50, y, f"Total loyers reçus : {total_recu}")
    y -= 20
    p.drawString(50, y, f"Loyer restant (impayés) : {loyer_restant}")
    y -= 20
    p.drawString(50, y, f"Commission totale entreprise : {commission_totale}")
    y -= 40
    p.drawString(50, y, f"Locataires payés : {locataires_payes}")
    y -= 20
    p.drawString(50, y, f"Locataires impayés : {locataires_impayes}")

    # Signatures
    y -= 60
    p.setFont("Helvetica", 12)
    p.drawString(50, y, "Signature du gestionnaire")
    p.drawString(width-200, y, "Signature du propriétaire")

    p.showPage()
    p.save()
    return response



def accueil(request):
    mois = request.GET.get("mois")

    proprietaires = Proprietaire.objects.all()
    locataires = Locataire.objects.all()
    paiements = Paiement.objects.all()

    if mois:
        paiements = paiements.filter(mois_concerne__month=int(mois))

    total_loyers = sum([l.loyer_mensuel for l in locataires])
    total_recu = sum([p.montant for p in paiements])
    commission = total_recu * Decimal('0.1')

    # ✅ Liste des locataires qui n'ont pas payé
    locataires_non_payes = []
    for proprietaire in proprietaires:
        for locataire in proprietaire.locataires.all():   # <-- CORRECT
            paiement_existe = paiements.filter(locataire=locataire).exists()
            if not paiement_existe:
                locataires_non_payes.append({
                    "proprietaire": proprietaire,
                    "locataire": locataire,
                })

    # ✅ dictionnaire {locataire_id: loyer}
    loyers_dict = {str(locataire.id): float(locataire.loyer_mensuel) for locataire in locataires}

    context = {
        "proprietaires": proprietaires,
        "locataires": locataires,
        "locataires_count": locataires.count(),
        "proprietaires_count": proprietaires.count(),
        "total_loyers": total_loyers,
        "total_recu": total_recu,
        "commission": commission,
        "mois": mois,
        "mois_list": range(1, 13),
        "locataires_non_payes": locataires_non_payes,
        "non_payes_count": len(locataires_non_payes),
        "proprietaire_form": ProprietaireForm(),
        "locataire_form": LocataireForm(),
        "paiement_form": PaiementForm(),
        "loyers_dict": loyers_dict,
    }

    return render(request, "core/accueil.html", context)



@cache_page(60 * 5)  # cache 5 minutes
def rapport_proprietaire(request, proprietaire_id):
    ...

    proprietaire = get_object_or_404(Proprietaire.objects.prefetch_related("locataires"), id=proprietaire_id)
    locataires = proprietaire.locataires.all()   # relation inverse correcte
    paiements = Paiement.objects.filter(locataire__proprietaire=proprietaire).select_related("locataire")

    mois = request.GET.get("mois")
    mois_rapport = ""
    if mois:
        mois_int = int(mois)
        paiements = paiements.filter(mois_concerne__month=mois_int)
        mois_rapport = MOIS_FR[mois_int]

    total_loyers = sum([l.loyer_mensuel for l in locataires])
    total_paye = sum([p.montant for p in paiements])
    commission = total_paye * Decimal("0.1")

    locataires_data = []
    for locataire in locataires:
        paiement_existe = paiements.filter(locataire=locataire).exists()
        statut = "Payé" if paiement_existe else "Non payé"
        locataires_data.append({
            "nom": locataire.nom,
            "loyer": locataire.loyer_mensuel,
            "statut": statut,
        })

    context = {
        "proprietaire": proprietaire,
        "total_loyers": total_loyers,
        "total_paye": total_paye,
        "commission": commission,
        "locataires_data": locataires_data,
        "mois_list": [(i, MOIS_FR[i]) for i in range(1, 13)],
        "mois_rapport": mois_rapport,
        "mois": mois,
    }
    return render(request, "core/rapport_proprietaire.html", context)

def ajouter_proprietaire(request):
    if request.method == "POST":
        form = ProprietaireForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("accueil")
    else:
        form = ProprietaireForm()
    return render(request, "core/ajouter_proprietaire.html", {"form": form})

def ajouter_locataire(request):
    if request.method == "POST":
        form = LocataireForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("accueil")
    else:
        form = LocataireForm()
    return render(request, "core/ajouter_locataire.html", {"form": form})





def ajouter_paiement(request):
    proprietaire_id = request.GET.get("proprietaire")

    if request.method == "POST":
        form = PaiementForm(request.POST, proprietaire_id=proprietaire_id)
        if form.is_valid():
            paiement = form.save()
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": True, "id": paiement.id})
            return redirect("accueil")
        else:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "errors": form.errors}, status=400)
    else:
        form = PaiementForm(proprietaire_id=proprietaire_id)

    return render(request, "core/ajouter_paiement.html", {"form": form})






def paiement_create(request, proprietaire_id):
    proprietaire = get_object_or_404(Proprietaire, id=proprietaire_id)
    locataires = Locataire.objects.filter(proprietaire=proprietaire)

    if request.method == "POST":
        form = PaiementForm(request.POST)
        if form.is_valid():
            paiement = form.save(commit=False)
            paiement.proprietaire = proprietaire
            paiement.save()
            return redirect("paiement_list")
    else:
        form = PaiementForm()

    return render(request, "core/paiement_form.html", {
        "form": form,
        "proprietaire": proprietaire,
        "locataires": locataires,
    })




# Modifier un propriétaire
def modifier_proprietaire(request, pk):
    proprietaire = get_object_or_404(Proprietaire, pk=pk)
    if request.method == "POST":
        form = ProprietaireForm(request.POST, instance=proprietaire)
        if form.is_valid():
            form.save()
            return redirect("accueil")
    else:
        form = ProprietaireForm(instance=proprietaire)
    return render(request, "core/modifier_proprietaire.html", {"form": form})

# Supprimer un propriétaire
def supprimer_proprietaire(request, pk):
    proprietaire = get_object_or_404(Proprietaire, pk=pk)
    if request.method == "POST":
        proprietaire.delete()
        return redirect("accueil")
    return render(request, "core/supprimer_proprietaire.html", {"proprietaire": proprietaire})


# Modifier un locataire
def modifier_locataire(request, pk):
    locataire = get_object_or_404(Locataire, pk=pk)
    if request.method == "POST":
        form = LocataireForm(request.POST, instance=locataire)
        if form.is_valid():
            form.save()
            return redirect("accueil")
    else:
        form = LocataireForm(instance=locataire)
    return render(request, "core/modifier_locataire.html", {"form": form})

# Supprimer un locataire
def supprimer_locataire(request, pk):
    locataire = get_object_or_404(Locataire, pk=pk)
    if request.method == "POST":
        locataire.delete()
        return redirect("accueil")
    return render(request, "core/supprimer_locataire.html", {"locataire": locataire})


def get_loyer(request, locataire_id):
    try:
        locataire = Locataire.objects.get(id=locataire_id)
        return JsonResponse({"loyer": float(locataire.loyer_mensuel)})
    except Locataire.DoesNotExist:
        return JsonResponse({"error": "Locataire introuvable"}, status=404)


def get_locataires_by_proprietaire_nom(request, proprietaire_nom):
    print("DEBUG - Propriétaire reçu :", proprietaire_nom)  # affiche dans la console
    locataires = Locataire.objects.filter(proprietaire__nom=proprietaire_nom)
    print("DEBUG - Locataires trouvés :", list(locataires))  # affiche la liste des objets

    data = [{"id": l.id, "nom": l.nom} for l in locataires]
    print("DEBUG - JSON renvoyé :", data)  # affiche le JSON final

    return JsonResponse(data, safe=False)





def get_locataires(request, proprietaire_id):
    locataires = Locataire.objects.filter(proprietaire_id=proprietaire_id)
    data = [{"id": l.id, "nom": l.nom} for l in locataires]
    return JsonResponse({"locataires": data})



MOIS_FR = { 1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 
           5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août", 
           9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre" 
        }

def rapport_global(request):
    mois = request.GET.get("mois")
    proprietaires = Proprietaire.objects.prefetch_related("locataires")
    data = []

    for proprietaire in proprietaires:
        locataires = proprietaire.locataires.all()
        paiements = Paiement.objects.filter(locataire__in=locataires)

        # ✅ Filtrer par mois si sélectionné
        if mois:
            paiements = paiements.filter(mois_concerne__month=int(mois))

        total_loyers = sum([l.loyer_mensuel for l in locataires])
        total_paye = sum([p.montant for p in paiements])
        commission = total_paye * Decimal("0.1")

        locataires_non_payes = [
            l.nom for l in locataires
            if not paiements.filter(locataire=l).exists()
        ]

        data.append({
            "proprietaire": proprietaire.nom,
            "total_loyers": total_loyers,
            "total_paye": total_paye,
            "non_paye": total_loyers - total_paye,
            "commission": commission,
            "locataires_non_payes": locataires_non_payes,
        })

    context = {
        "rapport": data,
        "mois_list": [(i, MOIS_FR[i]) for i in range(1, 13)],
        "mois": mois,
    }
    return render(request, "core/rapport_global.html", context)


def rapport_proprietaire_pdf(request, proprietaire_id):
    mois = request.GET.get("mois")
    proprietaire = get_object_or_404(Proprietaire, id=proprietaire_id)
    locataires = proprietaire.locataires.all()
    paiements = Paiement.objects.filter(locataire__in=locataires)

    if mois:
        paiements = paiements.filter(mois_concerne__month=int(mois))

    # Totaux
    total_loyers = sum([l.loyer_mensuel for l in locataires])
    total_paye = sum([p.montant for p in paiements])
    commission = total_paye * Decimal("0.1")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_proprietaire_{proprietaire.nom}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # ✅ Titre
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width/2, height-50, "RAPPORT MENSUEL NIVAL IMPACT")

    # ✅ Mois du rapport juste en dessous
    p.setFont("Helvetica", 12)
    if mois:
        try:
            mois_num = int(mois)
            p.drawCentredString(width/2, height-70, f"Mois du rapport : {MOIS_FR[mois_num]}")
        except (ValueError, KeyError):
            p.drawCentredString(width/2, height-70, "Mois du rapport : Invalide")
    else:
        p.drawCentredString(width/2, height-70, "Mois du rapport : Non spécifié")

    # ✅ Infos propriétaire
    p.setFont("Helvetica", 12)
    p.drawString(50, height-100, f"Propriétaire : {proprietaire.nom}")
    p.drawString(50, height-120, f"Montant total loyers : {total_loyers:.2f} FCFA")
    p.drawString(50, height-140, f"Montant total payé : {total_paye:.2f} FCFA")
    p.drawString(50, height-160, f"Commission agence (10%) : {commission:.2f} FCFA")

    # ✅ Tableau des locataires
    y = height - 200
    row_height = 20
    col_x = [50, 250, 400]
    col_widths = [200, 150, 150]

    headers = ["Locataire", "Loyer", "Statut"]
    p.setFont("Helvetica-Bold", 12)
    for i, header in enumerate(headers):
        p.rect(col_x[i], y, col_widths[i], row_height, stroke=1, fill=0)
        p.drawCentredString(col_x[i] + col_widths[i]/2, y+5, header)

    y -= row_height
    p.setFont("Helvetica", 11)

    for locataire in locataires:
        loyer = locataire.loyer_mensuel
        paiement = paiements.filter(locataire=locataire).first()
        statut = "Payé" if paiement else "Non payé"

        values = [locataire.nom, f"{loyer:.2f} FCFA", statut]
        for i, val in enumerate(values):
            p.rect(col_x[i], y, col_widths[i], row_height, stroke=1, fill=0)
            p.drawString(col_x[i]+5, y+5, val)

        y -= row_height
        if y < 100:
            p.showPage()
            y = height - 100

    # ✅ Signatures
    y -= 40
    p.setFont("Helvetica", 12)
    p.drawString(50, y, "Signature du gestionnaire")
    p.drawString(width-200, y, "Signature du propriétaire")

    p.showPage()
    p.save()
    return response







def liste_paiements(request):
    paiements = Paiement.objects.select_related("locataire", "proprietaire").all().order_by("-date_paiement")
    return render(request, "core/liste_paiements.html", {"paiements": paiements})



def rapport_global_pdf(request):
    mois = request.GET.get("mois")
    proprietaires = Proprietaire.objects.prefetch_related("locataires")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="rapport_global.pdf"'

    p = canvas.Canvas(response, pagesize=landscape(A4))
    width, height = landscape(A4)

    # ✅ Titre
    p.setFont("Helvetica-Bold", 16)
    titre = "RAPPORT GLOBAL MENSUEL NIVAL IMPACT"
    if mois:
        titre += f" - {MOIS_FR[int(mois)]}"
    p.drawCentredString(width/2, height-50, titre)

    # Position de départ
    y = height - 100
    row_height = 20

    # Colonnes
    col_x = [1 * cm, 7 * cm, 11 * cm, 15 * cm, 19 * cm, 23 * cm]
    col_widths = [6 * cm, 4 * cm, 4 * cm, 4 * cm, 4 * cm, 8 * cm]

    # En-têtes
    p.setFont("Helvetica-Bold", 12)
    headers = ["Propriétaire", "Total loyers", "Total payé", "Non payé", "Commission", "Locataires non payés"]
    for i, header in enumerate(headers):
        p.rect(col_x[i], y, col_widths[i], row_height, stroke=1, fill=0)
        p.drawCentredString(col_x[i] + col_widths[i]/2, y + 5, header)

    y -= row_height

    # Totaux globaux
    total_loyers_global = 0
    total_paye_global = 0
    total_non_paye_global = 0
    total_commission_global = 0

    # Données par propriétaire
    for proprietaire in proprietaires:
        locataires = proprietaire.locataires.all()
        paiements = Paiement.objects.filter(locataire__in=locataires)

        if mois:
            paiements = paiements.filter(mois_concerne__month=int(mois))

        total_loyers = sum([l.loyer_mensuel for l in locataires])
        total_paye = sum([p.montant for p in paiements])
        non_paye = total_loyers - total_paye
        commission = total_paye * Decimal("0.1")

        total_loyers_global += total_loyers
        total_paye_global += total_paye
        total_non_paye_global += non_paye
        total_commission_global += commission

        locataires_non_payes = [l.nom for l in locataires if not paiements.filter(locataire=l).exists()]
        locataires_lines = locataires_non_payes if locataires_non_payes else ["✅ Tous ont payé"]
        cell_height = max(row_height, len(locataires_lines) * 12)

        values = [
            proprietaire.nom,
            f"{total_loyers:.2f}",
            f"{total_paye:.2f}",
            f"{non_paye:.2f}",
            f"{commission:.2f}"
        ]

        for i, val in enumerate(values):
            p.rect(col_x[i], y, col_widths[i], cell_height, stroke=1, fill=0)
            if i == 0:
                p.drawString(col_x[i] + 5, y + cell_height - 15, val)
            else:
                p.drawCentredString(col_x[i] + col_widths[i]/2, y + cell_height - 15, val)

        # Colonne locataires impayés
        p.rect(col_x[5], y, col_widths[5], cell_height, stroke=1, fill=0)
        text_obj = p.beginText(col_x[5] + 5, y + cell_height - 15)
        text_obj.setFont("Helvetica", 9)
        for line in locataires_lines:
            text_obj.textLine(line)
        p.drawText(text_obj)

        y -= cell_height

        if y < 100:
            p.showPage()
            y = height - 100
            p.setFont("Helvetica-Bold", 12)
            for i, header in enumerate(headers):
                p.rect(col_x[i], y, col_widths[i], row_height, stroke=1, fill=0)
                p.drawCentredString(col_x[i] + col_widths[i]/2, y + 5, header)
            y -= row_height
            p.setFont("Helvetica", 10)

    # Totaux globaux
    p.setFont("Helvetica-Bold", 11)
    totals = [
        "TOTAL GLOBAL",
        f"{total_loyers_global:.2f}",
        f"{total_paye_global:.2f}",
        f"{total_non_paye_global:.2f}",
        f"{total_commission_global:.2f}",
        ""
    ]
    for i, val in enumerate(totals):
        p.rect(col_x[i], y, col_widths[i], row_height, stroke=1, fill=0)
        p.drawCentredString(col_x[i] + col_widths[i]/2, y + 5, val)

    y -= row_height

    # Signatures
    y -= 40
    p.setFont("Helvetica", 12)
    p.drawString(2 * cm, y, "Signature du gestionnaire")
    p.drawString(width - 7 * cm, y, "Signature du propriétaire")

    p.showPage()
    p.save()
    return response






