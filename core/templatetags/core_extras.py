from django import template

register = template.Library()

MOIS_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}

@register.filter
def mois_nom(value):
    try:
        return MOIS_FR.get(int(value), str(value))
    except (ValueError, TypeError):
        return value

@register.filter
def get_item(dictionary, key):
    try:
        return dictionary.get(key, key)
    except AttributeError:
        return key