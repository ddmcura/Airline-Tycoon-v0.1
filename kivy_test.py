from kivy.app import App
from kivy.uix.label import Label

class KivyTestApp(App):
    def build(self):
        return Label(text="🛫 Kivy is working! Welcome aboard.")

if __name__ == "__main__":
    KivyTestApp().run()
