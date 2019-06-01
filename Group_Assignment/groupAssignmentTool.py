# Group Assignment Tool, version 5.1
# Built by Chris Miller '20
# This file customized for use with a demo program

import os.path
import csv
import copy
import random
import math
import time
import itertools
from typing import *

from courseElements import *

class GroupAssign:
    '''
    Class which allows group assignment operations performed on student data

    Attributes: (We list only important attributes)
        class_state: Stores class state which holds group and student objects
        questions: Stores list of questions to use when scoring groups
        question_weights: Dict of question weights
        question_types: Dict of question types

    '''
    def __init__(self, student_csv: str, question_weights: Dict[str,float],
                question_types: Dict[str,str],
                question_opts: Optional[Dict[str,List[str]]] = None,
                per_group: Optional[int] = 4, n_iter: Optional[int] = 15000,
                combos: Optional[int] = 10000, timelimit: Optional[int] = 10,
                mode: Optional[str] = "Strong", select_size: Optional[int] = 0,
                optimal_comp: Optional[bool] = False):
        '''
        Initialization for the GroupAssign object

        Args:
            student_csv: CSV file of student responses, with questions as headers
            question_weights: Dictionary linking questions to their weights
            question_types: Dictionary linking questions to their types
            question_opts: Dictionary linking questions to a list of possible responses
            per_group: Number of students to assign to each group
            n_iter: Number of swap attempts to perform by default when calling iterate_normal()
            combos: Number of student combinations to sample for strong initializations
            timelimit: Number of seconds to run anytime_run() for
            mode: Initialization style, "Strong" or "Random"
            select_size: Number of students to clip class size to (Used for demo only)
            optimal_comp: Whether or not to generate data with known optimal groups for comparison (Demo only)
        '''
        self.student_csv = student_csv
        self.check_delimiter = ";" # delimiter for checkbox questions
        self.per_group = per_group

        self.n_iter = n_iter
        self.initial_ep = 0.05
        self.epsilon = self.initial_ep
        self.epsilon_b = .25
        self.conv_thresh = .001
        self.discount = 1
        self.discount = math.pow(.001/self.epsilon, 1/(self.n_iter))

        # How long to run anytime_run() for until exiting
        self.timelimit = timelimit

        # How many combinations to run in assign_strong_groups()
        self.combinationlimit = combos

        self.class_state = full_state()
        self.questions = list(question_weights.keys())
        self.question_weights = question_weights
        self.question_types = question_types
        self.question_opts = question_opts
        self.students = []
        self.optimal_groups = []

        self.blocks = ["9L", "9S", "10", "11", "12", "2", "10A", "2A", "3A", "3B", "6A", "6B"]
        for question in self.questions:
            if self.question_types[question] == "(Identification Question)":
                self.name_question = question

        assert (self.name_question), "No identification question provided in questions!"

        # Stores associated questions for restrictive question types
        self.restrictive_questions = {}

        # Stores associated majority options for isolation question types
        # Only hardcoded for demo purposes
        self.majority_opt = {"What gender do you identify with?":"Male", \
                            "What is your ethnicity?":"White or Caucasian"}
        if optimal_comp:
            self.opt_score = self.gen_opt_groups(select_size)
        else:
            self.opt_score = 0
            self.process_students()
            if select_size > 0: # Clip class size. For demo purposes only
                self.students  = self.students[0:select_size]

        if mode == "Strong":
            self.assign_strong_groups()
        else:
            self.assign_initial_groups()

