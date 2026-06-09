from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Count, Q
from decimal import Decimal
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from .models import (Commune, Arrondissement, Quartier, Zone,
                     Terrain, Parcelle, Acheteur, Vente, Tranche, AdminCompte)
from .forms import (CommuneForm, ArrondissementForm, QuartierForm, ZoneForm,
                    TerrainForm, ParcelleManuelleForm, GenerationParcellesForm,
                    AcheteurForm, VenteForm, TrancheForm)
from functools import wraps


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.session.get('admin_connecte'):
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def login_view(request):
    error = None
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        try:
            compte = AdminCompte.objects.get(username=username)
            if compte.check_password(password):
                request.session['admin_connecte'] = True
                request.session['admin_username']  = compte.username
                return redirect('dashboard')
            else:
                error = "Mot de passe incorrect."
        except AdminCompte.DoesNotExist:
            error = "Identifiant introuvable."
    return render(request, 'core/login.html', {'error': error})


def logout_view(request):
    request.session.flush()
    return redirect('login')


# ── Dashboard ──
@admin_required
def dashboard(request):
    # Stats globales
    total_parcelles  = Parcelle.objects.count()
    disponibles      = Parcelle.objects.filter(statut='disponible')
    reservees        = Parcelle.objects.filter(statut='reservee').count()
    vendues          = Parcelle.objects.filter(statut='vendue').count()
    total_encaisse   = Tranche.objects.aggregate(s=Sum('montant'))['s'] or Decimal('0')
    total_restant    = sum(v.solde_restant for v in Vente.objects.all())

    sup_dispo_m2 = sum(p.superficie_m2 for p in disponibles)
    sup_dispo_ha = sup_dispo_m2 / Decimal('10000')

    # Stats par commune
    stats_communes = []
    for commune in Commune.objects.all():
        parcelles_commune = Parcelle.objects.filter(
            terrain__zone__quartier__arrondissement__commune=commune
        )
        nb_total    = parcelles_commune.count()
        nb_dispo    = parcelles_commune.filter(statut='disponible').count()
        nb_vendues  = parcelles_commune.filter(statut='vendue').count()
        sup_total   = sum(p.superficie_m2 for p in parcelles_commune)
        sup_restante = sum(p.superficie_m2 for p in parcelles_commune.filter(statut='disponible'))
        stats_communes.append({
            'nom':          commune.nom,
            'nb_total':     nb_total,
            'nb_dispo':     nb_dispo,
            'nb_vendues':   nb_vendues,
            'sup_total_ha': sup_total / Decimal('10000'),
            'sup_reste_ha': sup_restante / Decimal('10000'),
        })

    ventes_recentes = Vente.objects.select_related('parcelle', 'acheteur').order_by('-date_vente')[:5]

    context = {
        'total_parcelles': total_parcelles,
        'nb_disponibles':  disponibles.count(),
        'nb_reservees':    reservees,
        'nb_vendues':      vendues,
        'total_encaisse':  total_encaisse,
        'total_restant':   total_restant,
        'sup_dispo_m2':    sup_dispo_m2,
        'sup_dispo_ha':    sup_dispo_ha,
        'stats_communes':  stats_communes,
        'ventes_recentes': ventes_recentes,
    }
    return render(request, 'core/dashboard.html', context)


# ── API AJAX pour cascades géographiques ──
def get_arrondissements(request, commune_id):
    data = list(Arrondissement.objects.filter(commune_id=commune_id).values('id', 'nom'))
    return JsonResponse({'arrondissements': data})

def get_quartiers(request, arrondissement_id):
    data = list(Quartier.objects.filter(arrondissement_id=arrondissement_id).values('id', 'nom'))
    return JsonResponse({'quartiers': data})

def get_zones(request, quartier_id):
    data = list(Zone.objects.filter(quartier_id=quartier_id).values('id', 'nom'))
    return JsonResponse({'zones': data})

def get_terrains(request, zone_id):
    data = list(Terrain.objects.filter(zone_id=zone_id).values('id', 'reference', 'superficie_ha'))
    return JsonResponse({'terrains': data})


