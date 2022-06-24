import random
import re
import copy
import socket
import threading
from multiprocessing import Process, Queue
import time
import ssl

from input_tree_node import Node
from input_tree import InputTree
from input_tree_mutator import Mutator
from helper_functions import _print_exception, _parse_args

class Fuzzer:

    def __init__(self, verbose, seed, outfilename, seedfile):
        self.read_config(args.config)

        self.verbose = verbose
        self.seed = seed
        self.lock = threading.Lock()
        self.outfilename = outfilename
        self.seedfile = seedfile

    def read_config(self, configfile):
        config_content = open(configfile).read().replace('config.', 'self.')
        exec(config_content)
        if False in [item in self.__dict__ for item in ["target_urls", "target_host_headers", "grammar", "min_num_mutations", "max_num_mutations", "symbol_mutation_types"]]:
            print("Please make sure that the configuration is complete.")
            exit()

        self.target_hosts = {self.target_urls[i]:self.target_host_headers[i] for i in range(len(self.target_urls))}
 
    def send_fuzzy_data(self, inputdata, list_responses):
        try:
            request = inputdata.tree_to_request()
            _socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            _socket.settimeout(4)

            _wsocket = _socket

            print(inputdata.host, inputdata.port, inputdata.scheme)

            if inputdata.scheme == 'https':
                context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
                _wsocket = context.wrap_socket(_socket, server_hostname=inputdata.host)

            _wsocket.connect((inputdata.host, int(inputdata.port)))
            _wsocket.sendall(request)

            response = b''
            while True:
                data = _wsocket.recv(2048)
                if not data:
                    break
                else:
                    response += data

            _wsocket.shutdown(socket.SHUT_RDWR)
            _wsocket.close()

            with self.lock:
                list_responses.append(response)
        except socket.timeout:
            with self.lock:
                list_responses.append(b"takes too long")

        except Exception as exception:
            _print_exception([request])
            raise exception

    def get_responses(self, seed, request):
        threads = []
        list_responses = []
        for target_url in self.target_urls:
            request.seed = seed
            request.url = target_url
            request.host_header = self.target_hosts[target_url]

            request_copy = copy.deepcopy(request)
            thread = threading.Thread(target=self.send_fuzzy_data, args=(request_copy, list_responses))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(5)

        return list_responses

    def blackbox_fuzz_parallel_batch(self):
        for j in range(1): # number of batches
            num_procs = 64
            batch_size = 1000
            seeds_splitted = [[j*batch_size + i for i in list(range(i, batch_size, num_procs))] for i in range(num_procs)]
            quot = Queue()
            processes = [Process(target=self.run, args=(seeds_splitted[i], quot)) for i in range(num_procs)]
            responses_list = []

            for i, proc in enumerate(processes):
                proc.start()

            result = [quot.get() for p in processes]

            for i, proc in enumerate(processes):
                proc.join()

            responses_list = [ent for sublist in result for ent in sublist]

            with open("batch{}.out".format(j), 'w') as outfile:
                outfile.write("\n".join(responses_list))
                outfile.write("\n")

    def blackbox_fuzz_individual(self, filename=None, seeds=[None]):
        if seeds == [None]:
            with open(filename, 'r') as _file:
                seeds = [int(line.strip()) for line in _file.readlines()]

        num_procs = 64
        seeds_splitted = [[seeds[i] for i in list(range(i, len(seeds), num_procs))] for i in range(num_procs)]
        quot = Queue()
        processes = [Process(target=self.run_individual, args=(seeds_splitted[i], quot)) for i in range(num_procs)]
        responses_list = []

        for i, proc in enumerate(processes):
            proc.start()

        result = [quot.get() for p in processes]

        for i, proc in enumerate(processes):
            proc.join()

        responses_list = [ent for sublist in result for ent in sublist]

        if self.outfilename is None:
            print("\n".join(responses_list))
            print("\n")
        else:
            with open(self.outfilename, 'w') as outfile:
                outfile.write("\n".join(responses_list))
                outfile.write("\n")

    def run(self, seeds, _queue):
        responses_list = []
        for seed in seeds:
            base_input = InputTree(self.grammar, seed, "http://hostname/uri", False)
            base_input.build_tree(base_input.root)

            mutator = Mutator(self.symbol_mutation_types, self.char_pool, base_input, seed, self.min_num_mutations, self.max_num_mutations, self.verbose)
            mutator.mutate_input()
            responses = self.get_responses(seed, base_input)
            responses_list.append("{} ***** {} ***** {} ***** {}".format(seed, base_input.tree_to_request(), responses, mutator.mutation_messages))

        _queue.put(responses_list)

    def run_individual(self, seeds, _queue):
        responses_list = []
        for seed in seeds:
            base_input = InputTree(self.grammar, seed, "http://hostname/uri", False)
            base_input.build_tree(base_input.root)

            mutator = Mutator(self.symbol_mutation_types, self.char_pool, base_input, seed, self.min_num_mutations, self.max_num_mutations, self.verbose)
            mutator.mutate_input()
            responses = self.get_responses(seed, base_input)
            responses_list.append("{} ***** {} ***** {} ***** {}".format(seed, base_input.tree_to_request(), responses, mutator.mutation_messages))

        _queue.put(responses_list)

args = _parse_args()
start = time.time()

fuzzer = Fuzzer(args.verbose, args.seed, args.outfilename, args.seedfile)
if args.individual_mode:
    fuzzer.blackbox_fuzz_individual(fuzzer.seedfile, [fuzzer.seed])
else:
    fuzzer.blackbox_fuzz_parallel_batch()

print(time.time() - start)
