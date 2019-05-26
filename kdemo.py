
# Authored by Chris Miller '20
# To provide a GUI demo of the Group Assignment Tool

from kemeny_GAT import GroupAssign

import kivy
kivy.require('1.10.1')

from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window

from kivy.uix.screenmanager import ScreenManager, Screen

from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.slider import Slider
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.textinput import TextInput


class ScreenManaging(ScreenManager):
    pass

class SplashScreen(Screen):
    def __init__(self, **kwargs):
        super(SplashScreen, self).__init__(**kwargs)
class EndScreen(Screen):
    def __init__(self, **kwargs):
        super(EndScreen, self).__init__(**kwargs)

    def init_type_callback(self, val):
        # Set stuff active/inactive
        self.ids.time_limit_input.disabled = val
        self.ids.combination_input.disabled = not val
        pass

    def process_dataset(self):
        questions = [screen for screen in self.manager.screens if
                    screen.__class__.__name__ == "Question"]
        q_text_list = []
        q_types = {}
        q_weights = {}

        for question in questions:
            q_text = question.ids.text_label.text
            q_weights[q_text] = question.ids.weight_slider.value
            q_types[q_text] = question.ids.type_label.text

            q_text_list.append(q_text)

        try:
            n_iter = abs(int(self.ids.iteration_input))
        except:
            print("Invalid iteration count, using default value " + \
                    str(self.default_iterations))
            n_iter = self.default_iterations

        if strong:
            mode = "Strong"
            try:
                combos = abs(int(self.ids.combination_input))
            except:
                print("Invalid combination count, using default value " + \
                        str(self.default_combinations))
                combos = self.default_combinations
        else:
            mode = "Random"
            try:
                timelimit = abs(int(self.ids.time_limit_input))
            except:
                print("Invalid combination count, using default value " + \
                        str(self.default_timelimit))
                timelimit = self.default_timelimit

# Types:
# S: (String Response Question)
# M: (Multiple Choice Question)
# C: (Checkbox Question)
# I: (Isolation Question)
# Sc: (Scheduling Question)
# R? idk if we should use lol
class Question(Screen):
    def __init__(self, q_text, q_type, num, **kwargs):
        super(Question, self).__init__(**kwargs)
        self.ids.text_label.text = q_text
        self.ids.type_label.text = q_type

        self.ids.activate_toggle.group = 'activation_group_' + str(num)
        self.ids.deactivate_toggle.group = 'activation_group_' + str(num)

    def activate_callback(self, val):
        self.ids.distrib_spinner.disabled = val
        self.ids.weight_slider.disabled = val

class KemenyDemo(App):
    def __init__(self, q_text_list, q_type_list):
        super(KemenyDemo, self).__init__()
        Window.size = (800,400)
        Window.clearcolor = (.259, .446, .296, 1)

        if len(q_text_list) != len(q_type_list):
            print("Fatal error: Question text list and question type list do not correspond.")
            exit(1)

        self.q_text_list = q_text_list
        self.q_type_list = q_type_list
        self.q_list = []

    def build(self):
        sm = ScreenManaging()

        sm.add_widget(SplashScreen(name='Start'))
        for i,q_text in enumerate(self.q_text_list):
            cQuestion = Question(q_text, self.q_type_list[i], i, name = "Q" + str(i))
            self.q_list.append(cQuestion)
            sm.add_widget(cQuestion)
        if self.q_list:
            self.q_list[0].ids.pquestion_button.text = "Back"
            self.q_list[-1].ids.nquestion_button.text = "Finish"
        sm.add_widget(EndScreen(name='End'))

        return sm

if __name__ == '__main__':
    qtlist = ["With what gender do you identify?", "What is your ethnicity?"]
    qtylist = ["(String Response Question)", "(Isolation Question)"]
    red = KemenyDemo(qtlist, qtylist).run()
