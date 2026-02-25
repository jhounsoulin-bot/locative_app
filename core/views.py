from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape   # ✅ ajout du paysage
from reportlab.lib.units import cm
from decimal import Decimal
from .models import Proprietaire, Locataire, Paiement
from .forms import ProprietaireForm, LocataireForm, PaiementForm
from django.views.decorators.cache import cache_page
from django.db import IntegrityError
from datetime import datetime
from django.contrib import messages
from .models import AdminCompte  # adapte selon ton app
from functools import wraps


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('admin_connecte'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper

def login_view(request):
    if request.session.get('admin_connecte'):
        return redirect('accueil')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        try:
            compte = AdminCompte.objects.get(username=username)
            if compte.check_password(password):
                request.session['admin_connecte'] = True
                request.session['admin_username'] = compte.username
                request.session['admin_id'] = compte.id
                return redirect('accueil')
            else:
                messages.error(request, "Mot de passe incorrect.")
        except AdminCompte.DoesNotExist:
            messages.error(request, "Identifiant introuvable.")

    return render(request, 'core/login.html')


def logout_view(request):
    request.session.flush()
    return redirect('login')


def parametres_view(request):
    if not request.session.get('admin_connecte'):
        return redirect('login')

    compte = AdminCompte.objects.get(id=request.session['admin_id'])
    success = False
    error = None

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'changer_username':
            new_username = request.POST.get('new_username', '').strip()
            if not new_username:
                error = "Le nom d'utilisateur ne peut pas être vide."
            elif AdminCompte.objects.filter(username=new_username).exclude(id=compte.id).exists():
                error = "Ce nom d'utilisateur est déjà pris."
            else:
                compte.username = new_username
                compte.save()
                request.session['admin_username'] = new_username
                success = True

        elif action == 'changer_password':
            ancien = request.POST.get('ancien_password', '')
            nouveau = request.POST.get('nouveau_password', '')
            confirmation = request.POST.get('confirmation_password', '')

            if not compte.check_password(ancien):
                error = "Ancien mot de passe incorrect."
            elif len(nouveau) < 6:
                error = "Le nouveau mot de passe doit avoir au moins 6 caractères."
            elif nouveau != confirmation:
                error = "Les mots de passe ne correspondent pas."
            else:
                compte.set_password(nouveau)
                compte.save()
                success = True

    return render(request, 'core/parametres.html', {
        'compte': compte,
        'success': success,
        'error': error,
    })


def dashboard(request):
    return render(request, "core/dashboard.html")


# Liste des mois en français
MOIS_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}


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
         mois_num = paiements.first().mois_concerne
         mois_facture = MOIS_FR.get(mois_num, "")



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

    if mois and mois.isdigit():
         paiements = paiements.filter(mois_concerne=int(mois))


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
    if mois and mois.isdigit():
         paiements = paiements.filter(mois_concerne=int(mois))


    # Calculs principaux
    total_loyers_locataires = sum([l.loyer_mensuel for l in locataires_qs])
    total_recu = sum([p.montant for p in paiements])
    loyer_restant = total_loyers_locataires - total_recu
    commission_totale = total_recu * Decimal('0.1')

    locataires_payes = paiements.values_list("locataire", flat=True).distinct().count()
    locataires_impayes = locataires_qs.count() - locataires_payes

    # Déterminer le mois en français
    mois_facture = ""
    if mois and mois.isdigit():
         mois_facture = MOIS_FR.get(int(mois), "")

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


