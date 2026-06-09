from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from decimal import Decimal
from .models import Proprietaire, Locataire, Paiement
from .forms import ProprietaireForm, LocataireForm, PaiementForm
from django.db import IntegrityError
from datetime import datetime
from django.contrib import messages
from .models import AdminCompte
from functools import wraps
from dateutil.relativedelta import relativedelta  # pip install python-dateutil

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('admin_connecte'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def login_view(request):
    # ✅ Vider toute session corrompue d'abord
    if request.session.get('admin_connecte'):
        try:
            # Vérifier que le compte existe encore
            AdminCompte.objects.get(id=request.session.get('admin_id'))
            return redirect('accueil')
        except (AdminCompte.DoesNotExist, KeyError):
            # Session corrompue → on la vide
            request.session.flush()

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
    return render(request, 'core/parametres.html', {'compte': compte, 'success': success, 'error': error})


MOIS_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}


# -------------------------
# ACCUEIL
# -------------------------

@admin_required
def accueil(request):
    mois = request.GET.get("mois")
    annee = request.GET.get("annee")

    proprietaires = Proprietaire.objects.filter(is_deleted=False).order_by('nom')
    locataires = Locataire.objects.filter(is_deleted=False).order_by('nom')
    paiements_all = list(Paiement.objects.all())

    # ── Loyers reçus : basé sur date_paiement (mois où l'argent est arrivé) ──
    paiements_recus = paiements_all
    if mois and mois.isdigit():
        paiements_recus = [p for p in paiements_recus if p.date_paiement.month == int(mois)]
    if annee and annee.isdigit():
        paiements_recus = [p for p in paiements_recus if p.date_paiement.year == int(annee)]

    total_recu = sum([p.montant for p in paiements_recus]) or Decimal('0')
    commission = total_recu * Decimal('0.1')

    # ── Non payés : basé sur mois_concerne (mois couvert) ──
    paiements_couvrant = paiements_all
    if mois and mois.isdigit():
        paiements_couvrant = [p for p in paiements_couvrant if p.mois_concerne == int(mois)]
    if annee and annee.isdigit():
        paiements_couvrant = [p for p in paiements_couvrant if p.annee == int(annee)]

    locataires_non_payes = []
    for proprietaire in proprietaires:
        for locataire in proprietaire.locataires.filter(is_deleted=False):
            if not any(p.locataire_id == locataire.id for p in paiements_couvrant):
                locataires_non_payes.append({
                    "proprietaire": proprietaire,
                    "locataire": locataire,
                })

    # ── Notifications arriérés : paiements reçus ce mois qui couvrent un autre mois ──
    notifications_arrieres = []
    for p in paiements_recus:
        if p.locataire is None or p.proprietaire is None:
            continue
        mois_paiement = p.date_paiement.month
        annee_paiement = p.date_paiement.year
        # C'est un arriéré si le mois couvert != mois de paiement ou année différente
        if p.mois_concerne != mois_paiement or p.annee != annee_paiement:
            notifications_arrieres.append({
                "locataire": p.locataire,
                "proprietaire": p.proprietaire,
                "mois_concerne": MOIS_FR.get(p.mois_concerne, ""),
                "annee_concerne": p.annee,
                "mois_paye": MOIS_FR.get(mois_paiement, ""),
                "annee_paye": annee_paiement,
                "montant": p.montant,
                "date_paiement": p.date_paiement,
            })

    loyers_dict = {str(l.id): float(l.loyer_mensuel) for l in locataires}

    # ── Arriérés par locataire pour affichage dans les cartes ──
    # On regroupe tous les paiements arriérés (tous mois confondus) par locataire_id
    arrieres_par_locataire = {}
    for p in paiements_all:
        if p.locataire_id is None:
            continue
        if p.mois_concerne != p.date_paiement.month or p.annee != p.date_paiement.year:
            if p.locataire_id not in arrieres_par_locataire:
                arrieres_par_locataire[p.locataire_id] = []
            arrieres_par_locataire[p.locataire_id].append(p)

    proprietaires_avec_locataires = []
    for prop in proprietaires:
        locs_avec_info = []
        for loc in prop.locataires.filter(is_deleted=False):
            locs_avec_info.append({
                "locataire": loc,
                "arrieres": arrieres_par_locataire.get(loc.id, []),
            })
        proprietaires_avec_locataires.append({
            "proprietaire": prop,
            "locataires": locs_avec_info,
        })

    context = {
        "proprietaires": proprietaires,
        "proprietaires_avec_locataires": proprietaires_avec_locataires,
        "locataires": locataires,
        "locataires_count": locataires.count(),
        "proprietaires_count": proprietaires.count(),
        "total_loyers": sum([l.loyer_mensuel for l in locataires]) or Decimal('0'),
        "total_recu": total_recu,
        "commission": commission,
        "mois": mois,
        "annee": annee,
        "mois_list": range(1, 13),
        "annee_list": [2024, 2025, 2026],
        "locataires_non_payes": locataires_non_payes,
        "non_payes_count": len(locataires_non_payes),
        "notifications_arrieres": notifications_arrieres,
        "proprietaire_form": ProprietaireForm(),
        "locataire_form": LocataireForm(),
        "paiement_form": PaiementForm(),
        "loyers_dict": loyers_dict,
        "MOIS_FR": MOIS_FR,
    }
    return render(request, "core/accueil.html", context)
