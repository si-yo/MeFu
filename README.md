# MeFu – Menu Flottant Gestuel pour Kivy / KivyMD<br>

[![Demo Video](https://img.youtube.com/vi/nqXrZo2a2Qg/0.jpg)](https://youtu.be/nqXrZo2a2Qg)
> 🎥 Cliquez sur la vignette pour voir la démonstration.<br>

MeFu est un **menu contextuel flottant** pour applications Kivy / KivyMD, ouvrable :<br>
- par **clic droit** (menu à la position du clic),<br>
- par **gestes de la main** via la caméra (Mediapipe).<br>

Il supporte des **sous-menus hiérarchiques**, un bouton **Retour**, l’animation d’ouverture/fermeture, et un système d’actions dynamiques.<br>

---

## ✨ Fonctionnalités<br>

| Fonction | Description |
|---------|-------------|
| Clic droit | Ouvre le menu à l’endroit du pointeur. |
| Gestes caméra | Mouvement / contact doigts → ouverture au centre de l’écran. |
| Navigation fine | Déplacement du curseur “virtuel” avec l’index + sélection pouce/majeur rapprochés. |
| Sous-menus | Items imbriqués avec historique et bouton **Retour**. |
| Actions dynamiques | `add_action(nom, fonction)` pour brancher facilement des callbacks. |
| Thème KivyMD | Utilise `theme_cls` (primary / accent) – changement d’accent à chaud. |
| Animation | Apparition progressive + (optionnel) animation de fermeture en cercle. |
| Mode geste toggle | Activation / désactivation à la volée (caméra libérée). |
| Extensible | Sous-classe minimale pour ajouter tes handlers sans toucher au cœur. |

---

## 🗂 Arborescence (exemple)<br>

project/<br>
│<br>
├─ mefu.py               # Classe MeFu (logique + gestures + menu)<br>
├─ test_mefu.py          # Exemple / App de démonstration (DemoApp + handlers)<br>
├─ requirements.txt<br>
├─ README.md<br>
└─ models/<br>
└─ vosk/              # (Optionnel) modèle Vosk (si reconnaissance vocale ajoutée)<br>

---

## 🔧 Installation<br>

### 1. Cloner<br>

```bash
git clone https://github.com/ton-compte/mefu.git
cd mefu

2. Créer et activer un venv (recommandé)

python3 -m venv .venv
source .venv/bin/activate      # macOS / Linux
# ou
.\.venv\Scripts\activate       # Windows

3. Installer les dépendances

pip install --upgrade pip
pip install -r requirements.txt

💡 Sur macOS (Apple Silicon), si opencv-python pose problème :
pip install opencv-python-headless ou brew install opencv.
```
⸻

▶️ Lancer la démo<br>
```bash
python test_mefu.py
```
	•	Clic droit n’importe où → menu.<br>
	•	Sous-menu Couleurs → change accent_palette.<br>
	•	Mode geste → active/désactive la caméra (menu gestuel).<br>

⸻

🧠 Gestes (par défaut)<br>

Geste	Effet<br>
Mouvement configuré (ex: contact pouce/auriculaire ou swipe vertical)	Ouvre le menu (centré).<br>
Index dirigé	Navigation dans les entrées.<br>
Pouce ↔ majeur rapprochés (< seuil)	Sélection (simule clic).<br>
Swipe droit (dx > seuil)	Ferme le menu (si ouvert).<br>

Le code actuel utilise Mediapipe Hands pour landmarks et calcule des distances / déplacements.<br>
Tu peux adapter les conditions dans CameraWidget.update().

⸻

🏗 Ajouter des actions<br>

Dans ton code principal :<br>
```python
mefu.add_action("say_hello", lambda: print("Hello!"))
```
Dans le menu_config :
```python
menu_config = {
    "menu": {
        "items": [
            {"name": "Hello", "icon": "hand-wave", "handler": "say_hello"},
            {
                "name": "Extras",
                "icon": "menu",
                "children": [
                    {"name": "Sub A", "icon": "alpha-a-box", "handler": "sub_a"},
                    {"name": "Sub B", "icon": "alpha-b-box", "handler": "sub_b"},
                ]
            }
        ]
    }
}
```


⸻

🎨 Personnalisation UI<br>

Élément	Où modifier<br>
Largeur du menu	Paramètre size à l’instanciation.<br>
Padding / Spacing	Dans _create_context_menu (self.menu_layout).<br>
Couleurs	theme_cls.primary_palette, theme_cls.accent_palette.<br>
Animation	Durées dans Animation(..., d=0.3, t="out_cubic").<br>
Bouton Retour	Bloc if self.menu_history: dans _create_context_menu.<br>


⸻

🛠 Débogage & Conseils<br>

Problème	Solution<br>
Menu mal positionné (HiDPI)	Ajuster heuristique dans show_menu() (scale).<br>
Caméra occupée	Vérifier qu’une autre app n’utilise pas / relancer toggle.<br>
Gestes trop sensibles	Augmenter les seuils dy > 40, distance doigts, timers.<br>
CPU élevé	Diminuer fréquence : remplacer Clock.schedule_interval(..., 1/30) par 1/20.<br>
Couleur accent non changée	Vérifier que palette existe dans la liste KivyMD ('Red','Blue','Green',...).<br>


⸻

🧪 Tests rapides (manuel)<br>
	1.	Ouvrir → Sous-menu → Retour → Revenir.<br>
	2.	Changer plusieurs couleurs d’affilée.<br>
	3.	Ouvrir menu → geste fermeture.<br>
	4.	Désactiver geste → vérifier que la caméra est libérée (process CPU chute).<br>

⸻

🚀 Roadmap (suggestions)<br>
	•	Mode radial alternatif<br>
	•	Support multi-mains / reconnaissance de clic “air tap”<br>
	•	Intégration microphone + commandes vocales (via Vosk)<br>
	•	Thèmes dynamiques sauvegardés utilisateur<br>
	•	Tests unitaires sur parser menu_config<br>

⸻

🤝 Contribution<br>
	1.	Fork<br>
	2.	Créer une branche : feature/ma-fonction<br>
	3.	Commit : feat: ajout option X<br>
	4.	PR avec description claire.<br>


📹 Vidéo<br>

👉 https://youtu.be/nqXrZo2a2Qg <br>

⸻

💬 Contact <br>

Ouvre une issue ou envoie un message si tu veux proposer des idées / optimiser les gestes.<br>
