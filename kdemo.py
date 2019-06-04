
# Authored by Chris Miller '20
# Provides a GUI demo of the Group Assignment Tool
# For submission to the Kemeny Prize

from Group_Assignment.groupAssignmentTool import GroupAssign
import csv
import os
from typing import *

import kivy

from kivy.app import App
from kivy.core.window import Window
from kivy.clock import Clock

from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.floatlayout import FloatLayout

from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.slider import Slider
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.uix.popup import Popup


class Question(Screen):
    '''
    Generic screen for any question
    Attributes:
        distrib_active: True if users can modify distribution type
        opts: Potential repsonses for the question
    '''
    def __init__(self, q_text: str, q_type: str, q_opts: List[str], num: int, **kwargs):
        super(Question, self).__init__(**kwargs)
        self.distrib_active = True

        self.ids.text_label.text = q_text
        self.ids.type_label.text = q_type
        self.opts = q_opts

        self.ids.activate_toggle.group = 'activation_group_' + str(num)
        self.ids.deactivate_toggle.group = 'activation_group_' + str(num)

        self.parse_type(q_type)

    def activate_callback(self, val: bool):
        '''
        Activates/deactivates fields depending on whether or not the question is active
        Args:
            val: True if a question is disabled, false else
        '''
        if self.distrib_active:
            self.ids.distrib_spinner.disabled = val
        self.ids.weight_slider.disabled = val

    def parse_type(self, q_type: str):
        '''
        Sets default distribution and determines what users are allowed to modify
        Args:
            q_type: Question type, which takes on one of the following values
                (Identification Question)
                (Multiple Choice Question)
                (Checkbox Question)
                (Isolation Question)
                (Scheduling Question)
                (Restrictive Question)
        '''
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

class ParamScreen(Screen):
    '''
    Allows users to set various GroupAssign parameters
    '''
    def __init__(self, **kwargs):
        super(ParamScreen, self).__init__(**kwargs)


    def init_type_callback(self, val: bool):
        '''
        Sets various fields inactive or active depending on initialization type
        Args:
            val: True if user requests strong initializations, false otherwise
        '''
        self.ids.time_limit_input.disabled = val
        self.ids.combination_input.disabled = not val

    def call_process(self):
        '''
        Schedules dataset processing, with half second delay for screen transition
        '''
        Clock.schedule_once((self.manager.get_screen(self.manager.current)).process_dataset, .5)