# -------------------------
# AJOUTER PAIEMENT
# -------------------------
def ajouter_paiement(request):
    if request.method == "POST":
        try:
            proprietaire_id  = request.POST.get("proprietaire")
            locataire_id     = request.POST.get("locataire")
            date_paiement_str = request.POST.get("date_paiement")
            mois_concernes   = request.POST.getlist("mois_concerne")
            montant          = request.POST.get("montant")
            frais_wc         = request.POST.get("frais_wc") or 0
            paye_en_avance   = request.POST.get("paye_en_avance") == "on"

            date_paiement  = datetime.strptime(date_paiement_str, "%Y-%m-%d").date()
            mois_paiement  = date_paiement.month
            annee_paiement = date_paiement.year

            erreurs = []
            succes  = []

            for mois_concerne in mois_concernes:
                mois_int = int(mois_concerne)

                # ── Calcul intelligent de l'année du mois couvert ──
                # Si le mois couvert est INFÉRIEUR au mois de paiement
                # → c'est un arriéré de l'année précédente (ex: payer Jan en Mars)
                # Si le mois couvert est SUPÉRIEUR au mois de paiement
                # → c'est une avance, mais sur la même année EN GÉNÉRAL
                # SAUF si on est en fin d'année (Nov/Déc) et qu'on paie Jan/Fév
                # → dans ce cas c'est l'année suivante

                if mois_int > mois_paiement:
                    # Avance : même année dans la plupart des cas
                    # Exception : mois_paiement >= 10 et mois_int <= 3
                    # (ex: paiement en Nov, couvre Janvier → année suivante)
                    if mois_paiement >= 10 and mois_int <= 3:
                        annee_concerne = annee_paiement + 1
                    else:
                        annee_concerne = annee_paiement
                elif mois_int < mois_paiement:
                    # Arriéré : même année dans la plupart des cas
                    # Exception : mois_paiement <= 3 et mois_int >= 10
                    # (ex: paiement en Janv, couvre Octobre → année précédente)
                    if mois_paiement <= 3 and mois_int >= 10:
                        annee_concerne = annee_paiement - 1
                    else:
                        annee_concerne = annee_paiement
                else:
                    # Même mois → même année
                    annee_concerne = annee_paiement

                try:
                    paiement = Paiement(
                        proprietaire_id=proprietaire_id,
                        locataire_id=locataire_id,
                        date_paiement=date_paiement,
                        mois_concerne=mois_int,
                        annee=annee_concerne,  # ← EXPLICITEMENT défini
                        montant=montant,
                        frais_wc=frais_wc,
                        paye_en_avance=paye_en_avance,
                    )
                    paiement.save()
                    succes.append(mois_concerne)
                except IntegrityError:
                    erreurs.append(mois_concerne)

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                if erreurs:
                    mois_noms = {
                        "1": "Janvier",  "2": "Février",  "3": "Mars",
                        "4": "Avril",    "5": "Mai",      "6": "Juin",
                        "7": "Juillet",  "8": "Août",     "9": "Septembre",
                        "10": "Octobre", "11": "Novembre","12": "Décembre"
                    }
                    noms_erreurs = [mois_noms.get(str(m), m) for m in erreurs]
                    return JsonResponse({
                        "success": len(succes) > 0,
                        "errors": {"__all__": [f"⚠️ Déjà payé pour : {', '.join(noms_erreurs)}"]}
                    }, status=400 if not succes else 200)
                return JsonResponse({"success": True})
            return redirect("accueil")

        except Exception as e:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({
                    "success": False,
                    "errors": {"__all__": [f"Erreur: {str(e)}"]}
                }, status=400)
    else:
        form = PaiementForm()
    return render(request, "core/ajouter_paiement.html", {"form": form})

def rapport_proprietaire(request, proprietaire_id):
    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    proprietaire = get_object_or_404(Proprietaire, id=proprietaire_id)
    locataires   = proprietaire.locataires.all()  # actifs + archivés pour historique
    paiements    = Paiement.objects.filter(
        locataire__proprietaire=proprietaire
    ).select_related("locataire")

    mois  = request.GET.get("mois")
    annee = request.GET.get("annee")
    mois_int  = int(mois)  if mois  and mois.isdigit()  else None
    annee_int = int(annee) if annee and annee.isdigit() else None

    # ── Filtre par DATE DE PAIEMENT ──
    if mois_int:
        paiements = paiements.filter(date_paiement__month=mois_int)
    if annee_int:
        paiements = paiements.filter(date_paiement__year=annee_int)

    paiements_list = list(paiements)
    tous_paiements = list(Paiement.objects.filter(locataire__proprietaire=proprietaire))

    # ── Titre du rapport = mois PRÉCÉDENT du filtre ──
    if mois_int:
        date_filtre  = datetime(annee_int or datetime.now().year, mois_int, 1)
        date_rapport = date_filtre - relativedelta(months=1)
        mois_rapport  = MOIS_FR.get(date_rapport.month, "")
        annee_rapport = date_rapport.year
    else:
        mois_rapport  = ""
        annee_rapport = annee_int or datetime.now().year

    # ── Totaux ──
    total_loyers = sum([l.loyer_mensuel for l in locataires]) or Decimal('0')
    total_paye   = sum([p.montant  for p in paiements_list]) or Decimal('0')
    total_wc     = sum([p.frais_wc for p in paiements_list]) or Decimal('0')
    commission   = total_paye * Decimal("0.1")
    total_recu_proprietaire = total_paye - commission

    # ── Notifications : paiements en AVANCE encaissés ce mois ──
    notifications_avance = []
    for p in paiements_list:
        if p.locataire is None:
            continue
        mois_p, annee_p = p.date_paiement.month, p.date_paiement.year
        if (p.annee > annee_p) or (p.annee == annee_p and p.mois_concerne > mois_p):
            notifications_avance.append({
                "locataire":      p.locataire.nom,
                "mois_couvert":   MOIS_FR.get(p.mois_concerne, ""),
                "annee_couverte": p.annee,
                "mois_paye":      MOIS_FR.get(mois_p, ""),
                "annee_payee":    annee_p,
                "montant":        p.montant,
            })

    # ── Notifications : déjà couverts ce mois via avance antérieure ──
    notifications_deja_paye = []
    if mois_int and annee_int:
        for loc in locataires.filter(is_deleted=False):
            paye_ce_mois = any(p.locataire_id == loc.id for p in paiements_list)
            if not paye_ce_mois:
                avance = next(
                    (p for p in tous_paiements
                     if p.locataire_id == loc.id
                     and p.mois_concerne == mois_int
                     and p.annee == annee_int
                     and (p.date_paiement.month != mois_int or p.date_paiement.year != annee_int)),
                    None
                )
                if avance:
                    notifications_deja_paye.append({
                        "locataire":      loc.nom,
                        "mois_couvert":   MOIS_FR.get(mois_int, ""),
                        "annee_couverte": annee_int,
                        "mois_paye":      MOIS_FR.get(avance.date_paiement.month, ""),
                        "annee_payee":    avance.date_paiement.year,
                        "montant":        avance.montant,
                    })

    # ── Notifications : ARRIÉRÉS encaissés ce mois ──
    notifications_arrieres = []
    for p in paiements_list:
        if p.locataire is None:
            continue
        mois_p, annee_p = p.date_paiement.month, p.date_paiement.year
        if (p.annee < annee_p) or (p.annee == annee_p and p.mois_concerne < mois_p):
            notifications_arrieres.append({
                "locataire":      p.locataire.nom,
                "mois_concerne":  MOIS_FR.get(p.mois_concerne, ""),
                "annee_concerne": p.annee,
                "mois_paye":      MOIS_FR.get(mois_p, ""),
                "annee_payee":    annee_p,
                "montant":        p.montant,
                "date_paiement":  p.date_paiement,
            })

    # ── Données par locataire ──
    locataires_data = []
    for loc in locataires:
        paiements_loc  = [p for p in paiements_list if p.locataire_id == loc.id]
        montant_total  = sum([p.montant  for p in paiements_loc]) or Decimal('0')
        frais_wc_total = sum([p.frais_wc for p in paiements_loc]) or Decimal('0')
        nb             = len(paiements_loc)

        # Mois couverts (pour affichage HTML)
        mois_couverts = [
            f"{MOIS_FR.get(p.mois_concerne, '')} {p.annee}"
            for p in paiements_loc
        ]

        if not paiements_loc:
            avance = next(
                (p for p in tous_paiements
                 if p.locataire_id == loc.id
                 and p.mois_concerne == mois_int
                 and p.annee == annee_int
                 and mois_int and annee_int
                 and (p.date_paiement.month != mois_int or p.date_paiement.year != annee_int)),
                None
            )
            if avance:
                statut = f"Payé en avance ({MOIS_FR.get(avance.date_paiement.month, '')} {avance.date_paiement.year})"
            else:
                statut = "Non payé"
        elif nb > 1:
            statut = f"Payé ({nb} mois)"
        else:
            p0 = paiements_loc[0]
            mois_p0, annee_p0 = p0.date_paiement.month, p0.date_paiement.year
            if (p0.annee > annee_p0) or (p0.annee == annee_p0 and p0.mois_concerne > mois_p0):
                statut = f"Payé en avance → {MOIS_FR.get(p0.mois_concerne, '')} {p0.annee}"
            elif (p0.annee < annee_p0) or (p0.annee == annee_p0 and p0.mois_concerne < mois_p0):
                statut = f"Arriéré ({MOIS_FR.get(p0.mois_concerne, '')} {p0.annee})"
            else:
                statut = "Payé"

        nom_affiche = loc.nom if not loc.is_deleted else f"{loc.nom} (archivé)"

        locataires_data.append({
            "nom":          nom_affiche,
            "loyer":        montant_total,
            "frais_wc":     frais_wc_total,
            "statut":       statut,
            "nb_mois":      nb,
            "mois_couverts": mois_couverts,
            "is_deleted":   loc.is_deleted,
        })

    context = {
        "proprietaire":            proprietaire,
        "total_loyers":            total_loyers,
        "total_paye":              total_paye,
        "total_wc":                total_wc,
        "commission":              commission,
        "total_recu_proprietaire": total_recu_proprietaire,
        "locataires_data":         locataires_data,
        "mois_list":               [(i, MOIS_FR[i]) for i in range(1, 13)],
        "mois_rapport":            mois_rapport,
        "annee_rapport":           annee_rapport,
        "mois":                    mois,
        "annee":                   annee,
        "notifications_avance":    notifications_avance,
        "notifications_deja_paye": notifications_deja_paye,
        "notifications_arrieres":  notifications_arrieres,
    }
    return render(request, "core/rapport_proprietaire.html", context)


