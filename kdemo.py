
# Authored by Chris Miller '20
# To provide a GUI demo of the Group Assignment Tool

from kemeny_GAT import GroupAssign
import csv

import kivy
kivy.require('1.10.1')

from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.core.window import Window
from kivy.clock import Clock

from kivy.uix.screenmanager import ScreenManager, Screen

from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.slider import Slider
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.textinput import TextInput

# Allows easy transitions between screens
class ScreenManaging(ScreenManager):
    pass

# Basic splash screen to start
class SplashScreen(Screen):
    def __init__(self, **kwargs):
        super(SplashScreen, self).__init__(**kwargs)

# Displays results
class ResultScreen(Screen):
    def __init__(self, **kwargs):
        super(ResultScreen, self).__init__(**kwargs)

    # Sets up a GroupAssign object
    def process_dataset(self, dt):
        questions = []
        param_screen = None

        for screen in self.manager.screens:
            if screen.__class__.__name__ == "Question":
                questions.append(screen)
            elif screen.__class__.__name__ == "EndScreen":
                param_screen = screen

        assert (param_screen), "Parameter Screen Not Found"

        q_text_list = []
        q_types = {}
        q_weights = {}
        if param_screen.ids.strong_toggle.state == 'down':
            mode = "Strong"
        else:
            mode = "Random"

        per_group = 4 #add selection of this
        for question in questions:
            q_text = question.ids.text_label.text
            q_weights[q_text] = question.ids.weight_slider.value
            q_types[q_text] = question.ids.type_label.text

            q_text_list.append(q_text)

        (n_iter, combos, timelimit) = self.get_params(param_screen, mode)

        student_csv = "../GAT_Final/Testing/data/c6_s_40.csv"
        assigner = GroupAssign(student_csv, q_weights, q_types, per_group = per_group,
                                n_iter=n_iter, combos=combos, timelimit=timelimit,
                                mode = mode)
        if mode == "Strong":
            sc = assigner.iterate_normal(visible=False)
        else:
            sc = assigner.anytime_run()

        self.ids.result_label.text = "Final class score: {:.2f}".format(sc)

        result_groups = ""
        for group in assigner.class_state.groups:
            result_groups += "Group " + str(group.number) + " contains students:\n"
            for student in group.students:
                result_groups += student.name + "\n"
            result_groups += "\n"

        self.ids.result_box.text = result_groups

    # Pulls iteration count, combination samples, and time limit
    def get_params(self, instance, mode):
        n_iter = 0
        combos = 0
        timelimit = 0

        try:
            n_iter = abs(int(instance.ids.iteration_input.text))
        except:
            print("Invalid iteration count, using default value " + \
                    str(instance.default_iterations))
            n_iter = instance.default_iterations

        if mode == "Strong":
            try:
                combos = abs(int(instance.ids.combination_input.text))
            except:
                print("Invalid combination count, using default value " + \
                        str(instance.default_combinations))
                combos = instance.default_combinations
        else:
            try:
                timelimit = abs(int(instance.ids.time_limit_input.text))
            except:
                print("Invalid combination count, using default value " + \
                        str(instance.default_timelimit))
                timelimit = instance.default_timelimit
        return (n_iter, combos, timelimit)


# Implements the GAT initialization settings
class EndScreen(Screen):
    def __init__(self, **kwargs):
        super(EndScreen, self).__init__(**kwargs)

    def init_type_callback(self, val):
        # Set stuff active/inactive
        self.ids.time_limit_input.disabled = val
        self.ids.combination_input.disabled = not val

    def call_process(self):
        Clock.schedule_once((self.manager.get_screen(self.manager.current)).process_dataset, .5)

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
        self.distrib_active = True

        self.ids.text_label.text = q_text
        self.ids.type_label.text = q_type

        self.ids.activate_toggle.group = 'activation_group_' + str(num)
        self.ids.deactivate_toggle.group = 'activation_group_' + str(num)

        self.parse_type(q_type)

    def activate_callback(self, val):
        if self.distrib_active:
            self.ids.distrib_spinner.disabled = val
        self.ids.weight_slider.disabled = val

    # Set distribution spinner to the correct value and status
    def parse_type(self, q_type):
        active_types = ["(Multiple Choice Question)", "(Checkbox Question)"]
        het = ["(Multiple Choice Question)", "(Isolation Question)", "(String Response Question)"]

        if q_type not in het:
            self.ids.distrib_spinner.text = 'Homogeneous'

        if q_type not in active_types:
            self.distrib_active = False
            self.ids.distrib_spinner.disabled = True

class KemenyDemoApp(App):
    def __init__(self, q_text_list, q_type_list):
        super(KemenyDemoApp, self).__init__()
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
        sm.add_widget(ResultScreen(name='Results'))

        return sm

# Reads question text and types
def process_questions(finame):
    with open(finame, 'r') as q_data:
        linedata = q_data.readlines()

    assert (len(linedata) == 2), "Invalid question data file (" + str(finame) + ") provided to process_questions()"

    q_texts = linedata[0].strip().split(",")
    q_types = linedata[1].strip().split(",")

    assert (len(q_texts) == len(q_types)), "Question type list from file " + str(finame) + " is not the same length as question text list"

    return(q_texts, q_types)

if __name__ == '__main__':
    (q_text_list, q_type_list) = process_questions("qtypes.csv")
    red = KemenyDemoApp(q_text_list, q_type_list).run()
