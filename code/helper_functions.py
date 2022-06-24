import sys
import linecache
import configargparse
import random

try:
    from urllib.parse import urlparse # for Python 3
except ImportError:
    from urlparse import urlparse # for Python 2 and Jython

def _parse_url(url):
    """ This function extracts certain 
        components from a given URL.
    """
    u = urlparse(url)
    authority = u.netloc
    uri = u.path[1:]+'?'+u.query

    if ':' not in authority:
        host = authority
    else:
        host, _ = authority.split(':')

    if u.scheme == 'https':
        port = 443
    else:
        port = 43

    if u.port:
        port = u.port

    return host, port, authority, uri, u.scheme

def _print_exception(extra_details=[]):
    """ This function prints exception details
        including the line number where the exception
        is raised, which is helpful in most cases.
    """
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print('EXCEPTION IN ({}, LINE {} "{}"): {}, {}'.format(filename, lineno, line.strip(), exc_obj, extra_details))

def _parse_args(): 
    """ This function is for parsing the command
        line arguments fed into the script.
    """
    parser = configargparse.ArgParser(description='T-Reqs: Grammar-based HTTP Fuzzer')

    parser.add('-c', dest="config", required=True, help='config file path')
    parser.add('-i', action="store_true", dest="individual_mode", help="Turns the individual mode on where the fuzzer is run only for specified seeds.")
    parser.add('-s', dest="seed", type=int, help="Only needed for individual mode. Seed parameter for random number generator.")
    parser.add('-v', action="store_true", dest="verbose", help="Only needed for individual mode. Adds verbosity.")
    parser.add('-o', dest="outfilename", help = "Only needed for individual mode. File to write output.")
    parser.add('-f', dest="seedfile", help = "Only needed for individual mode. Input file containing seeds.")

    args = parser.parse_args()

    return args

def random_choose_with_weights(possible_expansions):
    probabilities = [0]*len(possible_expansions)
    for index, expansion in enumerate(possible_expansions):
        if "prob=" in expansion:
            probability = expansion[expansion.find("=")+1:expansion.find(")")]
            probabilities[index] = float(probability)

    probabilities = [(1-sum(probabilities))/probabilities.count(0) if elem == 0 else elem for elem in probabilities]

    chosen_expansion = random.choices(possible_expansions, weights=probabilities)[0]
    # '(<headers-frame-1><data-frame-1>, opts(prob=0.9))'
    # for cases where symbol looks like above, trimming is needed
    if chosen_expansion.startswith('('):
        chosen_expansion = chosen_expansion.split(',')[0][1:]

    return chosen_expansion