# -------------------------
# RAPPORT PROPRIÉTAIRE HTML
# -------------------------
def rapport_proprietaire_pdf(request, proprietaire_id):
    from datetime import datetime
    from dateutil.relativedelta import relativedelta

    mois  = request.GET.get("mois")
    annee = request.GET.get("annee")
    mois_int  = int(mois)  if mois  and mois.isdigit()  else None
    annee_int = int(annee) if annee and annee.isdigit() else None

    proprietaire   = get_object_or_404(Proprietaire, id=proprietaire_id)
    locataires     = proprietaire.locataires.all()
    tous_paiements = list(Paiement.objects.filter(locataire__in=locataires))

    # ── Filtre par DATE DE PAIEMENT ──
    paiements = tous_paiements
    if mois_int:
        paiements = [p for p in paiements if p.date_paiement.month == mois_int]
    if annee_int:
        paiements = [p for p in paiements if p.date_paiement.year  == annee_int]

    # ── Titre = mois PRÉCÉDENT ──
    if mois_int:
        date_filtre  = datetime(annee_int or datetime.now().year, mois_int, 1)
        date_rapport = date_filtre - relativedelta(months=1)
        mois_titre   = MOIS_FR.get(date_rapport.month, "")
        annee_titre  = date_rapport.year
    else:
        mois_titre  = "Non spécifié"
        annee_titre = annee or "Année courante"

    # ── Totaux ──
    total_loyers            = sum([l.loyer_mensuel for l in locataires]) or Decimal('0')
    total_paye              = sum([p.montant  for p in paiements])       or Decimal('0')
    total_wc                = sum([p.frais_wc for p in paiements])       or Decimal('0')
    commission              = total_paye * Decimal("0.1")
    total_recu_proprietaire = total_paye - commission

    # ── Données par locataire — statut simplifié, SANS mention arriéré/avance ──
    locataires_data = []
    for loc in locataires:
        paiements_loc = [p for p in paiements if p.locataire_id == loc.id]
        montant_total = sum([p.montant  for p in paiements_loc]) or Decimal('0')
        wc_total      = sum([p.frais_wc for p in paiements_loc]) or Decimal('0')
        nb            = len(paiements_loc)

        if nb == 0:
            # Vérifier si couvert par une avance antérieure
            avance = next(
                (p for p in tous_paiements
                 if p.locataire_id == loc.id
                 and p.mois_concerne == mois_int
                 and p.annee == annee_int
                 and mois_int and annee_int
                 and (p.date_paiement.month != mois_int or p.date_paiement.year != annee_int)),
                None
            )
            statut = "Payé" if avance else "Non payé"
        elif nb == 1:
            statut = "Payé"
        else:
            statut = f"Payé {nb} mois"

        locataires_data.append({
            "nom":     loc.nom if not loc.is_deleted else f"{loc.nom} (archivé)",
            "montant": montant_total,
            "wc":      wc_total,
            "nb":      nb,
            "statut":  statut,
        })

    # ════════════════════════════════════════
    #  GÉNÉRATION PDF
    # ════════════════════════════════════════
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="rapport_{proprietaire.nom}_{mois_titre}_{annee_titre}.pdf"'
    )

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    # ── En-tête ──
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 50, "RAPPORT MENSUEL NIVAL IMPACT")

    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(width / 2, height - 75, f"Rapport de : {mois_titre} {annee_titre}")

    p.setFont("Helvetica", 10)
    mois_filtre_nom = MOIS_FR.get(mois_int, "") if mois_int else ""
    if mois_filtre_nom:
        p.drawCentredString(
            width / 2, height - 93,
            f"(paiements encaissés en {mois_filtre_nom} {annee_int or ''})"
        )

    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, height - 118, f"Propriétaire : {proprietaire.nom}")

    # ── Récapitulatif financier ──
    recap_y = height - 150
    line_h  = 28

    def draw_recap_line(label, valeur, y):
        p.setFont("Helvetica", 12)
        p.drawString(50, y, label)
        p.setFont("Helvetica-Bold", 12)
        p.drawRightString(width - 50, y, valeur)

    draw_recap_line("Montant total des loyers :",    f"{total_loyers:.2f} FCFA",            recap_y); recap_y -= line_h
    draw_recap_line("Montant total perçu :",          f"{total_paye:.2f} FCFA",              recap_y); recap_y -= line_h
    draw_recap_line("Commission agence (10%) :",      f"{commission:.2f} FCFA",              recap_y); recap_y -= line_h

    # Ligne verte : montant propriétaire
    p.setFillColorRGB(0.85, 0.95, 0.85)
    p.rect(40, recap_y - 5, width - 80, line_h - 2, stroke=0, fill=1)
    p.setFillColorRGB(0, 0, 0)
    draw_recap_line("Montant payé au propriétaire :", f"{total_recu_proprietaire:.2f} FCFA", recap_y); recap_y -= line_h

    if total_wc > 0:
        draw_recap_line("Frais de fosse (WC) :", f"{total_wc:.2f} FCFA", recap_y)
        recap_y -= line_h

    # ── Séparateur ──
    recap_y -= 8
    p.setStrokeColorRGB(0.7, 0.7, 0.7)
    p.line(40, recap_y, width - 40, recap_y)
    recap_y -= 20

    # ── Tableau locataires — SANS colonne mois couverts, statut simplifié ──
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, recap_y, "Détail par locataire :")
    recap_y -= 22

    has_wc     = total_wc > 0
    row_height = 22

    if has_wc:
        col_x      = [50,  210, 340, 420]
        col_widths = [160, 130,  80,  85]
        headers    = ["Locataire", "Montant encaissé", "Frais WC", "Statut"]
    else:
        col_x      = [50,  240, 410]
        col_widths = [190, 170, 115]
        headers    = ["Locataire", "Montant encaissé", "Statut"]

    # En-tête tableau
    p.setFillColorRGB(0.15, 0.15, 0.35)
    for i in range(len(headers)):
        p.rect(col_x[i], recap_y, col_widths[i], row_height, stroke=0, fill=1)
    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica-Bold", 10)
    for i, header in enumerate(headers):
        p.drawCentredString(col_x[i] + col_widths[i] / 2, recap_y + 7, header)
    p.setFillColorRGB(0, 0, 0)

    y = recap_y - row_height

    for idx, ld in enumerate(locataires_data):
        if y < 100:
            p.showPage()
            y = height - 60

        bg = (0.95, 0.95, 1.0) if idx % 2 == 0 else (1, 1, 1)

        # Couleur statut : vert = payé, rouge = non payé
        if "Non" in ld["statut"]:
            statut_color = (0.75, 0.1, 0.1)
        else:
            statut_color = (0.1, 0.55, 0.1)

        montant_str = f"{ld['montant']:.2f} FCFA"

        if has_wc:
            vals       = [ld["nom"], montant_str, f"{ld['wc']:.2f} FCFA", ld["statut"]]
            col_statut = 3
        else:
            vals       = [ld["nom"], montant_str, ld["statut"]]
            col_statut = 2

        for i, val in enumerate(vals):
            p.setFillColorRGB(*bg)
            p.rect(col_x[i], y, col_widths[i], row_height, stroke=1, fill=1)
            p.setFillColorRGB(0, 0, 0)

            if i == col_statut:
                p.setFillColorRGB(*statut_color)
                p.setFont("Helvetica-Bold", 10)
                p.drawString(col_x[i] + 5, y + 7, val)
                p.setFillColorRGB(0, 0, 0)
            elif i == 1:
                p.setFont("Helvetica-Bold", 10)
                p.drawString(col_x[i] + 5, y + 7, val)
            else:
                p.setFont("Helvetica", 10)
                p.drawString(col_x[i] + 5, y + 7, val)

        y -= row_height

    # ── Signatures ──
    y -= 40
    if y < 60:
        p.showPage()
        y = height - 60
    p.setFont("Helvetica", 12)
    p.setFillColorRGB(0, 0, 0)
    p.drawString(50, y, "Signature du gestionnaire")
    p.drawString(width - 200, y, "Signature du propriétaire")

    p.showPage()
    p.save()
    return response

