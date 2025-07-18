
import os
import json
import threading
import time
import subprocess
from datetime import datetime
from pathlib import Path

# Kivy de base ---------------------------------------------------------------
from kivy.config import Config
Config.set("input", "mouse", "mouse,multitouch_on_demand")

from kivy.core.window       import Window
from kivy.metrics           import dp
from kivy.clock             import Clock, mainthread
from kivy.properties        import StringProperty, ListProperty, NumericProperty, BooleanProperty
from kivy.uix.floatlayout   import FloatLayout
from kivy.uix.boxlayout     import BoxLayout
from kivy.uix.label         import Label
from kivy.uix.image         import Image
from kivy.uix.filechooser   import FileChooserIconView
from kivy.uix.behaviors     import DragBehavior
from kivy.input.motionevent import MotionEvent
from kivy.graphics          import Color, RoundedRectangle, Rectangle, ScissorPush, ScissorPop
from kivy.graphics.texture  import Texture

import cv2
import mediapipe as mp

# KivyMD ---------------------------------------------------------------------
from kivymd.app          import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card      import MDCard
from kivymd.uix.button    import MDIconButton, MDFloatingActionButton, MDRaisedButton, MDFlatButton
from kivymd.uix.label     import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.dialog    import MDDialog
from kivymd.uix.scrollview import MDScrollView
from kivymd.uix.list      import MDList, OneLineListItem

from kivymd.toast         import toast

# --- Vosk (speech) ----------------------------------------------------------
import queue
import sounddevice as sd
from vosk import Model, KaldiRecognizer