@admin_required
def accueil(request):
    mois = request.GET.get("mois")

    proprietaires = Proprietaire.objects.all().order_by('nom')  # ✅ Tri alphabétique
    locataires = Locataire.objects.all().order_by('nom')  # ✅ Tri alphabétique
    paiements = Paiement.objects.all()

    if mois and mois.isdigit():
         paiements = paiements.filter(mois_concerne=int(mois))

    total_loyers = sum([l.loyer_mensuel for l in locataires])
    total_recu = sum([p.montant for p in paiements])
    commission = total_recu * Decimal('0.1')

    # Liste des locataires qui n'ont pas payé
    locataires_non_payes = []
    for proprietaire in proprietaires:
        for locataire in proprietaire.locataires.all():
            paiement_existe = paiements.filter(locataire=locataire).exists()
            if not paiement_existe:
                locataires_non_payes.append({
                    "proprietaire": proprietaire,
                    "locataire": locataire,
                })

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
    proprietaire = get_object_or_404(Proprietaire.objects.prefetch_related("locataires"), id=proprietaire_id)
    locataires = proprietaire.locataires.all()
    paiements = Paiement.objects.filter(locataire__proprietaire=proprietaire).select_related("locataire")

    mois = request.GET.get("mois")
    annee = request.GET.get("annee")
    mois_rapport = ""
    
    if mois and mois.isdigit():
        mois_int = int(mois)
        paiements = paiements.filter(mois_concerne=mois_int)
        mois_rapport = MOIS_FR.get(mois_int, "")
    
    if annee and annee.isdigit():
        paiements = paiements.filter(annee=int(annee))

    total_loyers = sum([l.loyer_mensuel for l in locataires]) or 0
    total_paye = sum([p.montant for p in paiements]) or 0
    commission = total_paye * Decimal("0.1")
    
    # ✅ NOUVEAU
    total_recu_proprietaire = total_paye - commission

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
        "total_recu_proprietaire": total_recu_proprietaire,  # ✅ NOUVEAU
        "locataires_data": locataires_data,
        "mois_list": [(i, MOIS_FR[i]) for i in range(1, 13)],
        "mois_rapport": mois_rapport,
        "mois": mois,
        "annee": annee,
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
    if request.method == "POST":
        try:
            proprietaire_id = request.POST.get("proprietaire")
            locataire_id = request.POST.get("locataire")
            date_paiement_str = request.POST.get("date_paiement")
            mois_concerne = request.POST.get("mois_concerne")
            montant = request.POST.get("montant")
            paye_en_avance = request.POST.get("paye_en_avance") == "on"
            
            # ✅ Convertir la date string en objet date
            date_paiement = datetime.strptime(date_paiement_str, "%Y-%m-%d").date()
            
            # ✅ Créer le paiement
            paiement = Paiement(
                proprietaire_id=proprietaire_id,
                locataire_id=locataire_id,
                date_paiement=date_paiement,
                mois_concerne=mois_concerne,
                montant=montant,
                paye_en_avance=paye_en_avance
            )
            paiement.save()
            
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": True, "id": paiement.id})
            return redirect("accueil")
            
        except IntegrityError:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({
                    "success": False, 
                    "errors": {"__all__": ["⚠️ Ce locataire a déjà payé pour ce mois de cette année !"]}
                }, status=400)
        except Exception as e:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({
                    "success": False, 
                    "errors": {"__all__": [f"Erreur: {str(e)}"]}
                }, status=400)
    else:
        form = PaiementForm()

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
    locataires = Locataire.objects.filter(proprietaire_id=proprietaire_id).order_by('nom')  # ✅ Tri alphabétique
    data = [{"id": l.id, "nom": l.nom} for l in locataires]
    return JsonResponse({"locataires": data})