# -------------------------
# RAPPORT GLOBAL HTML
# -------------------------
def rapport_global(request):
    mois  = request.GET.get("mois")
    annee = request.GET.get("annee")

    mois_int  = int(mois)  if mois  and mois.isdigit()  else None
    annee_int = int(annee) if annee and annee.isdigit() else None

    proprietaires = Proprietaire.objects.prefetch_related("locataires")
    data = []

    for proprietaire in proprietaires:
        locataires     = proprietaire.locataires.all()
        tous_paiements = list(Paiement.objects.filter(locataire__in=locataires))

        # Paiements encaissés ce mois (filtre date_paiement)
        paiements_list = tous_paiements
        if mois_int:
            paiements_list = [p for p in paiements_list if p.date_paiement.month == mois_int]
        if annee_int:
            paiements_list = [p for p in paiements_list if p.date_paiement.year == annee_int]

        total_loyers = sum([l.loyer_mensuel for l in locataires]) or Decimal('0')
        total_paye   = sum([p.montant  for p in paiements_list]) or Decimal('0')
        total_wc     = sum([p.frais_wc for p in paiements_list]) or Decimal('0')
        commission   = total_paye * Decimal("0.1")
        total_recu   = total_paye - commission + total_wc

        # ── Locataires non payés ce mois ──
        locataires_non_payes = []
        for loc in locataires:
            paye_ce_mois = any(p.locataire_id == loc.id for p in paiements_list)
            if not paye_ce_mois:
                couvert_par_avance = False
                if mois_int and annee_int:
                    couvert_par_avance = any(
                        p.locataire_id == loc.id
                        and p.mois_concerne == mois_int
                        and (p.annee or p.date_paiement.year) == annee_int
                        for p in tous_paiements
                    )
                if not couvert_par_avance:
                    locataires_non_payes.append(loc.nom)

        # ── Arriérés : encaissés ce mois mais couvrant un mois PASSÉ ──
        arrieres = []
        for p in paiements_list:
            if p.locataire is None:
                continue
            mois_p        = p.date_paiement.month
            annee_p       = p.date_paiement.year
            annee_couverte = p.annee or annee_p  # fallback si annee est None
            mois_couvert_passe = (
                (annee_couverte < annee_p) or
                (annee_couverte == annee_p and p.mois_concerne < mois_p)
            )
            if mois_couvert_passe:
                arrieres.append(
                    f"{p.locataire.nom} ({MOIS_FR.get(p.mois_concerne, '?')} {annee_couverte})"
                )

        # ── Avances : encaissées ce mois mais couvrant un mois FUTUR ──
        avances = []
        for p in paiements_list:
            if p.locataire is None:
                continue
            mois_p        = p.date_paiement.month
            annee_p       = p.date_paiement.year
            annee_couverte = p.annee or annee_p  # fallback si annee est None
            mois_couvert_futur = (
                (annee_couverte > annee_p) or
                (annee_couverte == annee_p and p.mois_concerne > mois_p)
            )
            if mois_couvert_futur:
                avances.append(
                    f"{p.locataire.nom} ({MOIS_FR.get(p.mois_concerne, '?')} {annee_couverte})"
                )

        # ── Couverts par avance antérieure ──
        deja_payes_avance = []
        if mois_int and annee_int:
            for loc in locataires:
                paye_ce_mois = any(p.locataire_id == loc.id for p in paiements_list)
                if not paye_ce_mois:
                    avance = next(
                        (p for p in tous_paiements
                         if p.locataire_id == loc.id
                         and p.mois_concerne == mois_int
                         and (p.annee or p.date_paiement.year) == annee_int
                         and (p.date_paiement.month != mois_int or p.date_paiement.year != annee_int)),
                        None
                    )
                    if avance:
                        deja_payes_avance.append(
                            f"{loc.nom} (payé en {MOIS_FR.get(avance.date_paiement.month, '')} {avance.date_paiement.year})"
                        )

        data.append({
            "proprietaire":         proprietaire.nom,
            "total_loyers":         total_loyers,
            "total_paye":           total_paye,
            "total_wc":             total_wc,
            "commission":           commission,
            "total_recu":           total_recu,
            "non_paye":             total_loyers - total_paye,
            "locataires_non_payes": locataires_non_payes,
            "arrieres":             arrieres,
            "avances":              avances,
            "deja_payes_avance":    deja_payes_avance,
        })

    context = {
        "rapport":    data,
        "mois_list":  [(i, MOIS_FR[i]) for i in range(1, 13)],
        "annee_list": [2024, 2025, 2026],
        "mois":       mois,
        "annee":      annee,
    }
    return render(request, "core/rapport_global.html", context)


