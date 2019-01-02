from random import randint
from termcolor import colored as clr


TIPS = [
    (
        "You can see all experiments "
        "(not just those that are currently running) with this command:\n\t"
        + clr("liftoff-status -a", "red", attrs=["bold"]),
        ["status"],
    ),
    (
        "You can see a narrower table of experiments with this command:\n\t "
        + clr("liftoff-status -r", "red", attrs=["bold"]),
        ["status"],
    ),
    (
        "You can resume an incomplete experiment using the "
        + clr("--resume", "red")
        + " flag in liftoff.\n"
        + "  Runs that crashed or did not even start will be (re)launched.\n"
        + "  Crashed experiments could start from a saved checkpoint.",
        ["abort", "launch"],
    ),
]


def display_tips(topic=None):
    if topic is None:
        good_tips = TIPS
    else:
        good_tips = [(msg,) for (msg, topics) in TIPS if topic in topics]
    print(clr("TIP!", "green"), good_tips[randint(0, len(good_tips) - 1)][0])
