import csv
import copy
from random import randint
import random
import os.path
import math
import time
import itertools
import cProfile
import pstats, io

from courseElements import *

class GroupAssign:
    def __init__(self, student_csv, question_weights, question_types, per_group = 4,
                n_iter = 15000, combos = 10000, timelimit = 10, mode = "Strong"):


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

        self.students = []

        self.blocks = ["9L", "9S", "10", "11", "12", "2", "10A", "2A", "3A", "3B", "6A", "6B"]
        self.name_question = "What is your NETID?"

        # Stores associated questions for restrictive question types
        self.restrictive_questions = {}
        self.majority_opt = {"What gender do you identify with?":"Male", \
                            "What is your ethnicity?":"White or Caucasian"}

        self.process_students()

        if mode == "Strong":
            self.assign_strong_groups()
        else:
            self.assign_initial_groups()



#===============================================================================
#=========================== DATA PROCESSING / SETUP ===========================
#===============================================================================
    # Processes professor data CSV
    def process_prof(self):
        prof_data = self.read_csv_data(self.weighting_csv)

        if not self.questions:
            self.questions = list(prof_data[0].keys())

        self.question_weights = (prof_data[0]).copy()
        self.question_types = (prof_data[1]).copy()

        for question in self.questions:
            if self.question_types[question][0] == "R" or self.question_types[question][0] == "I":
                csplit = self.question_types[question].split(self.check_delimiter)

                self.question_types[question] = self.question_types[question][0]

                if len(csplit) == 1:
                    if self.question_types[question] == "R":
                        self.restrictive_questions[question] = ""
                        print("Unable to find associated question for restrictive question "
                            + question)
                    else:
                        self.majority_opt[question] = ""
                        print("Unable to find associated majority option for isolation question "
                            + question)
                else:
                    if self.question_types[question] == "R":
                        if csplit[1] in self.questions:
                            self.restrictive_questions[question] = csplit[1]
                        else:
                            print("Unable to find associated question for restrictive question \"" + question + "\"")
                            print("Proceeding without this question.")
                            self.questions.remove(question)
                    else:
                        self.majority_opt[question] = csplit[1]
            elif self.question_types[question] == "C" or self.question_types[question] == "Sc":
                for student in self.students:
                    student.answers[question] = student.answers[question].split(self.check_delimiter)

    # Processes student response CSV
    def process_students(self):
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

    #read_csv_data function was originally written by Mark Franklin (Thayer IT), 9/29/17
    # input: file name
    # return: list containing a dictionary for each row indexed by column headers
    def read_csv_data(self, input_csv_file):

        headers = ""
        csv_data = []

        with open(input_csv_file, 'rU') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',', quotechar='|')
            for row in csv_reader:    # headers row is a special case
                if headers == "":
                    headers = row
                else:
                    row_data = {}
                    i = 0  # used to iterate through the columns
                    for item in row:  # stash each row element
                        #print(str(headers[i]) + "i = " + str(i))
                        row_data[headers[i]] = item  # keyed by column header
                        i = i + 1

                    csv_data.append(row_data)  # save this row in the list
        return(csv_data)