# -------------------------
# RAPPORT GLOBAL PDF
# -------------------------
def rapport_global_pdf(request):
    mois  = request.GET.get("mois")
    annee = request.GET.get("annee")

    mois_int  = int(mois)  if mois  and mois.isdigit()  else None
    annee_int = int(annee) if annee and annee.isdigit() else None

    proprietaires = Proprietaire.objects.prefetch_related("locataires")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="rapport_global.pdf"'

    p = canvas.Canvas(response, pagesize=landscape(A4))
    width, height = landscape(A4)

    def wrap_text(text, max_chars):
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

    titre = "RAPPORT GLOBAL MENSUEL NIVAL IMPACT"
    if mois_int:
        titre += f" - {MOIS_FR.get(mois_int, '')}"
    if annee:
        titre += f" - {annee}"

    p.setFont("Helvetica-Bold", 11)
    p.drawCentredString(width / 2, height - 28, titre)

    col_x      = [0.3*cm, 3.3*cm, 6.1*cm, 8.9*cm, 11.7*cm, 14.3*cm, 17.0*cm, 19.7*cm, 22.7*cm, 25.7*cm]
    col_widths = [3.0*cm, 2.8*cm, 2.8*cm, 2.8*cm,  2.6*cm,  2.7*cm,  2.7*cm,  3.0*cm,  3.0*cm,  3.0*cm]
    max_chars  = [10,     9,      9,      9,        8,       8,       8,       10,      10,      10]

    LINE_H   = 10
    PADDING  = 4
    header_h = 18
    header_y = height - 52

    headers = [
        "Proprietaire", "Total loyers", "Total paye", "Frais WC",
        "Non paye", "Commission", "Total recu",
        "Non payes", "Arrieres", "Avances/Couverts"
    ]

    def draw_headers(y_pos):
        p.setFont("Helvetica-Bold", 6)
        for i, header in enumerate(headers):
            p.setFillColorRGB(0.15, 0.15, 0.35)
            p.rect(col_x[i], y_pos, col_widths[i], header_h, stroke=0, fill=1)
            p.setFillColorRGB(1, 1, 1)
            p.drawCentredString(col_x[i] + col_widths[i] / 2, y_pos + 6, header)
        p.setFillColorRGB(0, 0, 0)
        return y_pos

    draw_headers(header_y)
    y = header_y

    total_loyers_global     = Decimal('0')
    total_paye_global       = Decimal('0')
    total_wc_global         = Decimal('0')
    total_non_paye_global   = Decimal('0')
    total_commission_global = Decimal('0')
    total_recu_global       = Decimal('0')

    def draw_headers_new_page():
        p.showPage()
        p.setFont("Helvetica-Bold", 11)
        p.drawCentredString(width / 2, height - 28, titre + " (suite)")
        hy = height - 52
        draw_headers(hy)
        return hy

    for idx, proprietaire in enumerate(proprietaires):
        locataires     = proprietaire.locataires.all()
        tous_paiements = list(Paiement.objects.filter(locataire__in=locataires))

        paiements = tous_paiements
        if mois_int:
            paiements = [pm for pm in paiements if pm.date_paiement.month == mois_int]
        if annee_int:
            paiements = [pm for pm in paiements if pm.date_paiement.year == annee_int]

        total_loyers = sum([l.loyer_mensuel for l in locataires]) or Decimal('0')
        total_paye   = sum([pm.montant  for pm in paiements])     or Decimal('0')
        total_wc     = sum([pm.frais_wc for pm in paiements])     or Decimal('0')
        non_paye     = total_loyers - total_paye
        commission   = total_paye * Decimal("0.1")
        total_recu   = total_paye - commission + total_wc

        total_loyers_global     += total_loyers
        total_paye_global       += total_paye
        total_wc_global         += total_wc
        total_non_paye_global   += non_paye
        total_commission_global += commission
        total_recu_global       += total_recu

        # Non payés
        locataires_non_payes = []
        for loc in locataires:
            paye = any(pm.locataire_id == loc.id for pm in paiements)
            if not paye:
                couvert = mois_int and annee_int and any(
                    pm.locataire_id == loc.id
                    and pm.mois_concerne == mois_int
                    and (pm.annee or pm.date_paiement.year) == annee_int
                    for pm in tous_paiements
                )
                if not couvert:
                    locataires_non_payes.append(loc.nom)

        # Arriérés
        arrieres = []
        for pm in paiements:
            if pm.locataire is None:
                continue
            mois_p         = pm.date_paiement.month
            annee_p        = pm.date_paiement.year
            annee_couverte = pm.annee or annee_p  # fallback
            if (annee_couverte < annee_p) or (annee_couverte == annee_p and pm.mois_concerne < mois_p):
                arrieres.append(
                    f"{pm.locataire.nom} ({MOIS_FR.get(pm.mois_concerne,'?')[:3]} {annee_couverte})"
                )

        # Avances + couverts
        avances_et_couverts = []
        for pm in paiements:
            if pm.locataire is None:
                continue
            mois_p         = pm.date_paiement.month
            annee_p        = pm.date_paiement.year
            annee_couverte = pm.annee or annee_p  # fallback
            if (annee_couverte > annee_p) or (annee_couverte == annee_p and pm.mois_concerne > mois_p):
                avances_et_couverts.append(
                    f"+{pm.locataire.nom} ({MOIS_FR.get(pm.mois_concerne,'?')[:3]} {annee_couverte})"
                )

        if mois_int and annee_int:
            for loc in locataires:
                paye_ce_mois = any(pm.locataire_id == loc.id for pm in paiements)
                if not paye_ce_mois:
                    avance = next(
                        (pm for pm in tous_paiements
                         if pm.locataire_id == loc.id
                         and pm.mois_concerne == mois_int
                         and (pm.annee or pm.date_paiement.year) == annee_int
                         and (pm.date_paiement.month != mois_int or pm.date_paiement.year != annee_int)),
                        None
                    )
                    if avance:
                        avances_et_couverts.append(
                            f"✓{loc.nom} ({MOIS_FR.get(avance.date_paiement.month,'')[:3]} {avance.date_paiement.year})"
                        )

        values_raw = [
            proprietaire.nom,
            f"{total_loyers:.0f} F",
            f"{total_paye:.0f} F",
            f"{total_wc:.0f} F",
            f"{non_paye:.0f} F",
            f"{commission:.0f} F",
            f"{total_recu:.0f} F",
        ]
        wrapped_values = [wrap_text(v, max_chars[i]) for i, v in enumerate(values_raw)]

        non_payes_flat = (
            [line for nom in locataires_non_payes for line in wrap_text(nom, max_chars[7])]
            if locataires_non_payes else ["Tous payes"]
        )
        arrieres_flat = (
            [line for a in arrieres for line in wrap_text(a, max_chars[8])]
            if arrieres else ["-"]
        )
        avances_flat = (
            [line for a in avances_et_couverts for line in wrap_text(a, max_chars[9])]
            if avances_et_couverts else ["-"]
        )

        max_lines = max(
            max(len(w) for w in wrapped_values),
            len(non_payes_flat),
            len(arrieres_flat),
            len(avances_flat),
        )
        cell_h = max_lines * LINE_H + PADDING * 2

        if y - cell_h < 50:
            y = draw_headers_new_page()

        cell_top = y - cell_h
        bg = (0.95, 0.95, 1.0) if idx % 2 == 0 else (1, 1, 1)

        p.setFont("Helvetica", 7)
        for i, lines in enumerate(wrapped_values):
            p.setFillColorRGB(*bg)
            p.rect(col_x[i], cell_top, col_widths[i], cell_h, stroke=1, fill=1)
            p.setFillColorRGB(0, 0, 0)
            text_y = y - PADDING - LINE_H
            for line in lines:
                p.drawString(col_x[i] + 3, text_y, line)
                text_y -= LINE_H

        # Colonne Non payés
        p.setFillColorRGB(*bg)
        p.rect(col_x[7], cell_top, col_widths[7], cell_h, stroke=1, fill=1)
        p.setFont("Helvetica", 6)
        text_y = y - PADDING - LINE_H
        for line in non_payes_flat:
            p.setFillColorRGB(0.6, 0.0, 0.0) if locataires_non_payes else p.setFillColorRGB(0.0, 0.4, 0.0)
            p.drawString(col_x[7] + 3, text_y, line)
            text_y -= LINE_H

        # Colonne Arriérés
        p.setFillColorRGB(*bg)
        p.rect(col_x[8], cell_top, col_widths[8], cell_h, stroke=1, fill=1)
        p.setFont("Helvetica", 6)
        text_y = y - PADDING - LINE_H
        for line in arrieres_flat:
            p.setFillColorRGB(0.7, 0.4, 0.0) if arrieres else p.setFillColorRGB(0.4, 0.4, 0.4)
            p.drawString(col_x[8] + 3, text_y, line)
            text_y -= LINE_H

        # Colonne Avances/Couverts
        p.setFillColorRGB(*bg)
        p.rect(col_x[9], cell_top, col_widths[9], cell_h, stroke=1, fill=1)
        p.setFont("Helvetica", 6)
        text_y = y - PADDING - LINE_H
        for line in avances_flat:
            p.setFillColorRGB(0.0, 0.35, 0.65) if avances_et_couverts else p.setFillColorRGB(0.4, 0.4, 0.4)
            p.drawString(col_x[9] + 3, text_y, line)
            text_y -= LINE_H

        p.setFillColorRGB(0, 0, 0)
        y = cell_top

    # Ligne TOTAL
    if y - 20 < 50:
        y = draw_headers_new_page()

    totals = [
        "TOTAL GLOBAL",
        f"{total_loyers_global:.0f} F",
        f"{total_paye_global:.0f} F",
        f"{total_wc_global:.0f} F",
        f"{total_non_paye_global:.0f} F",
        f"{total_commission_global:.0f} F",
        f"{total_recu_global:.0f} F",
        "", "", "",
    ]
    total_h = 16
    p.setFont("Helvetica-Bold", 7)
    for i, val in enumerate(totals):
        p.setFillColorRGB(0.75, 0.93, 0.75)
        p.rect(col_x[i], y - total_h, col_widths[i], total_h, stroke=1, fill=1)
        p.setFillColorRGB(0, 0, 0)
        p.drawCentredString(col_x[i] + col_widths[i] / 2, y - total_h + 5, val)

    y -= total_h + 35
    if y < 30:
        p.showPage()
        y = height - 60
    p.setFont("Helvetica", 10)
    p.drawString(2 * cm, y, "Signature du gestionnaire")
    p.drawString(width - 7 * cm, y, "Signature du PDG NIVAL IMPACT")

    p.showPage()
    p.save()
    return response


