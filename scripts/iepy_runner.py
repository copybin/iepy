"""
Run IEPY core loop

Usage:
    iepy_runner.py <dbname> <seeds_file> <output_file> [--gold=<gold_standard>]
    iepy_runner.py -h | --help | --version

Options:
  -h --help             Show this screen
  --version             Version number
"""
from docopt import docopt
import logging

from iepy.core import BootstrappedIEPipeline
from iepy import db
from iepy.human_validation import TerminalInterviewer
from iepy.utils import load_facts_from_csv, save_labeled_evidence_to_csv, load_evidence_from_csv


if __name__ == '__main__':
    opts = docopt(__doc__, version=0.1)
    connection = db.connect(opts['<dbname>'])
    seed_facts = load_facts_from_csv(opts['<seeds_file>'])
    output_file = opts['<output_file>']
    gold_standard_file = opts['--gold']
    if gold_standard_file:
        gold_standard = load_evidence_from_csv(gold_standard_file, connection)
    else:
        gold_standard = None

    p = BootstrappedIEPipeline(connection, seed_facts, gold_standard)

    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    STOP = 'STOP'

    p.start()  # blocking
    keep_looping = True
    while keep_looping:
        qs = list(p.questions_available())
        if not qs:
            keep_looping = False
        term = TerminalInterviewer(qs, p.add_answer, [(STOP, 'Stop execution ASAP')])
        result = term()
        if result == STOP:
            keep_looping = False
        else:
            p.force_process()
    facts = p.known_facts()  # profit
    save_labeled_evidence_to_csv(facts.items(), output_file)
