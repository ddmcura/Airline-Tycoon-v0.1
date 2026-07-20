# game/gui/app.py

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.lang import Builder

# Load the KV layout for dashboard
Builder.load_file("game/gui/kv/dashboard.kv")

class DashboardScreen(Screen):
    pass

class AirlineTycoonApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(DashboardScreen(name="dashboard"))
        return sm

if __name__ == '__main__':
    AirlineTycoonApp().run()