# ── Géographie ──
@admin_required
def geographie(request):
    """Page unique pour gérer les 4 niveaux géographiques"""
    commune_form        = CommuneForm(prefix='commune')
    arrondissement_form = ArrondissementForm(prefix='arr')
    quartier_form       = QuartierForm(prefix='qrt')
    zone_form           = ZoneForm(prefix='zone')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'commune':
            commune_form = CommuneForm(request.POST, prefix='commune')
            if commune_form.is_valid():
                commune_form.save()
                return redirect('geographie')
        elif action == 'arrondissement':
            arrondissement_form = ArrondissementForm(request.POST, prefix='arr')
            if arrondissement_form.is_valid():
                arrondissement_form.save()
                return redirect('geographie')
        elif action == 'quartier':
            quartier_form = QuartierForm(request.POST, prefix='qrt')
            if quartier_form.is_valid():
                quartier_form.save()
                return redirect('geographie')
        elif action == 'zone':
            zone_form = ZoneForm(request.POST, prefix='zone')
            if zone_form.is_valid():
                zone_form.save()
                return redirect('geographie')

    context = {
        'communes':           Commune.objects.prefetch_related('arrondissements__quartiers__zones').all(),
        'commune_form':       commune_form,
        'arrondissement_form': arrondissement_form,
        'quartier_form':      quartier_form,
        'zone_form':          zone_form,
    }
    return render(request, 'core/geographie.html', context)


@admin_required
def supprimer_commune(request, pk):
    get_object_or_404(Commune, pk=pk).delete()
    return redirect('geographie')

@admin_required
def supprimer_arrondissement(request, pk):
    get_object_or_404(Arrondissement, pk=pk).delete()
    return redirect('geographie')

@admin_required
def supprimer_quartier(request, pk):
    get_object_or_404(Quartier, pk=pk).delete()
    return redirect('geographie')

@admin_required
def supprimer_zone(request, pk):
    get_object_or_404(Zone, pk=pk).delete()
    return redirect('geographie')


# ── Terrains ──
@admin_required
def terrains(request):
    qs = Terrain.objects.select_related('zone__quartier__arrondissement__commune')

    # Filtres
    commune_id        = request.GET.get('commune')
    arrondissement_id = request.GET.get('arrondissement')
    quartier_id       = request.GET.get('quartier')
    zone_id           = request.GET.get('zone')

    if commune_id:
        qs = qs.filter(zone__quartier__arrondissement__commune_id=commune_id)
    if arrondissement_id:
        qs = qs.filter(zone__quartier__arrondissement_id=arrondissement_id)
    if quartier_id:
        qs = qs.filter(zone__quartier_id=quartier_id)
    if zone_id:
        qs = qs.filter(zone_id=zone_id)

    form = TerrainForm()
    if request.method == 'POST':
        form = TerrainForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('terrains')

    context = {
        'terrains':    qs,
        'form':        form,
        'communes':    Commune.objects.all(),
        'commune_sel': commune_id,
        'arr_sel':     arrondissement_id,
        'qrt_sel':     quartier_id,
        'zone_sel':    zone_id,
    }
    return render(request, 'core/terrains.html', context)


@admin_required
def fiche_terrain(request, pk):
    terrain  = get_object_or_404(Terrain, pk=pk)
    parcelles = terrain.parcelles.all()
    gen_form  = GenerationParcellesForm(initial={'terrain': terrain})
    return render(request, 'core/fiche_terrain.html', {
        'terrain':   terrain,
        'parcelles': parcelles,
        'gen_form':  gen_form,
    })


@admin_required
def supprimer_terrain(request, pk):
    if request.method == 'POST':
        get_object_or_404(Terrain, pk=pk).delete()
    return redirect('terrains')


