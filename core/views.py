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

    proprietaires = Proprietaire.objects.all().order_by('nom')
    locataires = Locataire.objects.all().order_by('nom')
    paiements = Paiement.objects.all()

    if mois and mois.isdigit():
        paiements = paiements.filter(mois_concerne=int(mois))
    if annee and annee.isdigit():
        paiements = paiements.filter(annee=int(annee))

    paiements_list = list(paiements)

    total_loyers = sum([l.loyer_mensuel for l in locataires]) or Decimal('0')
    total_recu = sum([p.montant for p in paiements_list]) or Decimal('0')
    commission = total_recu * Decimal('0.1')

    locataires_non_payes = []
    for proprietaire in proprietaires:
        for locataire in proprietaire.locataires.all():
            if not any(p.locataire_id == locataire.id for p in paiements_list):
                locataires_non_payes.append({
                    "proprietaire": proprietaire,
                    "locataire": locataire,
                })

    loyers_dict = {str(l.id): float(l.loyer_mensuel) for l in locataires}

    context = {
        "proprietaires": proprietaires,
        "locataires": locataires,
        "locataires_count": locataires.count(),
        "proprietaires_count": proprietaires.count(),
        "total_loyers": total_loyers,
        "total_recu": total_recu,
        "commission": commission,
        # total_wc intentionnellement absent — pas affiché sur l'accueil
        "mois": mois,
        "annee": annee,
        "mois_list": range(1, 13),
        "annee_list": [2024, 2025, 2026],
        "locataires_non_payes": locataires_non_payes,
        "non_payes_count": len(locataires_non_payes),
        "proprietaire_form": ProprietaireForm(),
        "locataire_form": LocataireForm(),
        "paiement_form": PaiementForm(),
        "loyers_dict": loyers_dict,
    }
    return render(request, "core/accueil.html", context)