# -------------------------
# DASHBOARD
# -------------------------
def dashboard(request):
    mois = request.GET.get("mois")
    proprietaire_id = request.GET.get("proprietaire")

    if proprietaire_id:
        proprietaire = Proprietaire.objects.get(id=proprietaire_id)
        locataires_qs = proprietaire.locataires.filter(is_deleted=False)
        paiements = Paiement.objects.filter(locataire__proprietaire=proprietaire)
    else:
        proprietaire = None
        locataires_qs = Locataire.objects.filter(is_deleted=False)
        paiements = Paiement.objects.all()

    if mois and mois.isdigit():
        paiements = paiements.filter(mois_concerne=int(mois))

    paiements_list = list(paiements)
    total_loyers_locataires = sum([l.loyer_mensuel for l in locataires_qs]) or Decimal('0')
    total_recu = sum([p.montant for p in paiements_list]) or Decimal('0')
    total_wc = sum([p.frais_wc for p in paiements_list]) or Decimal('0')
    loyer_restant = total_loyers_locataires - total_recu
    commission_totale = total_recu * Decimal('0.1')
    locataires_payes = len(set(p.locataire_id for p in paiements_list))
    locataires_impayes = locataires_qs.count() - locataires_payes

    locataires_data = []
    for locataire in locataires_qs:
        paiement = next((p for p in paiements_list if p.locataire_id == locataire.id), None)
        locataires_data.append({
            "nom": locataire.nom,
            "montant": paiement.montant if paiement else Decimal('0.00'),
            "frais_wc": paiement.frais_wc if paiement else Decimal('0.00'),
            "statut": "Payé" if paiement else "Impayé"
        })

    context = {
        "proprietaires_count": Proprietaire.objects.count(),
        "locataires_count": locataires_qs.count(),
        "total_loyers_locataires": total_loyers_locataires,
        "total_recu": total_recu,
        "total_wc": total_wc,
        "loyer_restant": loyer_restant,
        "commission_totale": commission_totale,
        "locataires_payes": locataires_payes,
        "locataires_impayes": locataires_impayes,
        "mois": mois,
        "proprietaire": proprietaire,
        "proprietaires": Proprietaire.objects.filter(is_deleted=False),
        "locataires_data": locataires_data,
    }
    return render(request, "core/dashboard.html", context)