class MeFu(FloatLayout):
    def __init__(self, theme_cls, menu_config, size, _b_activate_gestual=False, _b_anim=False,  **kwargs):
        super().__init__(**kwargs)
        self.theme_cls = theme_cls
        self.menu_config = menu_config
        self.size_param = size
        self.menu_history = []
        self.menu_card = None
        self.menu_layout = None
        self.mtx = False
        self._b_anim = _b_anim
        self.sub = self.SubMeFu(self)
        self.action_methods = {}
        self.selection_triggered = False
        # Tracking pour normalisation de position (ex-MeFuApp)
        self._from_gesture = False
        self._click_pos = (0, 0)
        
        if _b_activate_gestual:
            self.camera_widget = self.CameraWidget(self.gesture_callback, size_hint=(1, 1))
            self.camera_widget.opacity = 0
            self.add_widget(self.camera_widget)

        Window.bind(on_mouse_down=self._on_mouse)

    def _on_mouse(self, window, x, y, button, modifiers):
        if button == "right":
            self.show_menu((x, y))

    def add_action(self, option_name, method):
        def wrapper(*args, **kwargs):
            result = method(*args, **kwargs)
            self.sub.close_menu(self)
            return result
        self.action_methods[option_name] = wrapper

    def show_menu(self, pos):
        """
        Ouvre le menu au clic droit avec normalisation optionnelle (HiDPI + inversion Y).
        """
        raw_x, raw_y = pos

        # Heuristique HiDPI (ex-Retina)
        scale = 1.0
        if raw_x * 1.9 <= Window.width:
            scale = 2.0

        norm_x = raw_x * scale
        norm_y = raw_y * scale

        # Inversion Y heuristique
        if raw_y < Window.height * 0.4:
            norm_y = Window.height - norm_y

        self._from_gesture = False
        self._click_pos = (norm_x, norm_y)

        # Appel direct à la sous-classe pour conserver le workflow existant
        self.sub.show_context_menu(self._click_pos, self)

    def gesture_callback(self, gesture, pos, select=False):
        if gesture == "open_menu":
            # Forcer le menu au centre pour un geste d'ouverture
            self._from_gesture = True
            pos = (Window.width / 2, Window.height / 2)
            if not self.mtx:
                self.sub.show_context_menu(pos, self)
            return
        elif gesture == "swipe_right":
            if self.mtx:
                self._close_menu(self)
        elif gesture == "navigate":
            if self.mtx and self.menu_card is not None:
                if self.menu_card.collide_point(*pos):
                    hovered = None
                    for child in self.menu_layout.children:
                        child_x, child_y = child.to_window(child.x, child.y)
                        if (pos[0] >= child_x and pos[0] <= child_x + child.width and
                            pos[1] >= child_y and pos[1] <= child_y + child.height):
                            hovered = child
                            child.md_bg_color = self.theme_cls.accent_light
                        else:
                            child.md_bg_color = self.theme_cls.bg_normal
                    if hovered:
                        if select:
                            if not self.selection_triggered:
                                if any(hasattr(w, "text") and w.text == "Retour" for w in hovered.children):
                                    self._go_back()
                                else:
                                    fake_touch = self.FakeTouch(pos)
                                    hovered.dispatch("on_touch_down", fake_touch)
                                    hovered.dispatch("on_touch_up", fake_touch)
                                self.selection_triggered = True
                        else:
                            self.selection_triggered = False
                else:
                    for child in self.menu_layout.children:
                        child.md_bg_color = self.theme_cls.bg_normal
                    self.selection_triggered = False

    def _create_context_menu(self, pos, parent_layout):
        self._close_menu(parent_layout)
        self.main_layout = parent_layout
        num_items = len(self.menu_config["menu"]["items"])
        if self.menu_history:
            num_items += 1
        menu_width = self.size_param
        menu_height = num_items * 60 + 30
        if pos :
            self.pos = pos
        x, y = self.pos  # x,y = position du clic (coin supérieur gauche souhaité)

        # Ajustement horizontal (ne pas sortir de l'écran à droite / gauche)
        if x + menu_width > Window.width - dp(10):
            x = Window.width - menu_width - dp(10)
        if x < dp(10):
            x = dp(10)

        # --- SUPPRESSION de l'ancien ajustement vertical ici ---

        self.menu_card = MDCard(
            size_hint=(None, None),
            size=(menu_width, 0),
            pos=(x, y),
            elevation=12,
            radius=[15],
        )

        # Ajustement post-création si ouverture par clic (utilise _click_pos déjà normalisé)
        if not self._from_gesture:
            x, y = self._click_pos
            # Hauteur effective connue après calcul (menu_height)
            final_x = min(max(dp(10), x), Window.width - menu_width - dp(10))
            final_y = min(max(dp(10), y), Window.height - menu_height - dp(10))
            self.menu_card.pos = (final_x, final_y)

        self.menu_layout = MDBoxLayout(
            orientation="vertical",
            padding=[15, 24, 15, 15],  # valeur par défaut (sans sous-menu)
            spacing=10
        )

        if self.menu_history:
            back_item = MDCard(
                orientation="horizontal",
                spacing=15,
                size_hint_y=None,
                height=50,
                radius=[10],
                md_bg_color=self.theme_cls.bg_normal,
                ripple_behavior=True,
                ripple_color=(0, 0, 0, 0.2)
            )
            back_icon = MDIconButton(
                icon="arrow-left",
                theme_text_color="Custom",
                text_color=self.theme_cls.accent_color,
                size_hint=(None, None),
                size=(dp(40), dp(40)),
                pos_hint={"center_y": 0.5},
                on_release=lambda x: self._go_back()
            )
            back_label = MDLabel(
                text="Retour",
                theme_text_color="Custom",
                text_color=self.theme_cls.text_color,
                halign="left",
                size_hint=(1, None),
                height=dp(40),
                pos_hint={"center_y": 0.5},
            )
            back_item.md_bg_color = self.theme_cls.bg_dark if hasattr(self.theme_cls, "bg_dark") else (0, 0, 0, 0.25)
            back_item.padding = (4, 4, 4, 4)
            # Ajuste le padding top quand 'Retour' est présent pour ne PAS ajouter d'espace excessif
            pad = list(self.menu_layout.padding)
            pad[1] = 15   # même top que les autres menus (au lieu de 24)
            self.menu_layout.padding = pad

            back_item.opacity = 1
            back_item.add_widget(back_icon)
            back_item.add_widget(back_label)
            self.menu_layout.add_widget(back_item)
        for item in self.menu_config["menu"]["items"]:
            item_card = MDCard(
                orientation="horizontal",
                spacing=15,
                size_hint_y=None,
                height=50,
                radius=[10],
                md_bg_color=self.theme_cls.bg_normal,
                ripple_behavior=True,
                ripple_color=(0, 0, 0, 0.2)
            )
            item_card.bind(on_touch_down=self.sub._on_item_touch)
            handler = item.get("handler")
            icon_button = MDIconButton(
                icon=item["icon"],
                theme_text_color="Custom",
                text_color=self.theme_cls.accent_color,
                size_hint=(None, None),
                size=(dp(40), dp(40)),
                pos_hint={"center_y": 0.5},
                on_release=lambda x, handler=handler: self._execute_action(handler) if handler else None,
            )
            icon_button.bind(on_touch_down=lambda inst, touch: True)
            label = MDLabel(
                text=item["name"],
                theme_text_color="Custom",
                text_color=self.theme_cls.text_color,
                halign="left",
                size_hint=(1, None),
                height=dp(40),
                pos_hint={"center_y": 0.5},
            )
            item_card.add_widget(icon_button)
            item_card.add_widget(label)
            self.menu_layout.add_widget(item_card)
        # Normalisation des hauteurs et alignements (évite décalages visuels)
        for child in self.menu_layout.children:
            if isinstance(child, MDCard):
                child.height = 50
        # Si on est dans un sous-menu, garantir l'opacité de 'Retour'
        if self.menu_history and self.menu_layout.children:
            self.menu_layout.children[-1].opacity = 1
        self.menu_card.add_widget(self.menu_layout)
        parent_layout.add_widget(self.menu_card)
        Window.bind(on_touch_down=lambda inst, touch: self._global_touch(touch))
        from kivy.animation import Animation
        anim_open = Animation(size=(menu_width, menu_height), d=0.3, t="out_cubic")
        anim_open.bind(on_progress=self._show_items_progressivement)
        anim_open.start(self.menu_card)
        

    def _global_touch(self, touch):
        if touch.button == "left":
            if self.menu_card and not self.menu_card.collide_point(*touch.pos):
                self.sub.close_menu(self)
        return False

    def _close_menu(self, parent_layout):
        if self.menu_card and self.menu_card in parent_layout.children:
            from kivy.animation import Animation
            if self._b_anim:
                anim_shrink = Animation(
                    size=(self.menu_card.size[0], 15),
                    pos=(self.menu_card.pos[0], self.menu_card.pos[1] + self.menu_card.size[1] - 15),
                    d=0.2,
                    t="out_cubic",
                )
                anim_shrink.bind(on_progress=self._hide_items_progressivement)
                anim_shrink.bind(on_complete=self._to_circle_phase)
                anim_shrink.start(self.menu_card)
            else:
                self._cleanup_menu(parent_layout)

    def _show_items_progressivement(self, animation, widget, progress):
        """
        Animation d'apparition :
        - Rend immédiatement visible l'item 'Retour' (index le plus haut dans children)
          afin qu'il ne disparaisse pas pendant l'ouverture.
        - Les autres items apparaissent progressivement comme avant.
        """
        if self.menu_layout and self.menu_card:
            total_height = self.menu_card.size[1]
            total_children = len(self.menu_layout.children)
            for index, child in enumerate(self.menu_layout.children):
                # L'ordre est inversé: le dernier ajouté est en haut visuellement.
                # On calcule une hauteur seuil différente pour le premier (back) item.
                is_back_candidate = bool(self.menu_history) and (index == total_children - 1)
                if is_back_candidate:
                    # Toujours visible dans un sous-menu
                    child.opacity = 1
                else:
                    # Seuil classique (index+1)*60 mais on adoucit légèrement ( -10 )
                    item_position = (index + 1) * 60 - 10
                    child.opacity = 1 if total_height > item_position else 0

    def _hide_items_progressivement(self, animation, widget, progress):
        if self.menu_layout:
            total_height = self.menu_card.size[1] if self.menu_card else 0
            for index, child in enumerate(self.menu_layout.children):
                item_position = total_height - (index + 1) * 60
                child.opacity = 1 if item_position > 0 else 0

    def _to_circle_phase(self, *args):
        if self._b_anim and self.menu_card:
            from kivy.animation import Animation
            anim_circle = Animation(
                size=(15, 15),
                pos=(self.menu_card.pos[0] + (self.menu_card.size[0] - 15) / 2, self.menu_card.pos[1]),
                d=0.2,
                t='out_cubic'
            )
            anim_circle.bind(on_complete=self._close_circle)
            anim_circle.start(self.menu_card)

    def _close_circle(self, *args):
        if self._b_anim and self.menu_card:
            from kivy.animation import Animation
            anim_close = Animation(size=(0, 0), d=0.3, t='out_cubic')
            anim_close.bind(on_complete=self._cleanup_menu)
            anim_close.start(self.menu_card)

    def _cleanup_menu(self, *args):
        if self.menu_card and self.menu_layout in self.menu_card.children:
            self.menu_card.remove_widget(self.menu_layout)
        Window.unbind(on_touch_down=self._global_touch)
        if self.menu_card and self.menu_card.parent:
            self.menu_card.parent.remove_widget(self.menu_card)
        self.menu_card = None
        self.mtx = False

    def _execute_action(self, handler_name):
        if handler_name in self.action_methods:
            self.action_methods[handler_name]()
        else:
            print(f"Handler {handler_name} introuvable.")

    def _go_back(self):
        if self.menu_history:
            prev_config = self.menu_history.pop()
            self.menu_config = prev_config
            self._cleanup_menu(self)
            self.sub.show_context_menu(self.sub.pos, self)

    class SubMeFu:
        def __init__(self, parent):
            self.parent = parent
            self.pos = None

        def show_context_menu(self, pos, layout):
            if not self.parent.mtx:
                self.pos = pos
                self.parent._create_context_menu(pos, layout)
                self.parent.mtx = True

        def close_menu(self, layout):
            self.parent._close_menu(layout)

        def _on_item_touch(self, instance, touch):
            if hasattr(touch, "is_fake") and touch.is_fake:
                if getattr(touch, "processed", False):
                    return
                touch.processed = True
            if instance.collide_point(*touch.pos):
                original_color = instance.md_bg_color
                instance.md_bg_color = self.parent.theme_cls.accent_light
                from kivy.animation import Animation
                Animation(md_bg_color=original_color, d=0.3).start(instance)
                total_children = len(self.parent.menu_layout.children)
                reversed_index = total_children - self.parent.menu_layout.children.index(instance) - 1
                if self.parent.menu_history and reversed_index == 0:
                    self.parent._go_back()
                    return
                config_index = reversed_index - 1 if self.parent.menu_history else reversed_index
                try:
                    item = self.parent.menu_config["menu"]["items"][config_index]
                except IndexError:
                    print("Index error: config_index out of range", config_index)
                    return