# -------------------------
# AJOUTER PAIEMENT
# -------------------------
def ajouter_paiement(request):
    if request.method == "POST":
        try:
            proprietaire_id = request.POST.get("proprietaire")
            locataire_id = request.POST.get("locataire")
            date_paiement_str = request.POST.get("date_paiement")
            mois_concerne = request.POST.get("mois_concerne")
            montant = request.POST.get("montant")
            frais_wc = request.POST.get("frais_wc") or 0
            paye_en_avance = request.POST.get("paye_en_avance") == "on"

            date_paiement = datetime.strptime(date_paiement_str, "%Y-%m-%d").date()

            paiement = Paiement(
                proprietaire_id=proprietaire_id,
                locataire_id=locataire_id,
                date_paiement=date_paiement,
                mois_concerne=mois_concerne,
                montant=montant,
                frais_wc=frais_wc,
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


# -------------------------
# RAPPORT PROPRIÉTAIRE HTML
# -------------------------
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

    paiements_list = list(paiements)

    total_loyers = sum([l.loyer_mensuel for l in locataires]) or Decimal('0')
    total_paye   = sum([p.montant for p in paiements_list]) or Decimal('0')
    total_wc     = sum([p.frais_wc for p in paiements_list]) or Decimal('0')
    commission   = total_paye * Decimal("0.1")
    total_recu_proprietaire = total_paye - commission + total_wc

    locataires_data = []
    for locataire in locataires:
        paiement = next((p for p in paiements_list if p.locataire_id == locataire.id), None)
        locataires_data.append({
            "nom": locataire.nom,
            "loyer": locataire.loyer_mensuel,
            "frais_wc": paiement.frais_wc if paiement else Decimal('0'),
            "statut": "Payé" if paiement else "Non payé",
        })

    context = {
        "proprietaire": proprietaire,
        "total_loyers": total_loyers,
        "total_paye": total_paye,
        "total_wc": total_wc,
        "commission": commission,
        "total_recu_proprietaire": total_recu_proprietaire,
        "locataires_data": locataires_data,
        "mois_list": [(i, MOIS_FR[i]) for i in range(1, 13)],
        "mois_rapport": mois_rapport,
        "mois": mois,
        "annee": annee,
    }
    return render(request, "core/rapport_proprietaire.html", context)


# -------------------------
# RAPPORT PROPRIÉTAIRE PDF
# -------------------------
def rapport_proprietaire_pdf(request, proprietaire_id):
    mois = request.GET.get("mois")
    annee = request.GET.get("annee")
    proprietaire = get_object_or_404(Proprietaire, id=proprietaire_id)
    locataires = proprietaire.locataires.all()
    paiements = list(Paiement.objects.filter(locataire__in=locataires))

    if mois and mois.isdigit():
        paiements = [p for p in paiements if p.mois_concerne == int(mois)]
    if annee and annee.isdigit():
        paiements = [p for p in paiements if p.annee == int(annee)]

    total_loyers = sum([l.loyer_mensuel for l in locataires]) or Decimal('0')
    total_paye   = sum([p.montant for p in paiements]) or Decimal('0')
    total_wc     = sum([p.frais_wc for p in paiements]) or Decimal('0')
    commission   = total_paye * Decimal("0.1")
    total_recu_proprietaire = total_paye - commission + total_wc

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_{proprietaire.nom}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, height - 50, "RAPPORT MENSUEL NIVAL IMPACT")

    p.setFont("Helvetica", 12)
    mois_texte = MOIS_FR.get(int(mois), "Non spécifié") if mois and mois.isdigit() else "Non spécifié"
    annee_texte = annee if annee else "Année courante"
    p.drawCentredString(width / 2, height - 70, f"Mois : {mois_texte} | Année : {annee_texte}")

    p.setFont("Helvetica", 12)
    p.drawString(50, height - 100, f"Propriétaire : {proprietaire.nom}")
    p.drawString(50, height - 120, f"Montant total loyers : {total_loyers:.2f} FCFA")
    p.drawString(50, height - 140, f"Montant total payé : {total_paye:.2f} FCFA")
    p.drawString(50, height - 160, f"Frais WC : {total_wc:.2f} FCFA")
    p.drawString(50, height - 180, f"Commission agence (10%) : {commission:.2f} FCFA")
    p.drawString(50, height - 200, f"Total reçu par le propriétaire : {total_recu_proprietaire:.2f} FCFA")

    y = height - 240
    row_height = 20
    col_x = [50, 200, 320, 420]
    col_widths = [150, 120, 100, 100]

    headers = ["Locataire", "Loyer", "Frais WC", "Statut"]
    p.setFont("Helvetica-Bold", 11)
    for i, header in enumerate(headers):
        p.rect(col_x[i], y, col_widths[i], row_height, stroke=1, fill=0)
        p.drawCentredString(col_x[i] + col_widths[i] / 2, y + 5, header)

    y -= row_height
    p.setFont("Helvetica", 10)
    for locataire in locataires:
        paiement = next((p for p in paiements if p.locataire_id == locataire.id), None)
        wc = paiement.frais_wc if paiement else Decimal('0.00')
        statut = "Payé" if paiement else "Non payé"

        for i, val in enumerate([locataire.nom, f"{locataire.loyer_mensuel:.2f} FCFA", f"{wc:.2f} FCFA", statut]):
            p.rect(col_x[i], y, col_widths[i], row_height, stroke=1, fill=0)
            p.drawString(col_x[i] + 5, y + 5, val)

        y -= row_height
        if y < 100:
            p.showPage()
            y = height - 100

    y -= 40
    p.setFont("Helvetica", 12)
    p.drawString(50, y, "Signature du gestionnaire")
    p.drawString(width - 200, y, "Signature du propriétaire")

    p.showPage()
    p.save()
    return response


