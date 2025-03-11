"""
Pyhop, version 1.2.2 -- a simple SHOP-like planner written in Python.
Author: Dana S. Nau, 2013.05.31
Modified: Jaume Jordán, February 2025
Result returns both the plan and final state.
Goals and states objects are printed human readable.
Refactored and corrected Python warnings and style.


Copyright 2013 Dana S. Nau - http://www.cs.umd.edu/~nau

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
   
Pyhop should work correctly in both Python 2.7 and Python 3.2 (but recommended >=3.6).
For examples of how to use it, see the example files that come with Pyhop.

Pyhop provides the following classes and functions:

- foo = State('foo') tells Pyhop to create an empty state object named 'foo'.
  To put variables and values into it, you should do assignments such as
  foo.var1 = val1

- bar = Goal('bar') tells Pyhop to create an empty goal object named 'bar'.
  To put variables and values into it, you should do assignments such as
  bar.var1 = val1

- print_state(foo) will print the variables and values in the state foo.

- print_goal(foo) will print the variables and values in the goal foo.

- declare_operators(o1, o2, ..., ok) tells Pyhop that o1, o2, ..., ok
  are all of the planning operators; this supersedes any previous call
  to declare_operators.

- print_operators() will print out the list of available operators.

- declare_methods('foo', m1, m2, ..., mk) tells Pyhop that m1, m2, ..., mk
  are all of the methods for tasks having 'foo' as their taskname; this
  supersedes any previous call to declare_methods('foo', ...).

- print_methods() will print out a list of all declared methods.

- pyhop(state1,tasklist) tells Pyhop to find a plan for accomplishing tasklist
  (a list of tasks), starting from an initial state state1, using whatever
  methods and operators you declared previously.

- In the above call to pyhop, you can add an optional 3rd argument called
  'verbose' that tells pyhop how much debugging printout it should provide:
- if verbose = 0 (the default), pyhop returns the solution but prints nothing;
- if verbose = 1, it prints the initial parameters and the answer;
- if verbose = 2, it also prints a message on each recursive call;
- if verbose = 3, it also prints info about what it's computing.
"""

# Pyhop's planning algorithm is very similar to the one in SHOP and JSHOP
# (see http://www.cs.umd.edu/projects/shop). Like SHOP and JSHOP, Pyhop uses
# HTN methods to decompose tasks into smaller and smaller subtasks, until it
# finds tasks that correspond directly to actions. But Pyhop differs from 
# SHOP and JSHOP in several ways that should make it easier to use Pyhop
# as part of other programs:
# 
# (1) In Pyhop, one writes methods and operators as ordinary Python functions
#     (rather than using a special-purpose language, as in SHOP and JSHOP).
# 
# (2) Instead of representing states as collections of logical assertions,
#     Pyhop uses state-variable representation: a state is a Python object
#     that contains variable bindings. For example, to define a state in
#     which box b is located in room r1, you might write something like this:
#     s = State()
#     s.loc['b'] = 'r1'
# 
# (3) You also can define goals as Python objects. For example, to specify
#     that a goal of having box b in room r2, you might write this:
#     g = Goal()
#     g.loc['b'] = 'r2'
#     Like most HTN planners, Pyhop will ignore g unless you explicitly
#     tell it what to do with g. You can do that by referring to g in
#     your methods and operators, and passing g to them as an argument.
#     In the same fashion, you could tell Pyhop to achieve any one of
#     several different goals, or to achieve them in some desired sequence.
# 
# (4) Unlike SHOP and JSHOP, Pyhop doesn't include a Horn-clause inference
#     engine for evaluating preconditions of operators and methods. So far,
#     I've seen no need for it; I've found it easier to write precondition
#     evaluations directly in Python. But I could consider adding such a
#     feature if someone convinces me that it's really necessary.
# 
# Accompanying this file are several files that give examples of how to use
# Pyhop. To run them, launch python and type "import blocks_world_examples"
# or "import simple_travel_example".


import copy


############################################################
# States and goals

def to_string(obj):
    if not obj:
        return "False"
    return " ".join(f"{obj.__name__}.{name} = {val}" for name, val in vars(obj).items() if name != '__name__')


class State:
    """A state is just a collection of variable bindings."""

    def __init__(self, name):
        self.__name__ = name

    def __str__(self):
        return to_string(self)

    def __repr__(self):
        return self.__str__()


class Goal:
    """A goal is just a collection of variable bindings."""

    def __init__(self, name):
        self.__name__ = name

    def __str__(self):
        return to_string(self)

    def __repr__(self):
        return self.__str__()


