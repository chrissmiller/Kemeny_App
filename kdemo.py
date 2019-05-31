
# Authored by Chris Miller '20
# To provide a GUI demo of the Group Assignment Tool

from groupAssignmentTool import GroupAssign
import csv
import os

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
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup

# Basic splash screen to start
class SplashScreen(Screen):
    def __init__(self, **kwargs):
        super(SplashScreen, self).__init__(**kwargs)

# Displays results
class ResultScreen(Screen):
    def __init__(self, q_list, param_screen, **kwargs):
        super(ResultScreen, self).__init__(**kwargs)
        self.q_list = q_list
        self.param_screen = param_screen
        self.assigner = None
        self.dest_csv = None
        self.last_overwrite = None
    # Sets up and uses GroupAssign object
    def process_dataset(self, dt):
        questions = []
        param_screen = None
        # Get parameters and all active questions
        for screen in self.q_list:
            if screen.ids.activate_toggle.state == 'down':
                questions.append(screen)
        param_screen = self.param_screen

        assert (param_screen), "Parameter Screen Not Found"

        q_text_list = []
        q_types = {}
        q_opts = {}
        q_weights = {}
        if param_screen.ids.strong_toggle.state == 'down':
            mode = "Strong"
        else:
            mode = "Random"

        for question in questions:
            q_text = question.ids.text_label.text
            q_opts[q_text] = question.opts
            q_weights[q_text] = question.ids.weight_slider.value
            q_types[q_text] = question.ids.type_label.text

            if question.ids.distrib_spinner.text == 'Homogeneous':
                q_weights[q_text] = -q_weights[q_text]

            q_text_list.append(q_text)

        (c_size, per_group, n_iter, combos, timelimit) = self.get_params(param_screen, mode)

        if param_screen.ids.compare_toggle.state == 'down':
            opt_comp = True
            dataset_file = None
        else:
            opt_comp = False
            dataset_file = 'data/c6_s_117.csv'
            assert (os.path.isfile(dataset_file)), "File " + dataset_file + " not found!"

        assigner = GroupAssign(dataset_file, q_weights, q_types, question_opts = q_opts,
                            per_group = per_group, n_iter=n_iter, combos=combos,
                            timelimit=timelimit, mode = mode, select_size = c_size,
                            optimal_comp = opt_comp)

        if mode == "Strong":
            sc = assigner.iterate_normal(visible=False)
        else:
            sc = assigner.anytime_run()


        self.ids.result_label.text = "Final class score: {:.2f}".format(sc)

        result_groups = ""
        for group in assigner.class_state.groups:
            result_groups += "Group " + str(group.number) + " (score " + str(assigner.score_group(group)) + ") contains students:\n"
            for student in group.students:
                result_groups += student.name + "\n"
            result_groups += "\n"


        self.ids.result_box.text = result_groups

        if opt_comp:
            opt_text = 'Maximum Score: ' + str(assigner.opt_score) + "\n"
            noptimal = len([group for group in assigner.class_state.groups if group.score == assigner.opt_score])
            opt_text += str(noptimal) + ' of ' + (str(len(assigner.class_state.groups))) \
                        + ' groups generated achieved optimal scores.'
            self.ids.opt_label.text = opt_text
        else:
            self.ids.opt_label.text =  ''

        if self.dest_csv:
            assigner.output_state('c', self.dest_csv)

        self.assigner = assigner

    # Pulls iteration count, combination samples, and time limit
    def get_params(self, instance, mode):
        n_iter = 0
        combos = 0
        timelimit = 0

        per_group = int(instance.ids.select_per_group.text)
        c_size = per_group * int(instance.ids.select_n_groups.text)

        # Get iteration count
        try:
            n_iter = abs(int(instance.ids.iteration_input.text))
        except:
            print("Invalid iteration count, using default value " + \
                    str(instance.default_iterations))
            n_iter = instance.default_iterations

        if mode == "Strong": # Get # samples
            try:
                combos = abs(int(instance.ids.combination_input.text))
            except:
                print("Invalid combination count, using default value " + \
                        str(instance.default_combinations))
                combos = instance.default_combinations
        else: # Get timelimit
            try:
                timelimit = abs(int(instance.ids.time_limit_input.text))
            except:
                print("Invalid time limit, using default value " + \
                        str(instance.default_timelimit))
                timelimit = instance.default_timelimit

        return (c_size, per_group, n_iter, combos, timelimit)

    # Generate CSV file for students
    def make_csv(self, finame):

        if not self.last_overwrite == finame and os.path.isfile(finame):
            popup = Popup(title = "File Overwrite Warning",
                content = Label(text = "File \"" + finame + "\" already exists!" +
                "\nClick Generate again if you wish to overwrite the existing file.",
                size_hint = (.2, .2), pos_hint = {'center_x':.5, 'center_y':.5},
                halign = 'center'), size_hint = (.6, .35), pos_hint =
                {'center_x':.5, 'center_y':.5})

            popup.open()
            self.last_overwrite = finame
        else:
            if self.assigner: # Assign via existing object
                self.assigner.output_state('c', finame)
            else: # Prepare to assign
                self.dest_csv = finame

            self.last_overwrite = None