#===============================================================================
#=========================== DATA PROCESSING / SETUP ===========================
#===============================================================================

    def process_students(self):
        '''
        Processes student response CSV, builds list of students,
        sets each student's name and response dictionary
        Args:
            None
        Returns:
            None
        Raises:
            ValueError: If a question in the question list is not found in student CSV
        '''
        response_data = self.read_csv_data(self.student_csv)

        # Validate that all questions in the master question list are present
        student_qlist = set(response_data[0].keys())
        for question in self.questions:
            if question not in student_qlist:
                print(student_qlist)
                raise ValueError("Provided question \"{}\" not found in student data CSV.".format(question))

        #Creates an empty student object for each student
        self.students = [Student() for i in range(len(response_data))]
        counter = 0

        #Populates list of students
        for student in self.students:
            student.name = (response_data[counter])[self.name_question]
            student.answers = response_data[counter]
            counter += 1

    def read_csv_data(self, input_csv_file: str) -> List[Dict[str,str]]:
        '''
        Reads a CSV file and returns a list of dictionaries indexed by column headers
        read_csv_data function was originally written by Mark Franklin (Thayer IT), 9/29/17
        Args:
            input_csv_file: str, filename for data CSV
        Returns:
            List[Dict[str,str]], a list of dictionaries (one per row) indexed by column header
        Raises:
            AssertionError: CSV File does not exist
        '''
        headers = ""
        csv_data = []
        assert (os.path.isfile(input_csv_file)), "Input CSV file \"" + \
                                            str(input_csv_file) + "\" not found."

        with open(input_csv_file, 'rU') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',', quotechar='|')
            for row in csv_reader:    # headers row is a special case
                if headers == "":
                    headers = row
                else:
                    row_data = {}
                    i = 0  # used to iterate through the columns
                    for item in row:  # stash each row element
                        row_data[headers[i]] = item  # keyed by column header
                        i = i + 1

                    csv_data.append(row_data)  # save this row in the list
        return(csv_data)

#===============================================================================
#========================== Assignment Initialization ==========================
#===============================================================================

    def assign_initial_groups(self):
        '''
        Assigns students to random groups
        Args:
            None
        Returns:
            float, average group score after initialization
        '''
        per_group = self.per_group
        num_students = len(self.students)
        num_groups = int(num_students/self.per_group) # number of full groups we can make
        remainder = num_students%self.per_group

        self.class_state.groups = [Group() for i in range(num_groups)]

        i = 0

        # Gets a randomly shuffled copy of the student list for random group assignment
        rand_students = random.sample(self.students, len(self.students))
        n = 0
        for group in self.class_state.groups:

            group.number = int(i/self.per_group) + 1
            group.size = per_group
            group.students = rand_students[i:(i+self.per_group)]
            i += self.per_group
            n+=1


        # if remainder is within one person of the desired group size,
        # makes the remainders into a group otherwise, adds remainder to other
        # groups
        if remainder:
            if remainder + 1 == per_group and remainder != 1 and per_group>=3:
                new_group = Group()
                new_group.size = remainder
                new_group.students = rand_students[i:]
                new_group.number = num_groups
                self.class_state.groups.append(new_group)


            #distributes remainder across other groups
            else:
                j = 0
                while remainder:
                    self.class_state.groups[j].students.append(rand_students[i])
                    self.class_state.groups[j].size += 1
                    i+=1
                    j+=1
                    remainder -= 1
                    if (j == len(self.class_state.groups)):
                        j = 0

        self.initialized = True

        return self.score_class_state()

    def assign_strong_groups(self):
        '''
        Assigns each group in an iteratively optimal fashion - i.e., selects
        most optimal combo, then most optimal of remaining students, etc.

        Args:
            None
        Returns:
            float, average group score after initialization
        '''
        self.epsilon = 0
        self.initial_ep = 0

        per_group = self.per_group
        num_students = len(self.students)
        num_groups = int(num_students/self.per_group) # number of full groups we can make
        remainder = num_students%self.per_group
        students = copy.copy(self.students)

        self.class_state.groups = [Group() for i in range(num_groups)]

        scores = {}

        s = time.time()
        for group_num in range(num_groups):
            max_group = None
            max_score = float('-inf')
            if len(students) < per_group:
                per_group = len(students)

            potentials = self.get_potentials(students, per_group)

            for potential in potentials:
                hash = []
                for student in potential:
                    hash.append(student.name)
                hash = sorted(hash)
                hashstring = str(hash)

                if hashstring in scores.keys(): # We've scored this before
                    cscore = scores[hashstring]
                else:
                    temp_group = self.class_state.groups[group_num]
                    temp_group.students = list(potential)
                    temp_group.size = len(potential)
                    cscore = self.score_group(temp_group)
                    scores[hashstring] = cscore

                if cscore > max_score:
                    max_score = cscore
                    max_group = potential

            self.class_state.groups[group_num].students = list(max_group)
            self.class_state.groups[group_num].size = len(max_group)
            self.class_state.groups[group_num].number = group_num + 1
            self.class_state.groups[group_num].score = max_score

            for student in max_group: # Clear assigned students
                students.remove(student)

        if remainder:
            self.strong_remainder(students)

        e = time.time()

        sum = 0
        for group in self.class_state.groups:
            group.score = self.score_group(group)
            sum += group.score

        self.initialized = True

        return sum/len(self.class_state.groups)

    def strong_remainder(self, students: List[Student]):
        '''
        Adds students who do not divide evenly into groups to groups
        Args:
            students: List[Student], list of remaining students
        Returns:
            None
        '''
        n_groups = len(self.class_state.groups)
        self.per_group += 1
        # Fixes edge case of small number of groups and large remainder
        if n_groups < len(students):
            init_per_group = self.per_group - 1
            while ((self.per_group-init_per_group)*n_groups < len(students)):
                self.per_group += 1

        for student in students:
            max_improve = float('-inf')
            max_improve_group = None
            for group in self.class_state.groups:
                # don't want to go more than one over
                if len(group.students) < self.per_group:
                    init_score = group.score
                    group.students.append(student)
                    fin_score = self.score_group(group)
                    score_delta = (fin_score - init_score)

                    if score_delta > max_improve:
                        max_improve = score_delta
                        max_improve_group = group

                    group.students.remove(student)
            max_improve_group.students.append(student)
            max_improve_group.score = max_improve_group.score + max_improve

    def get_potentials(self, students: List[Student], per_group: int) -> Iterator[Tuple[Student]]:
        '''
        Gets group score for checkbox questions
        Args:
            students: List[Student], list of students to generate combinations from
            per_group: int, number of students to include in each combination
        Returns:
            Iterator[Tuple[Student]], an iterator of unique student combinations
        '''

        students = random.sample(students, len(students))
        potentials = itertools.combinations(students, per_group)

        # If there are too many combos, randomly sample
        if (math.factorial(len(students))/(math.factorial(per_group)*
            math.factorial(len(students) - per_group)) > self.combinationlimit):
            potentials = itertools.islice(potentials, self.combinationlimit)

        return potentials


