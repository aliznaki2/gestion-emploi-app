"""
Lanceur d'application backend Django pour la gestion d'emplois du temps (OFPPT).

Ce script permet d'exécuter directement `python app.py` pour démarrer le serveur
Django sur le port 3001 (port utilisé par l'interface React).
L'ancien script monolithique Flask a été sauvegardé dans `app_legacy_flask.py`.
"""
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    from django.core.management import execute_from_command_line
    
    port = os.environ.get('PORT', '3001')
    print(f"\n=======================================================")
    print(f" [OK] Démarrage du Backend Django (OFPPT Timetable)")
    print(f" -> Serveur API : http://localhost:{port}")
    print(f" -> Admin Panel : http://localhost:{port}/admin/")
    print(f"=======================================================\n")
    
    # Exécute Django runserver sur le port configuré
    execute_from_command_line([sys.argv[0], 'runserver', f'0.0.0.0:{port}'])