# print_state and print_goal are identical except for the name

def print_state(state, indent=4):
    """Print each variable in state, indented by indent spaces."""
    if state:
        for name, val in vars(state).items():
            if name != '__name__':
                print(' ' * indent + f"{state.__name__}.{name} = {val}")
    else:
        print('False')


def print_goal(goal, indent=4):
    """Print each variable in goal, indented by indent spaces."""
    if goal:
        for name, val in vars(goal).items():
            if name != '__name__':
                print(' ' * indent + f"{goal.__name__}.{name} = {val}")
    else:
        print('False')


############################################################
# Helper functions that may be useful in domain models

def forall(seq, cond):
    """Return True if cond(x) holds for all x in seq, otherwise False."""
    return all(cond(x) for x in seq)


def find_if(cond, seq):
    """
    Return the first element in seq such that cond(element) holds.
    If no such element is found, return None.
    """
    return next((x for x in seq if cond(x)), None)


############################################################
# Commands to tell Pyhop what the operators and methods are

operators = {}
methods = {}


def declare_operators(*op_list):
    """
    Call this after defining the operators, to tell Pyhop what they are.
    op_list must be a list of functions, not strings.
    """
    for op in op_list:
        if not callable(op):
            raise ValueError(f"Operator {op} is not callable")
        operators[op.__name__] = op
    return operators


def declare_methods(task_name, *method_list):
    """
    Call this once for each task, to tell Pyhop what the methods are.
    task_name must be a string.
    method_list must be a list of functions, not strings.
    """
    if not isinstance(task_name, str):
        raise ValueError("Task name must be a string")
    for method in method_list:
        if not callable(method):
            raise ValueError(f"Method {method} is not callable")
    methods[task_name] = list(method_list)
    return methods[task_name]


############################################################
# Commands to find out what the operators and methods are

def print_operators(olist=operators):
    """Print out a list of available operators."""
    print(f"{'OPERATORS: '}{', '.join(olist)}")


def print_methods(mlist=methods):
    """Print out a table of what the methods are for each task"""
    max_task_length = max(len(task) for task in mlist) if mlist else 4
    print(f"{'TASK':<{max_task_length}} | METHODS")
    for task in mlist:
        print(f"{task:<{max_task_length + 1}}{'| '}{', '.join(f.__name__ for f in mlist[task])}")


############################################################
# The actual planner

def pyhop(state, tasks, verbose=0):
    """
    Try to find a plan that accomplishes tasks in state. 
    If successful, return the plan. Otherwise return False.
    """
    if verbose > 0:
        print(f'\n** pyhop, verbose={verbose}: **\n   state = {state}\n   tasks = {tasks}')
    result_list = seek_plan(state, tasks, [], 0, verbose)
    if verbose > 0:
        if not result_list:
            print('** result =', result_list, '\n')
        else:
            print('** result =', result_list[0], '\n')
            print('** final state =')
            print_state(result_list[1])
            print()
    return result_list if result_list else []


def seek_plan(state, tasks, plan, depth, verbose=0):
    """
    Workhorse for pyhop. state and tasks are as in pyhop.
    - plan is the current partial plan.
    - depth is the recursion depth, for use in debugging
    - verbose is whether to print debugging messages
    """
    if verbose > 1:
        print(f'depth {depth} tasks {tasks}')
    if not tasks:
        if verbose > 2:
            print(f'depth {depth} returns plan {plan}')
        return [plan, state]
    task1 = tasks[0]
    if task1[0] in operators:
        if verbose > 2:
            print(f'depth {depth} action {task1}')
        operator = operators[task1[0]]
        newstate = operator(copy.deepcopy(state), *task1[1:])
        if verbose > 2:
            print(f'depth {depth} new state:')
            print_state(newstate)
        if newstate:
            solution_list = seek_plan(newstate, tasks[1:], plan + [task1], depth + 1, verbose)
            if solution_list:
                return solution_list
    if task1[0] in methods:
        if verbose > 2:
            print(f'depth {depth} method instance {task1}')
        relevant = methods[task1[0]]
        for method in relevant:
            subtasks = method(state, *task1[1:])
            # Can't just say "if subtasks:", because that's wrong if subtasks == []
            if verbose > 2:
                print(f'depth {depth} new tasks: {subtasks}')
            if subtasks is not False:
                solution_list = seek_plan(state, subtasks + tasks[1:], plan, depth + 1, verbose)
                if solution_list:
                    return solution_list
    if verbose > 2:
        print(f'depth {depth} returns failure')
    return False