#                if "children" in item and item["children"]:
#                    self.parent.menu_history.append(self.parent.menu_config)
#                    new_menu_config = {"menu": {"items": item["children"]}}
#                    self.parent.menu_config = new_menu_config
#                    self.parent._cleanup_menu(self.parent)
#                    self.show_context_menu(self.pos, self.parent)

                if "children" in item and item["children"]:
                    # Empile la configuration actuelle
                    self.parent.menu_history.append(self.parent.menu_config)
                    # Nouvelle config = sous-items
                    new_menu_config = {"menu": {"items": item["children"]}}
                    self.parent.menu_config = new_menu_config
                    # Nettoie l'ancien menu
                    self.parent._cleanup_menu(self.parent)
                    # Réouvre à la même position
                    self.show_context_menu(self.pos, self.parent)
                else:
                    handler_name = item.get("handler")
                    if handler_name in self.parent.action_methods:
                        self.parent.action_methods[handler_name]()
                    else:
                        print(f"Handler {handler_name} introuvable.")
                    self.parent._close_menu(instance.parent)

    class FakeTouch(MotionEvent):
        def __init__(self, pos):
            super().__init__("fake", 0, {})
            self.sx = pos[0] / Window.width
            self.sy = pos[1] / Window.height
            self.x, self.y = pos
            self.pos = pos
            self.button = "left"
            self.is_fake = True
            self.processed = False
        def depack(self, args=None):
            pass

    class CameraWidget(Image):
        def __init__(self, gesture_callback, **kwargs):
            super().__init__(**kwargs)
            self.capture = cv2.VideoCapture(0)
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5)
            self.prev_wrist_x = None
            self.prev_wrist_y = None
            self.last_swipe_time = 0
            self.gesture_callback = gesture_callback
            Clock.schedule_interval(self.update, 1.0/30)

        def update(self, dt):
            ret, frame = self.capture.read()
            if ret:
                frame = cv2.flip(frame, 1)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.hands.process(rgb_frame)
                frame_height, frame_width = frame.shape[:2]
                current_time = time.time()
                if results.multi_hand_landmarks:
                    hand_landmarks = results.multi_hand_landmarks[0]
                    wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
                    wrist_x = int(wrist.x * frame_width)
                    wrist_y = int(wrist.y * frame_height)
                    if self.prev_wrist_y is not None:
                        dy = self.prev_wrist_y - wrist_y
                        middle_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
                        middle_dist = ((middle_tip.x - wrist.x)**2 + (middle_tip.y - wrist.y)**2)**0.5
                        if dy > 40 and (current_time - self.last_swipe_time) > 0.3 and wrist_y < frame_height * 0.9 and middle_dist > 0.1:
                            self.last_swipe_time = current_time
                            if self.gesture_callback:
                                self.gesture_callback("open_menu", (wrist_x, frame_height - wrist_y))
                    self.prev_wrist_y = wrist_y
                    if self.prev_wrist_x is not None:
                        dx = wrist_x - self.prev_wrist_x
                        if dx > 40 and (current_time - self.last_swipe_time) > 1.0:
                            self.last_swipe_time = current_time
                            if self.gesture_callback:
                                self.gesture_callback("swipe_right", (wrist_x, frame_height - wrist_y))
                    self.prev_wrist_x = wrist_x
                    index_finger = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
                    index_x = int(index_finger.x * frame_width)
                    index_y = int(index_finger.y * frame_height)
                    nav_pos = (index_x, frame_height - index_y)
                    thumb_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
                    middle_finger = hand_landmarks.landmark[self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP]
                    dx_thumb = thumb_tip.x - middle_finger.x
                    dy_thumb = thumb_tip.y - middle_finger.y
                    dist_thumb = (dx_thumb*dx_thumb + dy_thumb*dy_thumb) ** 0.5
                    select = (dist_thumb < 0.02)
                    if self.gesture_callback:
                        self.gesture_callback("navigate", nav_pos, select)
                buf = cv2.flip(frame, 0).tobytes()
                texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
                texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
                self.texture = texture