# ── Parcelles ──
@admin_required
def parcelles(request):
    qs = Parcelle.objects.select_related('terrain__zone__quartier__arrondissement__commune')

    commune_id        = request.GET.get('commune')
    arrondissement_id = request.GET.get('arrondissement')
    quartier_id       = request.GET.get('quartier')
    zone_id           = request.GET.get('zone')
    statut            = request.GET.get('statut')

    if commune_id:
        qs = qs.filter(terrain__zone__quartier__arrondissement__commune_id=commune_id)
    if arrondissement_id:
        qs = qs.filter(terrain__zone__quartier__arrondissement_id=arrondissement_id)
    if quartier_id:
        qs = qs.filter(terrain__zone__quartier_id=quartier_id)
    if zone_id:
        qs = qs.filter(terrain__zone_id=zone_id)
    if statut:
        qs = qs.filter(statut=statut)

    # Totaux filtrés
    total_sup_m2  = sum(p.superficie_m2 for p in qs)
    dispo_sup_m2  = sum(p.superficie_m2 for p in qs.filter(statut='disponible'))

    form = ParcelleManuelleForm()
    if request.method == 'POST' and request.POST.get('action') == 'manuel':
        form = ParcelleManuelleForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('parcelles')

    context = {
        'parcelles':      qs,
        'form':           form,
        'communes':       Commune.objects.all(),
        'statut':         statut,
        'commune_sel':    commune_id,
        'arr_sel':        arrondissement_id,
        'qrt_sel':        quartier_id,
        'zone_sel':       zone_id,
        'total_sup_m2':   total_sup_m2,
        'total_sup_ha':   total_sup_m2 / Decimal('10000'),
        'dispo_sup_m2':   dispo_sup_m2,
        'dispo_sup_ha':   dispo_sup_m2 / Decimal('10000'),
        'nb_total':       qs.count(),
        'nb_dispo':       qs.filter(statut='disponible').count(),
        'nb_vendues':     qs.filter(statut='vendue').count(),
    }
    return render(request, 'core/parcelles.html', context)


@admin_required
def generer_parcelles(request):
    """Génération automatique de parcelles depuis un terrain"""
    if request.method == 'POST':
        form = GenerationParcellesForm(request.POST)
        if form.is_valid():
            terrain           = form.cleaned_data['terrain']
            nb                = form.cleaned_data['nb_parcelles']
            superficie        = form.cleaned_data['superficie_m2']
            prix              = form.cleaned_data['prix_total']
            prefixe           = form.cleaned_data['prefixe_reference']
            existantes        = terrain.parcelles.count()

            parcelles_crees = 0
            for i in range(1, nb + 1):
                num = existantes + i
                ref = f"{prefixe}{str(num).zfill(3)}"
                if not Parcelle.objects.filter(reference=ref).exists():
                    Parcelle.objects.create(
                        reference=ref,
                        terrain=terrain,
                        superficie_m2=superficie,
                        prix_total=prix,
                        statut='disponible',
                    )
                    parcelles_crees += 1

            return redirect('fiche_terrain', pk=terrain.pk)
    return redirect('terrains')


@admin_required
def fiche_parcelle(request, pk):
    parcelle = get_object_or_404(Parcelle, pk=pk)
    vente    = getattr(parcelle, 'vente', None)
    return render(request, 'core/fiche_parcelle.html', {
        'parcelle': parcelle,
        'vente':    vente,
    })


@admin_required
def modifier_parcelle(request, pk):
    parcelle = get_object_or_404(Parcelle, pk=pk)
    form = ParcelleManuelleForm(request.POST or None, request.FILES or None, instance=parcelle)
    if form.is_valid():
        form.save()
        return redirect('parcelles')
    return render(request, 'core/modifier_parcelle.html', {'form': form, 'parcelle': parcelle})


@admin_required
def supprimer_parcelle(request, pk):
    if request.method == 'POST':
        get_object_or_404(Parcelle, pk=pk).delete()
    return redirect('parcelles')


# ── Acheteurs ──
@admin_required
def acheteurs(request):
    form = AcheteurForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('acheteurs')
    return render(request, 'core/acheteurs.html', {
        'acheteurs': Acheteur.objects.all(),
        'form':      form,
    })


@admin_required
def supprimer_acheteur(request, pk):
    if request.method == 'POST':
        get_object_or_404(Acheteur, pk=pk).delete()
    return redirect('acheteurs')


# ── Ventes ──
@admin_required
def ventes(request):
    form = VenteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        vente = form.save()
        vente.parcelle.statut = 'vendue'
        vente.parcelle.save()
        if vente.mode_paiement == 'comptant':
            Tranche.objects.create(
                vente=vente,
                montant=vente.parcelle.prix_total,
                date_paiement=vente.date_vente,
                remarque='Paiement comptant'
            )
        return redirect('ventes')
    return render(request, 'core/ventes.html', {
        'ventes': Vente.objects.select_related('parcelle', 'acheteur').all(),
        'form':   form,
    })


