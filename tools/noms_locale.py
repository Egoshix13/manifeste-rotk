"""Les VRAIS noms d'objets, depuis les fichiers de langue du jeu.

LE CHAINON QUI MANQUAIT

`ClientItemDefinitions.txt` donne un `NAME_ID` (petit nombre, ex. 22374),
`Locale/en_us_data.dat` liste des textes indexes par de grands nombres
(ex. 4025209844) -- et rien ne reliait les deux. Plusieurs pistes avaient
ete essayees en vain (voir extraire.py).

La relation, trouvee par force brute sur des paires connues puis verifiee :

    id_langue = Jenkins lookup2("Global.Text.<NAME_ID>", initval 0)

Verifiee sur NAME_ID 32 -> "AR-15", 18056 -> "inboxes AR-15",
22374 -> "Fire Hazard AR-15", et resolvant 99,9 % du catalogue.

Deux sortes de lignes dans le .dat : `ucdt` = le nom affiche,
`ugdt` = la description (leur espace de cles differe, seul `ucdt` suit
la relation ci-dessus).
"""
import os
import re

M = 0xffffffff


def _mix(a, b, c):
    a = (a - b - c) & M; a ^= c >> 13
    b = (b - c - a) & M; b ^= (a << 8) & M
    c = (c - a - b) & M; c ^= b >> 13
    a = (a - b - c) & M; a ^= c >> 12
    b = (b - c - a) & M; b ^= (a << 16) & M
    c = (c - a - b) & M; c ^= b >> 5
    a = (a - b - c) & M; a ^= c >> 3
    b = (b - c - a) & M; b ^= (a << 10) & M
    c = (c - a - b) & M; c ^= b >> 15
    return a, b, c


def lookup2(cle):
    """Jenkins lookup2 (1996), initval 0 -- celui qu'utilise ForgeLight."""
    a = b = 0x9E3779B9
    c = 0
    n, i = len(cle), 0
    while n - i >= 12:
        a = (a + int.from_bytes(cle[i:i + 4], 'little')) & M
        b = (b + int.from_bytes(cle[i + 4:i + 8], 'little')) & M
        c = (c + int.from_bytes(cle[i + 8:i + 12], 'little')) & M
        a, b, c = _mix(a, b, c)
        i += 12
    c = (c + n) & M
    r = cle[i:]
    for j, d in ((11, 24), (10, 16), (9, 8)):
        if len(r) >= j:
            c = (c + (r[j - 1] << d)) & M
    for j, d in ((8, 24), (7, 16), (6, 8), (5, 0)):
        if len(r) >= j:
            b = (b + (r[j - 1] << d)) & M
    for j, d in ((4, 24), (3, 16), (2, 8), (1, 0)):
        if len(r) >= j:
            a = (a + (r[j - 1] << d)) & M
    return _mix(a, b, c)[2]


def id_langue(name_id):
    return lookup2(('Global.Text.%s' % name_id).encode())


def charger(racine_jeu, langue='en_us'):
    """{NAME_ID -> nom affiche}. `langue` : en_us, fr_fr, de_de..."""
    chemin = os.path.join(racine_jeu, 'Locale', '%s_data.dat' % langue)
    if not os.path.exists(chemin):
        return {}
    brut = open(chemin, 'rb').read().decode('utf-8', 'replace')
    par_hash = {}
    for m in re.finditer(r'^(\d+)\t(ucdt|ugdt)\t(.*)$', brut, re.M):
        if m.group(2) == 'ucdt':
            par_hash[int(m.group(1))] = m.group(3).strip()
    return par_hash


def nom_de(par_hash, name_id):
    """Le nom affiche pour un NAME_ID, ou None."""
    if not name_id:
        return None
    try:
        return par_hash.get(id_langue(name_id))
    except (TypeError, ValueError):
        return None
