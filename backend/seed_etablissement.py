"""Seed script: create NTIC2 establishment and assign all existing data."""
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from core.models import Etablissement, Secteur, Groupe, Salle, Module, Professeur, AnneeScolaire

etab, created = Etablissement.objects.get_or_create(
    code='NTIC2',
    defaults={
        'nom': 'Institut Spécialisé de Technologie Appliquée NTIC 2',
        'nom_court': 'ISTA NTIC 2',
        'ville': 'Casablanca',
        'quartier': 'Sidi Maârouf',
        'adresse': '1029, Route de Bouskoura, Sidi Maârouf, Casablanca',
        'email': 'istanticsm@gmail.com',
        'site_web': 'https://sites.google.com/view/ista-ntic-sm/accueil',
        'couleur_accent': '#1a5fa8',
    }
)
status = "created" if created else "already exists"
print(f"Etablissement NTIC2: {status} (id={etab.id})")

for Model in [Secteur, Groupe, Salle, Module, Professeur, AnneeScolaire]:
    count = Model.objects.filter(etablissement__isnull=True).update(etablissement=etab)
    print(f"  {Model.__name__}: {count} rows linked to NTIC2")

print("\nDone!")