#===============================================================================
#=================================== Scoring ===================================
#===============================================================================

    def score_group(self, group: Group):
        '''
        Gets group score
        Args:
            group: Group, the group to score
        Returns:
            float, score for group
        '''
        scores = 0

        for question in self.questions:
            # Scoring multiple choice question type
            if self.question_types[question] == "(Multiple Choice Question)":
                sm = self.score_m(group, question)
                scores += sm

            # Scheduling question scoring mode
            elif self.question_types[question] == "(Scheduling Question)":
                sm = self.score_scheduling(group, question)
                scores += sm

            # Scoring for checkbox style questions
            elif self.question_types[question] == "(Checkbox Question)":
                sm = self.score_c(group, question)
                scores += sm

            # Scoring for restrictive style questions
            elif self.question_types[question] == "(Restrictive Question)":
                sm = self.get_restrictive_penalty(group, question)
                scores += sm

            elif self.question_types[question] == "(Isolation Question)":
                sm = self.get_isolation_penalty(group, question)
                scores += sm
        return scores

    def score_scheduling(self, group: Group, question: str) -> float:
        '''
        Gets group score for scheduling questions
        Args:
            group: Group, the group to score
            question: str, the question to reference when scoring
        Returns:
            float, score for group with regard to question
        '''
        max_scheduling = len(self.blocks)

        #Lists all scheduling blocks
        scheduling_blocks = set(self.blocks.copy())

        for student in group.students:
            #Goes though every student's classes and removes them from the list
            #since those blocks are unavailable now
            for block in student.answers[question]:
                if block in scheduling_blocks:
                    scheduling_blocks.remove(block)

        #scheduling is now the remaining number of blocks that all members have free
        scheduling = len(scheduling_blocks)

        if scheduling>max_scheduling:
            scheduling = max_scheduling

        return abs(self.question_weights[question])*(scheduling/max_scheduling)

    def score_m(self, group: Group, question: str) -> float:
        '''
        Gets group score for multiple choice questions
        Args:
            group: Group, the group to score
            question: str, the question to reference when scoring
        Returns:
            float, score for group with regard to question
        '''
        sum_values = 0
        selected_choices = {}

        # Sets all selected answers in the group to 1
        for student in group.students:
            selected_choices[student.answers[question]] = 1

        #
        for value in selected_choices.values():
            if value == 1:
                sum_values += 1

        return (sum_values/group.size) * self.question_weights[question]

    def score_c(self, group: Group, question: str) -> float:
        '''
        Gets group score for checkbox questions
        Args:
            group: Group, the group to score
            question: str, the question to reference when scoring
        Returns:
            float, score for group with regard to question
        '''

        responses_set = {}
        n_total_responses = 0

        for student in group.students:
            for selection in student.answers[question]:
                if selection not in responses_set.keys():
                    responses_set[selection] = 1
                else:
                    responses_set[selection] += 1
                n_total_responses += 1
        squared_sum = 0
        for response_count in responses_set.values():
            if response_count > 1: # We're only interested if more than one person selected it
                squared_sum += response_count*response_count

        n_options = len(responses_set.keys())
        res = max(0, 1 - (1/(n_options*n_total_responses))*squared_sum)

        return res*self.question_weights[question]

    def get_restrictive_penalty(self, group: Group, question: str) -> float:
        '''
        Implements penalties for restrictive questions
        Args:
            group: Group, the group to score
            question: str, the question to reference when scoring
        Returns:
            float, restrictive penalty value
        '''
        student_choices = set()
        penalty = 0
        for student in group.students:
            for choice in student.answers[question].split(self.check_delimiter):
                student_choices.add(choice)

        associated_question = self.restrictive_questions[question]
        for student in group.students:
            for item in student.answers[associated_question].split(self.check_delimiter):
                if item in student_choices:
                    penalty -= self.question_weights[question]

        return penalty

    def get_isolation_penalty(self, group: Group, question: str) -> float:
        '''
        Implements penalties for students isolated by non-majority status
        Args:
            group: Group, the group to score
            question: str, the question to reference when scoring
        Returns:
            float, isolation penalty value
        '''

        iso_counter = 0

        for student in group.students:
            if student.answers[question] != self.majority_opt[question]:
                iso_counter += 1
        if iso_counter == 1:
            return -self.question_weights[question]
        elif len(group.students) > 4 and iso_counter == 2:
            return -self.question_weights[question]/3
        else:
            return 0

    def score_class_state(self):
        '''
        Scores a class state by averaging the scores of each group in the state
        Args:
            None
        Returns:
            float, average group score in the class state
        '''
        sum_scores = 0
        num_groups = len(self.class_state.groups)
        for group in self.class_state.groups:
            gscore = self.score_group(group)
            sum_scores += gscore
        return (sum_scores/num_groups)