def rapport_global(request):
    mois = request.GET.get("mois")
    proprietaires = Proprietaire.objects.prefetch_related("locataires")
    data = []

    for proprietaire in proprietaires:
        locataires = proprietaire.locataires.all()
        paiements = Paiement.objects.filter(locataire__in=locataires)

        if mois and mois.isdigit():
            paiements = paiements.filter(mois_concerne=int(mois))

        total_loyers = sum([l.loyer_mensuel for l in locataires])
        total_paye = sum([p.montant for p in paiements])
        commission = total_paye * Decimal("0.1")
        
        # ✅ NOUVEAU
        total_recu = total_paye - commission

        locataires_non_payes = [
            l.nom for l in locataires
            if not paiements.filter(locataire=l).exists()
        ]

        data.append({
            "proprietaire": proprietaire.nom,
            "total_loyers": total_loyers,
            "total_paye": total_paye,
            "commission": commission,
            "total_recu": total_recu,  # ✅ NOUVEAU
            "non_paye": total_loyers - total_paye,
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
    annee = request.GET.get("annee")  # ✅ Récupérer l'année
    proprietaire = get_object_or_404(Proprietaire, id=proprietaire_id)
    locataires = proprietaire.locataires.all()
    paiements = Paiement.objects.filter(locataire__in=locataires)

    if mois and mois.isdigit():
        paiements = paiements.filter(mois_concerne=int(mois))
    
    if annee and annee.isdigit():  # ✅ Filtrer par année
        paiements = paiements.filter(annee=int(annee))

    # Totaux
    total_loyers = sum([l.loyer_mensuel for l in locataires])
    total_paye = sum([p.montant for p in paiements])
    commission = total_paye * Decimal("0.1")
    total_recu_proprietaire = total_paye - commission

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_{proprietaire.nom}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # ✅ Titre
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width/2, height-50, "RAPPORT MENSUEL NIVAL IMPACT")

    # ✅ Mois ET Année affichés
    p.setFont("Helvetica", 12)
    mois_texte = "Non spécifié"
    if mois and mois.isdigit():
        try:
            mois_texte = MOIS_FR[int(mois)]
        except (ValueError, KeyError):
            mois_texte = "Invalide"
    
    annee_texte = annee if annee else "Année courante"
    
    p.drawCentredString(width/2, height-70, f"Mois : {mois_texte} | Année : {annee_texte}")  # ✅ NOUVEAU

    # ✅ Infos propriétaire
    p.setFont("Helvetica", 12)
    p.drawString(50, height-100, f"Propriétaire : {proprietaire.nom}")
    p.drawString(50, height-120, f"Montant total loyers : {total_loyers:.2f} FCFA")
    p.drawString(50, height-140, f"Montant total payé : {total_paye:.2f} FCFA")
    p.drawString(50, height-160, f"Commission agence (10%) : {commission:.2f} FCFA")
    p.drawString(50, height-180, f"Montant total reçu par le propriétaire : {total_recu_proprietaire:.2f} FCFA")  # ✅ NOUVEAU

    # ✅ Tableau des locataires
    y = height - 220
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
    annee = request.GET.get("annee")
    proprietaires = Proprietaire.objects.prefetch_related("locataires")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="rapport_global.pdf"'

    p = canvas.Canvas(response, pagesize=landscape(A4))
    width, height = landscape(A4)

    # ── Fonction utilitaire : coupe un texte long en plusieurs lignes ──
    def wrap_text(text, max_chars):
        """Découpe un texte en lignes de max_chars caractères max."""
        words = text.split()
        lines = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 <= max_chars:
                current = (current + " " + word).strip()
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines if lines else [text[:max_chars]]

    # ── Titre ──
    p.setFont("Helvetica-Bold", 13)
    titre = "RAPPORT GLOBAL MENSUEL NIVAL IMPACT"
    if mois and mois.isdigit():
        try:
            titre += f" - {MOIS_FR[int(mois)]}"
        except (ValueError, KeyError):
            pass
    if annee:
        titre += f" - {annee}"
    p.drawCentredString(width / 2, height - 35, titre)

    # ── Définition des colonnes (total = ~28cm sur A4 paysage ~29.7cm) ──
    # Propriétaire plus large, colonnes numériques compactes
    col_x      = [0.5*cm, 5.5*cm, 10*cm,  14*cm,  18*cm,  22*cm,  26*cm]
    col_widths = [5*cm,   4.5*cm,  4*cm,   4*cm,   4*cm,   4*cm,   3.5*cm]
    # max_chars par colonne pour le wrapping
    max_chars  = [16,     12,      12,     12,     12,     12,     14]

    LINE_H = 12     # hauteur d'une ligne de texte
    PADDING = 6     # padding vertical dans la cellule
    header_h = 20
    header_y = height - 65

    # ── En-têtes ──
    headers = ["Propriétaire", "Total loyers", "Total payé", "Non payé", "Commission", "Total reçu", "Non payés"]
    p.setFont("Helvetica-Bold", 8)
    for i, header in enumerate(headers):
        p.setFillColorRGB(0.15, 0.15, 0.35)
        p.rect(col_x[i], header_y, col_widths[i], header_h, stroke=0, fill=1)
        p.setFillColorRGB(1, 1, 1)
        p.drawCentredString(col_x[i] + col_widths[i] / 2, header_y + 6, header)
    p.setFillColorRGB(0, 0, 0)

    y = header_y  # y = bas de la ligne d'en-tête, on descend ensuite

    # ── Totaux globaux ──
    total_loyers_global    = Decimal('0')
    total_paye_global      = Decimal('0')
    total_non_paye_global  = Decimal('0')
    total_commission_global= Decimal('0')
    total_recu_global      = Decimal('0')

    def draw_headers_new_page():
        p.showPage()
        p.setFont("Helvetica-Bold", 13)
        p.drawCentredString(width / 2, height - 35, titre + " (suite)")
        p.setFont("Helvetica-Bold", 8)
        hy = height - 65
        for i, header in enumerate(headers):
            p.setFillColorRGB(0.15, 0.15, 0.35)
            p.rect(col_x[i], hy, col_widths[i], header_h, stroke=0, fill=1)
            p.setFillColorRGB(1, 1, 1)
            p.drawCentredString(col_x[i] + col_widths[i] / 2, hy + 6, header)
        p.setFillColorRGB(0, 0, 0)
        return hy  # retourne le bas des en-têtes

    for idx, proprietaire in enumerate(proprietaires):
        locataires = proprietaire.locataires.all()
        paiements = Paiement.objects.filter(locataire__in=locataires)

        if mois and mois.isdigit():
            paiements = paiements.filter(mois_concerne=int(mois))
        if annee and annee.isdigit():
            paiements = paiements.filter(annee=int(annee))

        total_loyers = sum([l.loyer_mensuel for l in locataires]) or Decimal('0')
        total_paye   = sum([pm.montant for pm in paiements])       or Decimal('0')
        non_paye     = total_loyers - total_paye
        commission   = total_paye * Decimal("0.1")
        total_recu   = total_paye - commission

        total_loyers_global     += total_loyers
        total_paye_global       += total_paye
        total_non_paye_global   += non_paye
        total_commission_global += commission
        total_recu_global       += total_recu

        locataires_non_payes = [l.nom for l in locataires if not paiements.filter(locataire=l).exists()]

        # Calculer les lignes wrappées pour chaque colonne
        values_raw = [
            proprietaire.nom,
            f"{total_loyers:.0f} F",
            f"{total_paye:.0f} F",
            f"{non_paye:.0f} F",
            f"{commission:.0f} F",
            f"{total_recu:.0f} F",
        ]
        wrapped_values = [wrap_text(v, max_chars[i]) for i, v in enumerate(values_raw)]

        # Colonne non payés : une ligne par locataire
        if locataires_non_payes:
            non_payes_lines = [wrap_text(nom, max_chars[6]) for nom in locataires_non_payes]
            non_payes_flat = [line for sublist in non_payes_lines for line in sublist]
        else:
            non_payes_flat = ["Tous ont paye"]

        # Hauteur de la cellule = max lignes de toutes les colonnes
        max_lines = max(
            max(len(w) for w in wrapped_values),
            len(non_payes_flat)
        )
        cell_h = max_lines * LINE_H + PADDING * 2

        # Nouvelle page si nécessaire
        if y - cell_h < 55:
            y = draw_headers_new_page()

        cell_top = y - cell_h

        # Fond alterné
        if idx % 2 == 0:
            p.setFillColorRGB(0.95, 0.95, 1.0)
        else:
            p.setFillColorRGB(1, 1, 1)

        # Dessiner les cellules colonnes 0-5
        p.setFont("Helvetica", 8)
        for i, lines in enumerate(wrapped_values):
            p.rect(col_x[i], cell_top, col_widths[i], cell_h, stroke=1, fill=1)
            p.setFillColorRGB(0, 0, 0)
            text_y = y - PADDING - LINE_H
            for line in lines:
                p.drawString(col_x[i] + 3, text_y, line)
                text_y -= LINE_H
            # Reset fill pour prochain rect
            if idx % 2 == 0:
                p.setFillColorRGB(0.95, 0.95, 1.0)
            else:
                p.setFillColorRGB(1, 1, 1)

        # Colonne non payés
        p.rect(col_x[6], cell_top, col_widths[6], cell_h, stroke=1, fill=1)
        p.setFillColorRGB(0, 0, 0)
        text_y = y - PADDING - LINE_H
        p.setFont("Helvetica", 7)
        for line in non_payes_flat:
            p.drawString(col_x[6] + 3, text_y, line)
            text_y -= LINE_H

        y = cell_top

    # ── Ligne totaux ──
    if y - 20 < 55:
        y = draw_headers_new_page()

    p.setFillColorRGB(0.9, 0.95, 0.9)
    p.setFont("Helvetica-Bold", 8)
    totals = [
        "TOTAL GLOBAL",
        f"{total_loyers_global:.0f} F",
        f"{total_paye_global:.0f} F",
        f"{total_non_paye_global:.0f} F",
        f"{total_commission_global:.0f} F",
        f"{total_recu_global:.0f} F",
        ""
    ]
    total_h = 18
    for i, val in enumerate(totals):
        p.rect(col_x[i], y - total_h, col_widths[i], total_h, stroke=1, fill=1)
        p.setFillColorRGB(0, 0, 0)
        p.drawCentredString(col_x[i] + col_widths[i] / 2, y - total_h + 5, val)

    y -= total_h

    # ── Signatures ──
    y -= 35
    if y < 30:
        p.showPage()
        y = height - 60
    p.setFont("Helvetica", 10)
    p.drawString(2 * cm, y, "Signature du gestionnaire")
    p.drawString(width - 7 * cm, y, "Signature du propriétaire")

    p.showPage()
    p.save()
    return response

def supprimer_paiement(request, pk):
    paiement = get_object_or_404(Paiement, pk=pk)
    if request.method == "POST":
        paiement.delete()
        return redirect("liste_paiements")
    return render(request, "core/supprimer_paiement.html", {"paiement": paiement})