# Collects initialization parameters
class ParamScreen(Screen):
    def __init__(self, **kwargs):
        super(ParamScreen, self).__init__(**kwargs)

    # Set fields active/inactive depending on mode
    # Val is a boolean, which is true if the user requests strong initializations,
    # false otherwise
    def init_type_callback(self, val):
        self.ids.time_limit_input.disabled = val
        self.ids.combination_input.disabled = not val

    # Schedule dataset processing, with half second delay for screen transition
    def call_process(self):
        Clock.schedule_once((self.manager.get_screen(self.manager.current)).process_dataset, .5)


class OptimalScreen(Screen):
    def __init__(self, **kwargs):
        super(OptimalScreen, self).__init__(**kwargs)

class Question(Screen):
    def __init__(self, q_text, q_type, q_opts, num, **kwargs):
        super(Question, self).__init__(**kwargs)
        self.distrib_active = True

        self.ids.text_label.text = q_text
        self.ids.type_label.text = q_type
        self.opts = q_opts

        self.ids.activate_toggle.group = 'activation_group_' + str(num)
        self.ids.deactivate_toggle.group = 'activation_group_' + str(num)

        self.parse_type(q_type)

    def activate_callback(self, val):
        if self.distrib_active:
            self.ids.distrib_spinner.disabled = val
        self.ids.weight_slider.disabled = val

    # Set distribution spinner to the correct value and status
    # Types:
    # S: (Identification Question)
    # M: (Multiple Choice Question)
    # C: (Checkbox Question)
    # I: (Isolation Question)
    # Sc: (Scheduling Question)
    # R: (Restrictive Question)
    def parse_type(self, q_type):
        active_types = ["(Multiple Choice Question)", "(Checkbox Question)"]
        het_types = ["(Multiple Choice Question)", "(Isolation Question)", "(Identification Question)"]
        unweighted_types = ["(Identification Question)"]
        high_weight_types = ["(Isolation Question)"]

        # Set default distribution
        if q_type not in het_types:
            self.ids.distrib_spinner.text = 'Homogeneous'

        # Deactivate distribution spinner
        if q_type not in active_types:
            self.distrib_active = False
            self.ids.distrib_spinner.disabled = True

        # Freeze all options
        if q_type in unweighted_types:
            self.ids.activate_toggle.disabled = True
            self.ids.deactivate_toggle.disabled = True

            self.ids.weight_slider.disabled = True

        # Increase weighting
        if q_type in high_weight_types:
            self.ids.weight_slider.max *= 4
            self.ids.weight_slider.value *= 4

class KemenyDemoApp(App):
    def __init__(self, q_text_list, q_type_list, q_opt_list):
        super(KemenyDemoApp, self).__init__()
        Window.size = (800,400)
        Window.clearcolor = (.259, .446, .296, 1)

        if len(q_text_list) != len(q_type_list):
            print("Fatal error: Question text list and question type list do not correspond.")
            exit(1)

        self.q_text_list = q_text_list
        self.q_type_list = q_type_list
        self.q_opt_list = q_opt_list

    def build(self):
        sm = ScreenManager()
        q_list = []

        sm.add_widget(SplashScreen(name='Start'))
        for i,q_text in enumerate(self.q_text_list):
            cQuestion = Question(q_text, self.q_type_list[i], self.q_opt_list[i],
                                i, name = "Q" + str(i))
            q_list.append(cQuestion)
            if self.q_type_list[i] != "(Identification Question)":
                sm.add_widget(cQuestion)
        if q_list:
            q_list[0].ids.pquestion_button.text = "Back"
            q_list[-1].ids.nquestion_button.text = "Finish"

        param_screen = ParamScreen(name='Params')
        sm.add_widget(param_screen)
        sm.add_widget(ResultScreen(q_list, param_screen, name='Results'))

        return sm

# Reads question text and types
def process_questions(finame):
    valid_types = set(["(Identification Question)", "(Multiple Choice Question)", \
                    "(Checkbox Question)", "(Isolation Question)", "(Scheduling Question)",\
                    "(Restrictive Question)"])

    while not os.path.isfile(finame):
        print("Question data file \""+ str(finame) + "\" not found!")
        finame = input("Enter new filename, or hit enter to exit: ")
        if finame == "":
            exit(1)
    with open(finame, 'r') as q_data:
        linedata = q_data.readlines()

    assert (len(linedata) == 3), "Invalid question data file (" + str(finame) + ") provided to process_questions()"

    q_texts = linedata[0].strip().split(",")
    q_types = linedata[1].strip().split(",")
    q_opts = [text.split(";") for text in linedata[2].strip().split(",")]

    # Validate types
    for i,type in enumerate(q_types):
        if type not in valid_types:
            print("Question type \"" + type + "\", associated with question \""
                    + q_texts[i] + "\" is not a valid type.\nThis may produce unexpected behavior.")

    assert (len(q_texts) == len(q_types)), "Question type list from file " + \
            str(finame) + " is not the same length as question text list."
    assert (len(q_texts) == len(q_opts)), "Question option list from file " + \
            str(finame) + " is not the same length as question text list."

    return(q_texts, q_types, q_opts)

if __name__ == '__main__':
    (q_text_list, q_type_list, q_opt_list) = process_questions("qtypes.csv")
    red = KemenyDemoApp(q_text_list, q_type_list, q_opt_list).run()