#===============================================================================
#=============================== Group Assignment ==============================
#===============================================================================

    def anytime_run(self, timelimit: Optional[int] = 0, iterations: Optional[int] = 0) -> float:
        '''
        Repeatedly calls iterate_normal up to a time limit
        Args:
            timelimit: Optional int, number of seconds to run for before returning
            iterations: Optional int, number of iterations to supply to iterate_normal()
        Returns:
            Best class score found
        '''
        if iterations == 0:
            iterations = self.n_iter
        if timelimit == 0:
            timelimit = self.timelimit

        stime = time.time()
        mscore = float('-inf')
        mstate = None
        sumtime = 0
        avgtime = 0
        nruns = 0
        ctime = time.time()
        while ((ctime - stime) < timelimit - avgtime):
            self.epsilon = self.initial_ep # reset epsilon
            self.assign_initial_groups()
            cscore = self.iterate_normal(iterations=iterations, visible = False)

            if cscore > mscore:
                mstate = copy.deepcopy(self.class_state)
                mscore = cscore

            ctime = time.time()
            nruns += 1
            sumtime = ctime - stime
            avgtime = sumtime / nruns

        self.class_state = mstate
        return mscore

    def iterate_normal(self, iterations: Optional[int] = 0, visible: Optional[bool] = False) -> float:
        '''
        Handles swapping and convergence detection
        Args:
            iterations: Optional int, number of swap attempts to make
            visible: Optional boolean, reports progress if true
        Returns:
            Final class score
        '''
        if not self.initialized:
            if self.default_init_mode == "Strong":
                self.assign_strong_groups()
            else:
                self.assign_initial_groups()
        if(iterations == 0):
            iterations = self.n_iter

        failure = 0
        prev_score = 0
        conv_1 = False
        ms=float('-inf')
        for i in range(iterations):
            scoresum = 0
            for group in self.class_state.groups:
                scoresum += group.score
            if scoresum/len(self.class_state.groups) > ms:
                ms = scoresum/len(self.class_state.groups)
            if i%500 == 0:
                if visible:
                    print("At iteration " + str(i))
                    print(str(scoresum/len(self.class_state.groups)))

                if prev_score != 0 and \
                        (scoresum - prev_score)/abs(prev_score) < self.conv_thresh:
                    if conv_1: # Ensures that convergence is stable for at least two 500 rounds
                        if visible:
                            print("Score converged.")
                        break
                    else:
                        conv_1 = True
                elif conv_1: # if it escaped convergence, reset flag
                    conv_1 = False

                if not conv_1:
                    prev_score = scoresum

            self.swap_students_limited(self.class_state.groups)


        # Scores and prints the final class state
        end_score = self.score_class_state()
        return end_score

    def get_rand_index(self, max_num: int) -> Tuple[int, int]:
        '''
        Gets indices of two random groups in the range 0 to max_num inclusive
        Args:
            max_num: Maximum boundary of the range to generate indices from
        Returns:
            Tuple of length 2 containing two distinct random values from [0, max_num]
        Raises:
            ValueError: If max_num less than 1
        '''
        return random.sample(list(range(max_num+1)), 2)

    def swap_students_limited(self, swappable_groups: List[Group]):
        '''
        Swaps students between two groups in list of groups provided using
        epsilon-greedy swap strategy
        Args:
            swappable_groups: List[Group], list of groups to swap between
        Returns:
            1: Successful swap
            0: Unsuccessful swap or random swap
        Raises:
            ValueError: If less than 3 groups are in swappable_groups
        '''
        swap_size = len(swappable_groups)
        if swap_size < 3:
            raise ValueError('Too few groups provided to swap_students_limited (minimum 3).')

        g1 = None
        g2 = None
        avoid = None
        if random.random() > self.epsilon_b:
            min_group_score = float('inf')
            max_group_score = float('-inf')
            for group in swappable_groups:
                if group.score < min_group_score:
                    min_group_score = group.score
                    g1 = group
                if group.score > max_group_score:
                    max_group_score = group.score
                    avoid = group
            if len(swappable_groups) < 3:
                avoid = None
        else:
            g1 = random.choice(swappable_groups)

        g2 = g1
        while g2 == g1 or g2 == avoid:
            g2 = random.choice(swappable_groups)

        self.epsilon *= self.discount
        if random.random() > self.epsilon: # Greedy search
            group_one = g1
            group_two = g2
            total_score = group_one.score + group_two.score

            best_from_one = None
            best_from_two = None
            best_g1 = group_one.score
            best_g2 = group_two.score
            best_score = total_score

            # For each student pairing, swap, test, and swap back
            for i in group_one.students:
                for j in group_two.students:
                    self.swap(group_one, i, group_two, j)
                    g1_score = self.score_group(group_one)
                    g2_score = self.score_group(group_two)
                    candidate_score = (g1_score + g2_score)
                    self.swap(group_one, j, group_two, i)

                    if candidate_score > best_score: # Improvement
                        best_from_one = i
                        best_from_two = j
                        best_g1 = g1_score
                        best_g2 = g2_score
                        best_score = candidate_score

            if best_from_one is not None: # Do the permanent swap, this is the best
                self.swap(group_one, best_from_one, group_two, best_from_two)
                group_one.score = best_g1
                group_two.score = best_g2

                return 1

            else:
                return 0

        else: # Random swap
            s1 = random.choice(g1.students)
            s2 = random.choice(g2.students)
            self.swap(g1, s1, g2, s2)
            g1.score = self.score_group(g1)
            g2.score = self.score_group(g2)

            return 0

    def swap(self, group_one: Group, student_one: Student, group_two: Group, student_two: Student):
        '''
        Swaps two students between groups
        Args:
            group_one: Group, the first group to swap from
            student_one: Student, the student to move from the first group
            group_two: Group, the second group to swap from
            student_two: Student, the student to move from the second group
        Returns:
            None
        Raises:
            ValueError: If either student is not present in the group
        '''
        if student_one not in group_one.students or student_two not in group_two.students:
            raise ValueError('Swapped student not present.')

        student_one.group = group_two.number
        student_two.group = group_one.number

        group_one.students.append(student_two)
        group_two.students.append(student_one)

        group_one.students.remove(student_one)
        group_two.students.remove(student_two)