# -------------------------
# DASHBOARD PDF
# -------------------------
def dashboard_pdf(request):
    mois = request.GET.get("mois")
    proprietaire_id = request.GET.get("proprietaire")

    if proprietaire_id:
        proprietaire = Proprietaire.objects.get(id=proprietaire_id)
        locataires_qs = proprietaire.locataires.filter(is_deleted=False)
        paiements = list(Paiement.objects.filter(locataire__proprietaire=proprietaire))
    else:
        proprietaire = None
        locataires_qs = Locataire.objects.filter(is_deleted=False)
        paiements = list(Paiement.objects.all())

    if mois and mois.isdigit():
        paiements = [p for p in paiements if p.mois_concerne == int(mois)]

    total_loyers_locataires = sum([l.loyer_mensuel for l in locataires_qs]) or Decimal('0')
    total_recu = sum([p.montant for p in paiements]) or Decimal('0')
    total_wc = sum([p.frais_wc for p in paiements]) or Decimal('0')
    loyer_restant = total_loyers_locataires - total_recu
    commission_totale = total_recu * Decimal('0.1')
    locataires_payes = len(set(p.locataire_id for p in paiements))
    locataires_impayes = locataires_qs.count() - locataires_payes
    mois_facture = MOIS_FR.get(int(mois), "") if mois and mois.isdigit() else ""

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="dashboard.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, height - 50, "RAPPORT GLOBAL LOCATIF")
    if mois_facture:
        p.setFont("Helvetica", 12)
        p.drawCentredString(width / 2, height - 70, f"Mois : {mois_facture}")

    y = height - 110
    p.setFont("Helvetica", 12)
    for ligne in [
        f"Nombre de propriétaires : {Proprietaire.objects.count()}",
        f"Nombre de locataires : {locataires_qs.count()}",
        f"Montant total loyers : {total_loyers_locataires}",
        f"Total loyers reçus : {total_recu}",
        f"Frais WC : {total_wc}",
        f"Loyer restant (impayés) : {loyer_restant}",
        f"Commission totale : {commission_totale}",
    ]:
        p.drawString(50, y, ligne); y -= 20
    y -= 20
    for ligne in [
        f"Locataires payés : {locataires_payes}",
        f"Locataires impayés : {locataires_impayes}",
    ]:
        p.drawString(50, y, ligne); y -= 20

    y -= 40
    p.drawString(50, y, "Signature du gestionnaire")
    p.drawString(width - 200, y, "Signature du propriétaire")

    p.showPage()
    p.save()
    return response