@admin_required
def detail_vente(request, pk):
    vente    = get_object_or_404(Vente, pk=pk)
    form     = TrancheForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        tranche       = form.save(commit=False)
        tranche.vente = vente
        tranche.save()
        return redirect('detail_vente', pk=pk)
    return render(request, 'core/detail_vente.html', {
        'vente':    vente,
        'tranches': vente.tranches.all(),
        'form':     form,
    })


@admin_required
def supprimer_tranche(request, pk):
    tranche  = get_object_or_404(Tranche, pk=pk)
    vente_pk = tranche.vente.pk
    if request.method == 'POST':
        tranche.delete()
    return redirect('detail_vente', pk=vente_pk)


# ── Reçu PDF ──
@admin_required
def recu_pdf(request, vente_pk):
    vente    = get_object_or_404(Vente, pk=vente_pk)
    tranches = list(vente.tranches.all())
    parcelle = vente.parcelle

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recu_{parcelle.reference}.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 50, "RECU DE VENTE — NIVAL IMPACT")

    p.setFont("Helvetica", 11)
    infos = [
        ("Référence parcelle", parcelle.reference),
        ("Terrain",            parcelle.terrain.reference),
        ("Zone",               parcelle.terrain.zone.nom),
        ("Quartier",           parcelle.terrain.zone.quartier.nom),
        ("Arrondissement",     parcelle.terrain.zone.quartier.arrondissement.nom),
        ("Commune",            parcelle.terrain.zone.quartier.arrondissement.commune.nom),
        ("Superficie",         f"{parcelle.superficie_m2} m² ({parcelle.superficie_ha:.4f} ha)"),
        ("Prix total",         f"{parcelle.prix_total:.2f} FCFA"),
        ("Acheteur",           vente.acheteur.nom),
        ("Téléphone",          vente.acheteur.telephone),
        ("Date de vente",      str(vente.date_vente)),
        ("Mode de paiement",   vente.get_mode_paiement_display()),
    ]
    y = height - 90
    for label, val in infos:
        p.setFont("Helvetica", 10)
        p.drawString(50, y, f"{label} :")
        p.setFont("Helvetica-Bold", 10)
        p.drawString(220, y, val)
        y -= 18

    y -= 10
    p.setStrokeColorRGB(0.7, 0.7, 0.7)
    p.line(40, y, width - 40, y)
    y -= 20

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Détail des paiements :")
    y -= 22

    col_x = [50, 230, 390]
    col_w = [180, 160, 120]
    row_h = 20

    p.setFillColorRGB(0.15, 0.15, 0.35)
    for i in range(3):
        p.rect(col_x[i], y, col_w[i], row_h, stroke=0, fill=1)
    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica-Bold", 10)
    for i, h in enumerate(["Date", "Montant (FCFA)", "Remarque"]):
        p.drawCentredString(col_x[i] + col_w[i] / 2, y + 6, h)
    p.setFillColorRGB(0, 0, 0)
    y -= row_h

    p.setFont("Helvetica", 10)
    for idx, t in enumerate(tranches):
        bg = (0.95, 0.95, 1.0) if idx % 2 == 0 else (1, 1, 1)
        p.setFillColorRGB(*bg)
        for i in range(3):
            p.rect(col_x[i], y, col_w[i], row_h, stroke=1, fill=1)
        p.setFillColorRGB(0, 0, 0)
        for i, val in enumerate([str(t.date_paiement), f"{t.montant:.2f}", t.remarque or "—"]):
            p.drawString(col_x[i] + 5, y + 6, val)
        y -= row_h
        if y < 120:
            p.showPage(); y = height - 60

    y -= 15
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, f"Total versé   : {vente.montant_verse:.2f} FCFA")
    y -= 20
    p.setFillColorRGB(0.1, 0.55, 0.1) if vente.est_solde else p.setFillColorRGB(0.75, 0.1, 0.1)
    p.drawString(50, y, f"Solde restant : {vente.solde_restant:.2f} FCFA")
    p.setFillColorRGB(0, 0, 0)

    y -= 55
    p.setFont("Helvetica", 11)
    p.drawString(50, y, "Signature du gestionnaire")
    p.drawString(width - 200, y, "Signature de l'acheteur")

    p.showPage()
    p.save()
    return response