# -------------------------
# RAPPORT GLOBAL HTML
# -------------------------
def rapport_global(request):
    mois = request.GET.get("mois")
    annee = request.GET.get("annee")
    proprietaires = Proprietaire.objects.prefetch_related("locataires")
    data = []

    for proprietaire in proprietaires:
        locataires = proprietaire.locataires.all()
        paiements = Paiement.objects.filter(locataire__in=locataires)

        if mois and mois.isdigit():
            paiements = paiements.filter(mois_concerne=int(mois))
        if annee and annee.isdigit():
            paiements = paiements.filter(annee=int(annee))

        paiements_list = list(paiements)
        total_loyers = sum([l.loyer_mensuel for l in locataires]) or Decimal('0')
        total_paye   = sum([p.montant for p in paiements_list]) or Decimal('0')
        total_wc     = sum([p.frais_wc for p in paiements_list]) or Decimal('0')
        commission   = total_paye * Decimal("0.1")
        total_recu   = total_paye - commission + total_wc

        locataires_non_payes = [l.nom for l in locataires if not any(p.locataire_id == l.id for p in paiements_list)]

        data.append({
            "proprietaire": proprietaire.nom,
            "total_loyers": total_loyers,
            "total_paye": total_paye,
            "total_wc": total_wc,
            "commission": commission,
            "total_recu": total_recu,
            "non_paye": total_loyers - total_paye,
            "locataires_non_payes": locataires_non_payes,
        })

    context = {
        "rapport": data,
        "mois_list": [(i, MOIS_FR[i]) for i in range(1, 13)],
        "annee_list": [2024, 2025, 2026],
        "mois": mois,
        "annee": annee,
    }
    return render(request, "core/rapport_global.html", context)


