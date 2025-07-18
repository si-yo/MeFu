from kivy.config import Config
Config.set("input", "mouse", "mouse,multitouch_on_demand")

from kivy.core.window import Window
from kivy.metrics import dp
from kivymd.app import MDApp
from kivymd.toast import toast
from kivy.uix.widget import Widget

# Classe MeFu d’origine (copie dans mefu.py)
from mefu import MeFu


class MeFuApp:
    """
    Subclass réduite : ne contient plus la logique de positionnement
    (fusionnée dans MeFu). Sert uniquement à déclarer les handlers.
    """

    def say_hello(self):
        toast("Hello World!")

    def set_accent_color(self, mefu, palette):
        mefu.theme_cls.accent_palette = palette
        toast(f"Accent -> {palette}")

    def toggle_gesture(self, mefu):
        if hasattr(mefu, "camera_widget") and mefu.camera_widget:
            mefu.remove_widget(mefu.camera_widget)
            try:
                mefu.camera_widget.capture.release()
            except Exception:
                pass
            mefu.camera_widget = None
            toast("Mode geste désactivé")
        else:
            mefu.camera_widget = MeFu.CameraWidget(
                mefu.gesture_callback,
                size_hint=(1, 1),
            )
            mefu.camera_widget.opacity = 0
            mefu.add_widget(mefu.camera_widget)
            toast("Mode geste activé")


class DemoApp(MDApp):
    RAINBOW = [
        ("Rouge", "Red"),
        ("Orange", "Orange"),
        ("Jaune", "Yellow"),
        ("Vert", "Green"),
        ("Bleu", "Blue"),
        ("Indigo", "Indigo"),
        ("Violet", "Purple"),
    ]

    def build(self):
        # Thème global
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "DeepPurple"
#        self.theme_cls.accent_palette = "Pink"

        # Sous-menu Couleurs
        rainbow_children = [
            {"name": label, "icon": "circle", "handler": f"accent_{pal.lower()}"}
            for label, pal in self.RAINBOW
        ]

        menu_config = {
            "menu": {
                "items": [
                    {"name": "Hello World!", "icon": "hand-wave", "handler": "say_hello"},
                    {"name": "Couleurs", "icon": "palette", "children": rainbow_children},
                    {"name": "Mode geste", "icon": "gesture-tap-button", "handler": "toggle_gesture"},
                ]
            }
        }

        mefu = MeFu(
            theme_cls=self.theme_cls,
            menu_config=menu_config,
            size=dp(280),
            _b_activate_gestual=False,
            _b_anim = True
        )
        
        handler = MeFuApp()
        
        w = Widget(size_hint=(1,1))
        w.add_widget(mefu)

        # Branchement des actions de base
        mefu.add_action("say_hello", handler.say_hello)
        mefu.add_action("toggle_gesture", lambda *a: handler.toggle_gesture(mefu))

        # Branchement des couleurs
        for label, pal in self.RAINBOW:
            handler_name = f"accent_{pal.lower()}"
            mefu.add_action(handler_name, lambda *a, p=pal: handler.set_accent_color(mefu, p))

        return w


if __name__ == "__main__":
    DemoApp().run()
