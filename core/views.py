from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from decimal import Decimal
from .models import Proprietaire, Locataire, Paiement
from .forms import ProprietaireForm, LocataireForm, PaiementForm




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



def rapport_proprietaire(request, proprietaire_id):
    proprietaire = get_object_or_404(Proprietaire, id=proprietaire_id)
    locataires = proprietaire.locataires.all()   # relation inverse correcte
    paiements = Paiement.objects.filter(locataire__in=locataires)

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
            form.save()
            return redirect("accueil")
    else:
        form = PaiementForm(proprietaire_id=proprietaire_id)

    context = {
        "form": form,
        "proprietaires": Proprietaire.objects.all(),
        "proprietaire_id": proprietaire_id,  # pour garder la sélection
    }
    return render(request, "core/ajouter_paiement.html", context)


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


def rapport_proprietaire_pdf(request, proprietaire_id):
    proprietaire = get_object_or_404(Proprietaire, id=proprietaire_id)
    locataires = proprietaire.locataires.all()   # relation inverse correcte
    paiements = Paiement.objects.filter(locataire__in=locataires)

    mois = request.GET.get("mois")
    mois_rapport = ""
    if mois:
        mois_int = int(mois)
        paiements = paiements.filter(mois_concerne__month=mois_int)
        mois_rapport = MOIS_FR[mois_int]
    elif paiements.exists():
        mois_num = paiements.first().mois_concerne.month
        mois_rapport = MOIS_FR[mois_num]

    total_loyers = sum([l.loyer_mensuel for l in locataires])
    total_paye = sum([p.montant for p in paiements])
    commission = total_paye * Decimal("0.1")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_{proprietaire.nom}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # Titre
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width/2, height-50, "RAPPORT MENSUEL NIVAL IMPACT")

    # Infos principales
    y = height - 100
    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Propriétaire : {proprietaire.nom}")
    y -= 20
    p.drawString(50, y, f"Montant total loyers : {total_loyers} FCFA")
    y -= 20
    p.drawString(50, y, f"Montant total payé : {total_paye} FCFA")
    y -= 20
    p.drawString(50, y, f"Commission agence (10%) : {commission} FCFA")

    # Tableau des locataires
    y -= 40
    row_height = 20
    col_x = [2 * cm, 9 * cm, 14 * cm]
    col_widths = [7 * cm, 5 * cm, 5 * cm]

    # Entêtes
    p.setFont("Helvetica-Bold", 12)
    headers = ["Locataire", "Loyer", "Statut"]
    for i, header in enumerate(headers):
        p.rect(col_x[i], y, col_widths[i], row_height, stroke=1, fill=0)
        p.drawCentredString(col_x[i] + col_widths[i]/2, y + 5, header)

    y -= row_height
    p.setFont("Helvetica", 11)

    # Lignes du tableau
    for locataire in locataires:
        paiement_existe = paiements.filter(locataire=locataire).exists()
        statut = "Payé" if paiement_existe else "Non payé"

        p.rect(col_x[0], y, col_widths[0], row_height, stroke=1, fill=0)
        p.rect(col_x[1], y, col_widths[1], row_height, stroke=1, fill=0)
        p.rect(col_x[2], y, col_widths[2], row_height, stroke=1, fill=0)

        p.drawString(col_x[0] + 5, y + 5, locataire.nom)
        p.drawString(col_x[1] + 5, y + 5, f"{locataire.loyer_mensuel} FCFA")
        p.drawString(col_x[2] + 5, y + 5, statut)
        y -= row_height

    # Signatures
    y -= 40
    p.setFont("Helvetica", 12)
    p.drawString(2 * cm, y, "Signature du gestionnaire")
    p.drawString(width - 7 * cm, y, "Signature du propriétaire")

    # Mois du rapport en bas
    y -= 40
    if mois_rapport:
        p.setFont("Helvetica-Bold", 12)
        p.drawCentredString(width/2, y, f"Mois du rapport : {mois_rapport}")

    p.showPage()
    p.save()
    return response


def get_locataires(request, proprietaire_id):
    locataires = Locataire.objects.filter(proprietaire_id=proprietaire_id)
    data = [{"id": l.id, "nom": l.nom} for l in locataires]
    return JsonResponse({"locataires": data})