# -------------------------
# FACTURE PDF PAR PROPRIÉTAIRE
# -------------------------
def facture_proprietaire(request, proprietaire_id):
    proprietaire = Proprietaire.objects.get(id=proprietaire_id)
    paiements = list(Paiement.objects.filter(locataire__proprietaire=proprietaire))

    total_loyers_locataires = sum([l.loyer_mensuel for l in proprietaire.locataires.all()]) or Decimal('0')
    total_recu = sum([p.montant for p in paiements]) or Decimal('0')
    total_wc = sum([p.frais_wc for p in paiements]) or Decimal('0')
    loyer_restant = total_loyers_locataires - total_recu
    commission = total_recu * Decimal('0.1')

    mois_facture = ""
    if paiements:
        mois_facture = MOIS_FR.get(paiements[0].mois_concerne, "")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="facture_{proprietaire.nom}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, height - 50, "FACTURE MENSUELLE NIVAL IMPACT")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, height - 70, f"Mois de la facture : {mois_facture}")

    info_y = height - 120
    row_height = 20
    col_x = [2 * cm, 10 * cm]
    col_widths = [8 * cm, 8 * cm]

    for label, value in [
        ("Propriétaire", proprietaire.nom),
        ("Montant total loyers", f"{total_loyers_locataires:.2f}"),
        ("Total loyers reçus", f"{total_recu:.2f}"),
        ("Frais WC", f"{total_wc:.2f}"),
        ("Loyer restant (impayés)", f"{loyer_restant:.2f}"),
        ("Commission entreprise", f"{commission:.2f}"),
    ]:
        p.setFont("Helvetica", 11)
        p.rect(col_x[0], info_y, col_widths[0], row_height, stroke=1, fill=0)
        p.rect(col_x[1], info_y, col_widths[1], row_height, stroke=1, fill=0)
        p.drawString(col_x[0] + 5, info_y + 5, label)
        p.drawString(col_x[1] + 5, info_y + 5, value)
        info_y -= row_height

    y_start = info_y - 40
    col_x2 = [2 * cm, 7 * cm, 11 * cm, 15 * cm]
    col_widths2 = [5 * cm, 4 * cm, 4 * cm, 4 * cm]

    p.setFont("Helvetica-Bold", 11)
    for i, header in enumerate(["Locataire", "Loyer payé", "Frais WC", "Statut"]):
        p.rect(col_x2[i], y_start, col_widths2[i], row_height, stroke=1, fill=0)
        p.drawCentredString(col_x2[i] + col_widths2[i] / 2, y_start + 5, header)

    y = y_start - row_height
    p.setFont("Helvetica", 10)
    for locataire in proprietaire.locataires.filter(is_deleted=False):
        paiement = next((p for p in paiements if p.locataire_id == locataire.id), None)
        montant = paiement.montant if paiement else Decimal('0.00')
        wc = paiement.frais_wc if paiement else Decimal('0.00')
        statut = "Payé" if paiement else "Impayé"
        for i, val in enumerate([locataire.nom, f"{montant:.2f}", f"{wc:.2f}", statut]):
            p.rect(col_x2[i], y, col_widths2[i], row_height, stroke=1, fill=0)
            p.drawString(col_x2[i] + 5, y + 5, val)
        y -= row_height

    y -= 40
    p.setFont("Helvetica", 12)
    p.drawString(2 * cm, y, "Signature du gestionnaire")
    p.drawString(width - 7 * cm, y, "Signature du propriétaire")

    p.showPage()
    p.save()
    return response


# -------------------------
# CRUD
# -------------------------
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


def paiement_create(request, proprietaire_id):
    proprietaire = get_object_or_404(Proprietaire, id=proprietaire_id)
    locataires = Locataire.objects.filter(proprietaire=proprietaire, is_deleted=False)
    if request.method == "POST":
        form = PaiementForm(request.POST)
        if form.is_valid():
            paiement = form.save(commit=False)
            paiement.proprietaire = proprietaire
            paiement.save()
            return redirect("paiement_list")
    else:
        form = PaiementForm()
    return render(request, "core/paiement_form.html", {"form": form, "proprietaire": proprietaire, "locataires": locataires})


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


# APRÈS
def supprimer_proprietaire(request, pk):
    proprietaire = get_object_or_404(Proprietaire, pk=pk)
    if request.method == "POST":
        proprietaire.locataires.all().update(is_deleted=True)  # ← AJOUTER cette ligne
        proprietaire.is_deleted = True
        proprietaire.save()
        return redirect("accueil")
    return render(request, "core/supprimer_proprietaire.html", {"proprietaire": proprietaire})



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


def supprimer_locataire(request, pk):
    locataire = get_object_or_404(Locataire, pk=pk)
    if request.method == "POST":
        locataire.is_deleted = True      # ← supprimé : locataire.nom = "[Supprimé]"
        locataire.save()
        return redirect("accueil")
    return render(request, "core/supprimer_locataire.html", {"locataire": locataire})


def get_loyer(request, locataire_id):
    try:
        locataire = Locataire.objects.get(id=locataire_id)
        return JsonResponse({"loyer": float(locataire.loyer_mensuel)})
    except Locataire.DoesNotExist:
        return JsonResponse({"error": "Locataire introuvable"}, status=404)


def get_locataires(request, proprietaire_id):
    locataires = Locataire.objects.filter(proprietaire_id=proprietaire_id, is_deleted=False).order_by('nom')
    return JsonResponse({"locataires": [{"id": l.id, "nom": l.nom} for l in locataires]})


def get_locataires_by_proprietaire_nom(request, proprietaire_nom):
    locataires = Locataire.objects.filter(proprietaire__nom=proprietaire_nom, is_deleted=False)
    return JsonResponse([{"id": l.id, "nom": l.nom} for l in locataires], safe=False)


def liste_paiements(request):
    paiements = Paiement.objects.select_related("locataire", "proprietaire").all().order_by("-date_paiement")
    return render(request, "core/liste_paiements.html", {"paiements": paiements})


def supprimer_paiement(request, pk):
    paiement = get_object_or_404(Paiement, pk=pk)
    if request.method == "POST":
        paiement.delete()
        return redirect("liste_paiements")
    return render(request, "core/supprimer_paiement.html", {"paiement": paiement})

def archives(request):
    proprietaires_supprimes = Proprietaire.objects.filter(is_deleted=True).order_by('nom')
    locataires_supprimes = Locataire.objects.filter(is_deleted=True).order_by('nom')

    archives_data = []
    for proprietaire in proprietaires_supprimes:
        locataires = proprietaire.locataires.filter(is_deleted=True)
        locataires_info = []
        for locataire in locataires:
            paiements = Paiement.objects.filter(locataire=locataire).order_by('annee', 'mois_concerne')
            locataires_info.append({
                "locataire": locataire,
                "paiements": paiements,
            })
        archives_data.append({
            "proprietaire": proprietaire,
            "locataires": locataires_info,
        })

    # Locataires supprimés dont le propriétaire est encore actif
    locataires_seuls = Locataire.objects.filter(
        is_deleted=True,
        proprietaire__is_deleted=False
    ).order_by('nom')
    locataires_seuls_info = []
    for locataire in locataires_seuls:
        paiements = Paiement.objects.filter(locataire=locataire).order_by('annee', 'mois_concerne')
        locataires_seuls_info.append({
            "locataire": locataire,
            "paiements": paiements,
        })

    context = {
        "archives_data": archives_data,
        "locataires_seuls": locataires_seuls_info,
    }
    return render(request, "core/archives.html", context)