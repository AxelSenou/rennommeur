"""Renommeur de fichiers - application Android (Kivy).

Fichiers sans extension -> 1.jpg, 2.jpg, 3.jpg, ...
"""
import os
import re

from kivy.app import App
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

DOSSIER_DEFAUT = "/storage/emulated/0/Download" if platform == "android" else os.path.expanduser("~")


# ---------- Logique de renommage ----------
def tri_naturel(nom):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", nom)]


def lister_sans_extension(dossier):
    return sorted(
        (f for f in os.listdir(dossier)
         if os.path.isfile(os.path.join(dossier, f))
         and not f.startswith(".") and "." not in f),
        key=tri_naturel,
    )


def construire_plan(fichiers, ext, debut):
    return [(f, f"{i}.{ext}") for i, f in enumerate(fichiers, start=debut)]


def appliquer_plan(dossier, plan):
    """Renommage en deux passes pour éviter toute collision."""
    for a, n in plan:
        if os.path.exists(os.path.join(dossier, n)):
            raise FileExistsError(n)
    tmp = []
    for a, n in plan:
        t = a + ".__tmp__"
        os.rename(os.path.join(dossier, a), os.path.join(dossier, t))
        tmp.append((t, n))
    for t, n in tmp:
        os.rename(os.path.join(dossier, t), os.path.join(dossier, n))


# ---------- Permissions Android ----------
def demander_permissions():
    if platform != "android":
        return
    try:
        from android.permissions import request_permissions, Permission
        request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
        from jnius import autoclass
        if autoclass("android.os.Build$VERSION").SDK_INT >= 30:
            Environment = autoclass("android.os.Environment")
            if not Environment.isExternalStorageManager():
                Intent = autoclass("android.content.Intent")
                Settings = autoclass("android.provider.Settings")
                Uri = autoclass("android.net.Uri")
                activity = autoclass("org.kivy.android.PythonActivity").mActivity
                intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
                intent.setData(Uri.parse("package:" + activity.getPackageName()))
                activity.startActivity(intent)
    except Exception as e:
        print("Permissions :", e)


# ---------- Interface ----------
class RenommeurApp(App):
    title = "Renommeur"

    def build(self):
        demander_permissions()
        racine = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        racine.add_widget(Label(text="Dossier", size_hint_y=None, height=dp(24), halign="left"))
        ligne = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        self.dossier = TextInput(text=DOSSIER_DEFAUT, multiline=False)
        ligne.add_widget(self.dossier)
        ligne.add_widget(Button(text="Parcourir", size_hint_x=0.35, on_release=self.parcourir))
        racine.add_widget(ligne)

        params = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        self.ext = TextInput(text="jpg", hint_text="Extension", multiline=False)
        self.debut = TextInput(text="1", hint_text="Début", multiline=False, input_filter="int")
        params.add_widget(self.ext)
        params.add_widget(self.debut)
        racine.add_widget(params)

        racine.add_widget(Button(text="Analyser", size_hint_y=None, height=dp(52),
                                 on_release=self.analyser))

        self.apercu = Label(text="", size_hint_y=None, halign="left", valign="top",
                            text_size=(None, None))
        self.apercu.bind(texture_size=lambda w, s: setattr(w, "height", s[1]))
        sv = ScrollView()
        sv.add_widget(self.apercu)
        racine.add_widget(sv)

        self.bouton_renommer = Button(text="Renommer", size_hint_y=None, height=dp(56),
                                      disabled=True, on_release=self.renommer)
        racine.add_widget(self.bouton_renommer)
        self.plan = []
        return racine

    def parcourir(self, *_):
        chooser = FileChooserListView(path=self.dossier.text or DOSSIER_DEFAUT, dirselect=True)
        boite = BoxLayout(orientation="vertical")
        boite.add_widget(chooser)
        ok = Button(text="Choisir ce dossier", size_hint_y=None, height=dp(52))
        boite.add_widget(ok)
        popup = Popup(title="Choisir un dossier", content=boite, size_hint=(0.95, 0.9))

        def choisir(*_):
            self.dossier.text = chooser.path
            popup.dismiss()

        ok.bind(on_release=choisir)
        popup.open()

    def analyser(self, *_):
        self.bouton_renommer.disabled = True
        dossier = self.dossier.text.strip()
        try:
            fichiers = lister_sans_extension(dossier)
        except Exception as e:
            self.apercu.text = f"Dossier inaccessible : {e}\nVérifiez l'autorisation « Accès à tous les fichiers »."
            return
        if not fichiers:
            self.apercu.text = "Aucun fichier sans extension dans ce dossier."
            return
        ext = self.ext.text.strip().lstrip(".") or "jpg"
        debut = int(self.debut.text or 1)
        self.plan = construire_plan(fichiers, ext, debut)
        lignes = [f"{a}  ->  {n}" for a, n in self.plan[:30]]
        if len(self.plan) > 30:
            lignes.append(f"... (+{len(self.plan) - 30} autres)")
        self.apercu.text = f"{len(self.plan)} fichier(s) :\n" + "\n".join(lignes)
        self.apercu.text_size = (self.root.width - dp(24), None)
        self.bouton_renommer.disabled = False

    def renommer(self, *_):
        try:
            appliquer_plan(self.dossier.text.strip(), self.plan)
            self.apercu.text = f"Terminé : {len(self.plan)} fichiers renommés."
            self.plan = []
            self.bouton_renommer.disabled = True
        except FileExistsError as e:
            self.apercu.text = f"Conflit : {e} existe déjà. Changez le numéro de départ."
        except Exception as e:
            self.apercu.text = f"Erreur : {e}"


if __name__ == "__main__":
    RenommeurApp().run()