#===============================================================================
#========================== Assignment Initialization ==========================
#===============================================================================

    # Assigns each student to a random group to begin
    def assign_initial_groups(self):
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

            group.number = int(i/self.per_group)
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

        for group in self.class_state.groups:
            group.score = self.score_group(group)

        self.initialized = True

    # Assigns each group in an optimal fashion
    # Ie, selects most optimal combo, then most optimal of remaining students, etc.
    def assign_strong_groups(self):
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

            # To avoid listifying - should we maybe just shuffle students and pull first (combinationlimit) from iterator?
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
            sum += group.score

        #print("Average score: " + str(sum/len(self.class_state.groups)))


        self.initialized = True

        return sum/len(self.class_state.groups)

    # Adds remainder students to groups
    def strong_remainder(self, students):
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

    def get_potentials(self, students, per_group):
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

    # Returns a score for the provided group
    def score_group(self, group):
        scores = 0

        for question in self.questions:
            # Scoring multiple choice question type
            if self.question_types[question] == "(Multiple Choice Question)":
                scores += self.score_m(group, question)

            # Scheduling question scoring mode
            elif self.question_types[question] == "(Scheduling Question)":
                scores += self.score_scheduling(group, question)

            # Scoring for checkbox style questions
            elif self.question_types[question] == "(Checkbox Question)":
                scores += self.score_c(group, question)

            # Scoring for restrictive style questions
            elif self.question_types[question] == "(Restrictive Question)":
                scores += self.get_restrictive_penalty(group, question)

            elif self.question_types[question] == "(Isolation Question)":
                scores += self.get_isolation_penalty(group, question)

        return scores

    # Scores scheduling element of groups for use in calculating final group score
    def score_scheduling(self, group, question):

        # out of 12 blocks, maximum free (assuming all students take 3 classes)
        # is 8 since 9L and 9S overlap
        max_scheduling = len(self.blocks) - 4

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
        #Allows us to limit how much open time is needed (ie, 40 hours/week or 2)
        if scheduling>max_scheduling:
            scheduling = max_scheduling

        return int(self.question_weights[question])*(scheduling/max_scheduling)

    # Multiple choice question style
    # Scores heterogeneity via number of unique answers
    def score_m(self, group, question):
        sum_values = 0
        selected_choices = {}

        # Sets all selected answers in the group to 1
        for student in group.students:
            selected_choices[student.answers[question]] = 1

        #
        for value in selected_choices.values():
            if value == 1:
                sum_values += 1

        return (sum_values/group.size) * int(self.question_weights[question])

    # Scores checkbox style questions
    def score_c(self, group, question):
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
        #print("SS: " + str((1/(n_options*n_total_responses))*squared_sum))
        res = max(0, 1 - (1/(n_options*n_total_responses))*squared_sum)

        return res*int(self.question_weights[question])

    # Implements penalties for restrictive question types
    def get_restrictive_penalty(self, group, question):
        student_choices = set()
        penalty = 0
        for student in group.students:
            for choice in student.answers[question].split(self.check_delimiter):
                student_choices.add(choice)

        associated_question = self.restrictive_questions[question]
        for student in group.students:
            for item in student.answers[associated_question].split(self.check_delimiter):
                if item in student_choices:
                    penalty -= int(self.question_weights[question])

        return penalty

    # Implements penalties for students isolated by non-majority status
    def get_isolation_penalty(self, group, question):
        iso_counter = 0

        for student in group.students:
            if student.answers[question] != self.majority_opt[question]:
                iso_counter += 1
        if iso_counter == 1:
            return -int(self.question_weights[question])
        elif len(group.students) > 4 and iso_counter == 2:
            return -int(self.question_weights[question])/3
        else:
            return 0

    # Scores a class state by averaging the scores of each group in the state
    def score_class_state(self):
        sum_scores = 0
        num_groups = len(self.class_state.groups)
        for group in self.class_state.groups:
            gscore = self.score_group(group)
            group.score = gscore
            #print("Group " + str(group.number) + " score: " + str(gscore))
            sum_scores += gscore
        return (sum_scores/num_groups)

    # Displays groups, scores, and students in each group
    # Input is a full class state and an output type - p, c, b, or u (Print/CSV/Both/User-defined)
    def output_state(self, output_type):
        if output_type == 'u':
            output_type = input("Please indicate the type of output you would like (C for CSV, P for Print, B for both)")
        output_type = output_type.lower()


        if output_type == 'c' or output_type == 'b':
            output_filename = input("Please enter a filename for the output: ")

            #Verifies that the file doesn't exist - if it does, verifies that the user would like to overwrite
            if os.path.isfile(output_filename):
                overwrite = input("This file already exists. Would you like to overwrite? (y/n) ")
                if not(overwrite == 'y' or overwrite == 'Y'):
                    while os.path.isfile(output_filename):
                        output_filename = input("Please enter a filename for the output: ")
            with open(output_filename, 'w') as output_file:
                for group in self.class_state.groups:
                    for student in group.students:
                        output_file.write(student.name + ", " + str(group.number))
                        #for question in self.questions:
                            #output_file.write(", " + student.answers[question])
                        output_file.write("\n")

            #Writes each group on a line in the new file
            #for group in self.class_state.groups:
            #    output_file.write(group.students[0].name)
            #    for student in group.students[1:]:
            #        output_file.write(", " + student.name)
            #    output_file.write("\n")

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


#===============================================================================
#=============================== Group Assignment ==============================
#===============================================================================
    # Repeatedly runs iterate_normal up to a time limit
    def anytime_run(self, timelimit=0, iterations=0):
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

    # Swaps two random groups
    # Accepts a number of iterations to perform
    # returns 1 and new state if score improves, 0 and old state else.
    def iterate_normal(self, iterations=0, visible=False):
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
            #self.epsilon = max(-.00000005*math.pow((i-3000),2) + .15, 0)
            scoresum = 0
            for group in self.class_state.groups:
                scoresum += group.score
            if scoresum/len(self.class_state.groups) > ms:
                ms = scoresum/len(self.class_state.groups)
            if i%5500 == 0:
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
                # This means that for the next run (last chance to improve)
                # we give it a chance and compare 1000 iterations back for improvement
                # instead of the typical 500
                if not conv_1:
                    prev_score = scoresum

            self.swap_students_limited(self.class_state.groups)


        # Scores and prints the final class state
        end_score = self.score_class_state()
        return end_score

    # Selects two random indices in the range 0 to max_num, inclusive
    def get_rand_index(self, max_num):
        rand_indices = random.sample(list(range(max_num+1)), 2)
        return (rand_indices[0], rand_indices[1])

    # swaps students between limited groups. Takes class state and list of groups which are ok to swap.
    def swap_students_limited(self, swappable_groups):
        swap_size = len(swappable_groups)
        #(rand_group_one, rand_group_two) = self.get_rand_index(swap_size - 1)
        #g1 = swappable_groups[rand_group_one]
        #g2 = swappable_groups[rand_group_two]
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
        #if self.epsilon < 0: self.epsilon = 0
        if random.random() > self.epsilon: # Greedy search

            #group_one = copy.deepcopy(g1)
            #group_two = copy.deepcopy(g2)
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

            return 1

    # Swaps student i from group one with student j from group two
    def swap(self, group_one, i, group_two, j):
        i.group = group_two.number
        j.group = group_one.number

        group_one.students.append(j)
        group_two.students.append(i)

        group_one.students.remove(i)
        group_two.students.remove(j)