class ResultScreen(Screen):
    '''
    Screen object which displays results and allows file output

    Attributes:
        q_list: List of question screens
        param_screen: Parameter setting screen
        assigner: Holds the GroupAssign object
        dest_csv: Holds the CSV to write to
        last_overwrite: Tracks if a user wishes to overwrite an existing file

    '''
    def __init__(self, q_list: List[Question], param_screen: ParamScreen, **kwargs):
        super(ResultScreen, self).__init__(**kwargs)
        self.q_list = q_list
        self.param_screen = param_screen
        self.assigner = None
        self.dest_csv = None
        self.last_overwrite = None


    def process_dataset(self, dt: float):
        '''
        Evaluates question parameters and assignment parameters
        Creates and uses a GroupAssign object to assign groups

        Args:
            dt: seconds since call was scheduled, required by kivy clock scheduling

        '''
        param_screen = None
        param_screen = self.param_screen

        assert (param_screen), "Parameter Screen Not Found"

        if param_screen.ids.strong_toggle.state == 'down':
            mode = "Strong"
        else:
            mode = "Random"

        (q_text_list, q_opts, q_weights, q_types) = self.process_questions()

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
            result_groups += "Group " + str(group.number) + " (score {:.2f}) contains students:\n".format(group.score)
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

    def process_questions(self) -> Tuple[List[str], List[List[str]], Dict[str, float], Dict[str, str]]:
        '''
        Processes all question screens, evaluating weights and distribution types
        Args:
            None
        Returns:
            q_text_list: List of activated question texts
            q_opts: List of activated question response options
            q_weights: Dictionary of question weights, indexed by question text
            q_types: Dictionary of question types, indexed by question text
        '''
        questions = []
        q_text_list = []
        q_types = {}
        q_opts = {}
        q_weights = {}

        # Get all active questions
        for screen in self.q_list:
            if screen.ids.activate_toggle.state == 'down':
                questions.append(screen)

        for question in questions:
            q_text = question.ids.text_label.text
            q_opts[q_text] = question.opts
            q_weights[q_text] = question.ids.weight_slider.value
            q_types[q_text] = question.ids.type_label.text

            if question.ids.distrib_spinner.text == 'Homogeneous':
                q_weights[q_text] = -q_weights[q_text]

            q_text_list.append(q_text)

        return (q_text_list, q_opts, q_weights, q_types)

    def get_params(self, instance: ParamScreen, mode: str) -> Tuple[int, int, int, int, int]:
        '''
        Gets and enforces constraints on various GroupAssign parameters
        Args:
            instance: ParamScreen object which stores GroupAssign parameters
            mode: Initialization mode
        Returns:
            c_size: Class size
            per_group: Number of students per group
            n_iter: Number of swap attempts to make
            combos: Number of combinations to sample
            timelimit: Number of seconds to run for
        '''
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
        if n_iter > self.max_iter:
            n_iter = self.max_iter
            print("Iteration count greater than maximum allowed (" + str(self.max_iter) + ")")
            print("Setting iteration count to " + str(self.max_iter) + ".")
        if mode == "Strong": # Get # samples
            try:
                combos = abs(int(instance.ids.combination_input.text))
            except:
                print("Invalid combination count, using default value " + \
                        str(instance.default_combinations))
                combos = instance.default_combinations

            if combos >  self.max_combo:
                combos = self.max_combo
                print("# combination samples greater than maximum allowed (" + str(self.max_combo) + ")")
                print("Setting # samples to " + str(self.max_combo) + ".")
        else: # Get timelimit
            try:
                timelimit = abs(int(instance.ids.time_limit_input.text))
            except:
                print("Invalid time limit, using default value " + \
                        str(instance.default_timelimit))
                timelimit = instance.default_timelimit

            if timelimit > self.max_time:
                timelimit = self.max_time
                print("Time limit greater than maximum allowed (" + str(self.max_time) + ")")
                print("Setting time limit to " + str(self.max_time) + ".")

        return (c_size, per_group, n_iter, combos, timelimit)

    def make_csv(self, finame: str):
        '''
        Generates a file with student groups
        Args:
            finame: The file to output groups to
        '''
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

class SplashScreen(Screen):
    '''
    Screen object which displays an introduction to the demo program
    Attributes:
        None
    '''
    def __init__(self, **kwargs):
        super(SplashScreen, self).__init__(**kwargs)

class KemenyDemoApp(App):
    '''
    App class for Kemeny Prize demo
    '''
    def __init__(self, q_text_list, q_type_list, q_opt_list):
        super(KemenyDemoApp, self).__init__()
        Window.size = (800,400)
        Window.clearcolor = (.259, .446, .296, 1)

        assert (len(q_text_list) == len(q_type_list)), "Fatal error: Question text list and question type list do not correspond."

        self.q_text_list = q_text_list
        self.q_type_list = q_type_list
        self.q_opt_list = q_opt_list

    def build(self):
        '''
        Builds screen manager object
        Returns:
            ScreenManager
        '''
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

def process_questions(finame: str) -> Tuple[List[str], List[str], List[List[str]]]:
    '''
    Gets question texts, types, and options from a csv file
    Args:
        finame: Filename to read from
    Returns:
        q_texts: List of question texts
        q_types: List of question types
        q_opts: List of lists of question response options
    Raises:
        AssertionError: File has unexpected number of rows (nrows != 3)
        AssertionError: Lengths of all rows are not equal
    '''
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
    (q_text_list, q_type_list, q_opt_list) = process_questions("data/qtypes.csv")
    red = KemenyDemoApp(q_text_list, q_type_list, q_opt_list).run()