# -------------------------
# RAPPORT GLOBAL PDF
# -------------------------
def rapport_global_pdf(request):
    mois = request.GET.get("mois")
    annee = request.GET.get("annee")
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

    col_x      = [0.5*cm, 4.5*cm, 8*cm,   11.5*cm, 15*cm,  18.5*cm, 22*cm,  25.5*cm]
    col_widths = [4*cm,   3.5*cm,  3.5*cm,  3.5*cm,  3.5*cm,  3.5*cm,  3.5*cm,  4*cm]
    max_chars  = [13,     10,      10,      10,      10,      10,     10,      13]

    LINE_H = 12
    PADDING = 6
    header_h = 20
    header_y = height - 65

    headers = ["Propriétaire", "Total loyers", "Total payé", "Frais WC", "Non payé", "Commission", "Total reçu", "Non payés"]
    p.setFont("Helvetica-Bold", 7)
    for i, header in enumerate(headers):
        p.setFillColorRGB(0.15, 0.15, 0.35)
        p.rect(col_x[i], header_y, col_widths[i], header_h, stroke=0, fill=1)
        p.setFillColorRGB(1, 1, 1)
        p.drawCentredString(col_x[i] + col_widths[i] / 2, header_y + 6, header)
    p.setFillColorRGB(0, 0, 0)

    y = header_y
    total_loyers_global = total_paye_global = total_wc_global = Decimal('0')
    total_non_paye_global = total_commission_global = total_recu_global = Decimal('0')

    def draw_headers_new_page():
        p.showPage()
        p.setFont("Helvetica-Bold", 13)
        p.drawCentredString(width / 2, height - 35, titre + " (suite)")
        p.setFont("Helvetica-Bold", 7)
        hy = height - 65
        for i, header in enumerate(headers):
            p.setFillColorRGB(0.15, 0.15, 0.35)
            p.rect(col_x[i], hy, col_widths[i], header_h, stroke=0, fill=1)
            p.setFillColorRGB(1, 1, 1)
            p.drawCentredString(col_x[i] + col_widths[i] / 2, hy + 6, header)
        p.setFillColorRGB(0, 0, 0)
        return hy

    for idx, proprietaire in enumerate(proprietaires):
        locataires = proprietaire.locataires.all()
        paiements = list(Paiement.objects.filter(locataire__in=locataires))

        if mois and mois.isdigit():
            paiements = [pm for pm in paiements if pm.mois_concerne == int(mois)]
        if annee and annee.isdigit():
            paiements = [pm for pm in paiements if pm.annee == int(annee)]

        total_loyers  = sum([l.loyer_mensuel for l in locataires]) or Decimal('0')
        total_paye    = sum([pm.montant for pm in paiements]) or Decimal('0')
        total_wc      = sum([pm.frais_wc for pm in paiements]) or Decimal('0')
        non_paye      = total_loyers - total_paye
        commission    = total_paye * Decimal("0.1")
        total_recu    = total_paye - commission + total_wc

        total_loyers_global     += total_loyers
        total_paye_global       += total_paye
        total_wc_global         += total_wc
        total_non_paye_global   += non_paye
        total_commission_global += commission
        total_recu_global       += total_recu

        locataires_non_payes = [l.nom for l in locataires if not any(pm.locataire_id == l.id for pm in paiements)]

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
        non_payes_flat = [line for nom in locataires_non_payes for line in wrap_text(nom, max_chars[7])] if locataires_non_payes else ["Tous ont paye"]

        max_lines = max(max(len(w) for w in wrapped_values), len(non_payes_flat))
        cell_h = max_lines * LINE_H + PADDING * 2

        if y - cell_h < 55:
            y = draw_headers_new_page()

        cell_top = y - cell_h
        bg = (0.95, 0.95, 1.0) if idx % 2 == 0 else (1, 1, 1)

        p.setFont("Helvetica", 8)
        for i, lines in enumerate(wrapped_values):
            p.setFillColorRGB(*bg)
            p.rect(col_x[i], cell_top, col_widths[i], cell_h, stroke=1, fill=1)
            p.setFillColorRGB(0, 0, 0)
            text_y = y - PADDING - LINE_H
            for line in lines:
                p.drawString(col_x[i] + 3, text_y, line)
                text_y -= LINE_H

        p.setFillColorRGB(*bg)
        p.rect(col_x[7], cell_top, col_widths[7], cell_h, stroke=1, fill=1)
        p.setFillColorRGB(0, 0, 0)
        text_y = y - PADDING - LINE_H
        p.setFont("Helvetica", 7)
        for line in non_payes_flat:
            p.drawString(col_x[7] + 3, text_y, line)
            text_y -= LINE_H

        y = cell_top

    if y - 20 < 55:
        y = draw_headers_new_page()

    totals = [
        "TOTAL GLOBAL",
        f"{total_loyers_global:.0f} F",
        f"{total_paye_global:.0f} F",
        f"{total_wc_global:.0f} F",
        f"{total_non_paye_global:.0f} F",
        f"{total_commission_global:.0f} F",
        f"{total_recu_global:.0f} F",
        ""
    ]
    total_h = 18
    p.setFont("Helvetica-Bold", 8)
    for i, val in enumerate(totals):
        p.setFillColorRGB(0.8, 0.95, 0.8)
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
        locataires_qs = proprietaire.locataires.all()
        paiements = Paiement.objects.filter(locataire__proprietaire=proprietaire)
    else:
        proprietaire = None
        locataires_qs = Locataire.objects.all()
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
        "proprietaires": Proprietaire.objects.all(),
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
        locataires_qs = proprietaire.locataires.all()
        paiements = list(Paiement.objects.filter(locataire__proprietaire=proprietaire))
    else:
        proprietaire = None
        locataires_qs = Locataire.objects.all()
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
    for locataire in proprietaire.locataires.all():
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


def supprimer_proprietaire(request, pk):
    proprietaire = get_object_or_404(Proprietaire, pk=pk)
    if request.method == "POST":
        proprietaire.delete()
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
        locataire.delete()
        return redirect("accueil")
    return render(request, "core/supprimer_locataire.html", {"locataire": locataire})


def get_loyer(request, locataire_id):
    try:
        locataire = Locataire.objects.get(id=locataire_id)
        return JsonResponse({"loyer": float(locataire.loyer_mensuel)})
    except Locataire.DoesNotExist:
        return JsonResponse({"error": "Locataire introuvable"}, status=404)


def get_locataires(request, proprietaire_id):
    locataires = Locataire.objects.filter(proprietaire_id=proprietaire_id).order_by('nom')
    return JsonResponse({"locataires": [{"id": l.id, "nom": l.nom} for l in locataires]})


def get_locataires_by_proprietaire_nom(request, proprietaire_nom):
    locataires = Locataire.objects.filter(proprietaire__nom=proprietaire_nom)
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