#===============================================================================
#============================== Output & Comparison ============================
#===============================================================================

    def output_state(self, output_type: str, output_filename: Optional[str] = None):
        '''
        Outputs groups, scores, and students in each group
        Args:
            output_type: str, p, c, b, or u (Print/CSV/Both/User-defined)
            output_filename: str, if not included, will prompt user for output filename
        Returns:
            None
        '''

        if output_type == 'u':
            output_type = input("Please indicate the type of output you would like (C for CSV, P for Print, B for both)")
        output_type = output_type.lower()


        if output_type == 'c' or output_type == 'b':
            if not output_filename:
                output_filename = input("Please enter a filename for the output: ")

            # Verification of overwrite is done on the UI side
            with open(output_filename, 'w') as output_file:
                output_file.write("Group Number")
                for question in self.questions:
                    output_file.write("," + question)
                output_file.write("\n")
                for group in self.class_state.groups:
                    for student in group.students:
                        output_file.write(str(group.number))
                        for question in self.questions:
                            to_write = student.answers[question]
                            if to_write.__class__.__name__ == 'list' and to_write:
                                to_write = str(to_write[0])
                                for ans in student.answers[question][1:]:
                                    to_write += self.check_delimiter + str(ans)
                            output_file.write("," + str(to_write))
                        output_file.write("\n")


        if output_type == 'p' or output_type == 'b':
            for group in self.class_state.groups:
                print("-----------------------------")
                print("Group number: " + str(group.number))
                print("Group score: " + str(group.score))
                print("Group members:")
                for student in group.students:
                    print(student.name)
        if output_type not in ['c', 'p', 'b']:
            print("Invalid output type.")
            self.output_state('u')

    def gen_opt_groups(self, select_size: int):
        '''
        Generates data such that optimal groups are known
        Args:
            select_size: int, number of students to generate
        Returns:
            Class score of optimal groups
        Raises:
            ValueError: If select_size less than group size
        '''
        if select_size < self.per_group:
            raise ValueError('select_size must be greater than group size.')
        for g in range(select_size//self.per_group):
            nG = Group()
            nG.number = g + 1
            nG.size = self.per_group
            nG.students = []
            for s in range(nG.size):
                nS = Student()
                nS.name = str(g*self.per_group + s + 1)
                nS.answers = {}
                nS.answers[self.name_question] = nS.name
                nG.students.append(nS)
                self.students.append(nS)
            self.optimal_groups.append(nG)

        # Shuffles student list so that initialization starts from a random list
        # for valid comparison
        random.shuffle(self.students)

        scoresum = 0
        for group in self.optimal_groups:
            for question in self.questions:
                opts = None
                blocks = None
                choice = None

                if self.question_types[question] in ["(Checkbox Question)", "(Multiple Choice Question)"]:
                    if self.question_weights[question] > 0: # Heterogenous
                        for student in group.students:
                            if not opts:
                                opts = list(range(len(self.question_opts[question])))
                                random.shuffle(opts)
                            ch = opts.pop()
                            student.answers[question] = self.question_opts[question][ch]
                            if self.question_types[question] == "(Checkbox Question)":
                                student.answers[question] = [student.answers[question]]
                    else: # Homogeneous
                        choice = random.choice(self.question_opts[question])
                        for student in group.students:
                            student.answers[question] = choice
                            if self.question_types[question] == "(Checkbox Question)":
                                student.answers[question] = [student.answers[question]]

                elif self.question_types[question] == "(Isolation Question)":
                    nMin = random.choice([math.ceil(self.per_group/2), 0])
                    majopt = self.majority_opt[question]
                    minopts = self.question_opts[question].copy()
                    if majopt in minopts:
                        minopts.remove(majopt)
                    for i, student in enumerate(group.students):
                        if i < nMin:
                            choice = random.choice(minopts)
                        else:
                            choice = majopt
                        student.answers[question] = choice

                elif self.question_types[question] == "(Scheduling Question)":
                    blocks = random.sample(self.blocks, 3)
                    for student in group.students:
                        student.answers[question] = blocks

            group.score = self.score_group(group)
            scoresum += group.score

        return scoresum / len(self.optimal_groups)
