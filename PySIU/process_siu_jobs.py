#!/usr/bin/env python
# coding=utf-8

__author__ = 'Esteban Garcia-Gurtubay'
__copyright__ = 'Ericsson Spain 2013'
__version__ = 'R13A01'
__email__ = 'esteban.garcia.gurtubay@gmail.com'
__date__ = '19/06/2013 17:07:15'


# Description     : Run a batch of generic commands against SIUs, with multiprocess.
# Note            : It has to be run within a proper virtualenv


import json
import multiprocessing
import pprint
import time


class Multiprocess_SIU(object):
    def __init__(self, json_dump_full_filename, logger, siu_data_dict_list, processing_function,
                 num_workers=40):

        """Main process that launches dedicated Worker subprocesses
        Use num_workers=1 to force a single process
        """

        now = time.localtime()
        full_timestamp_suffix = time.strftime('%d%b%Y_%H%M%S', now)


        # Initialize a queue
        siu_jobs_queue = multiprocessing.JoinableQueue()

        # Fill the queue with job tuples
        for siu_data_dict in siu_data_dict_list:
            # For each SIU, put a copy of the siu_job_dict in the Queue
            siu_jobs_queue.put(siu_data_dict)

        # Calculate how many results we should expect
        num_expected_job_results = len(siu_data_dict_list)

        # Make a queue to store the workers results
        siu_results_queue = multiprocessing.Queue()

        # Launch worker process objects
        total_workers = min(siu_jobs_queue.qsize(), num_workers)

        for i in range(1, 1 + total_workers):
            logger.info('Creating worker process %i of %i' % (i, total_workers))

            # Put a poison pill in the jobs queue
            siu_jobs_queue.put(None)

            # Make a dedicated logger per Worker
            worker_logger_object_name = 'pysiu_process.%i' % i
            worker_log_filename = 'pysiu_process.%i.log' % i
            worker_logger = logger.get_sublogger(worker_logger_object_name, worker_log_filename)

            # Instantiate the Process Worker
            worker = Worker_Process(siu_jobs_queue, siu_results_queue, worker_logger, processing_function)

            # Go!
            worker.start()
            logger.info('')


        # Read the session results as soon as they are put in the queue by the workers
        # Dump them to a text file in JSON format, so that it can be read
        # externally for later analysis/processing
        logger.info('Dumping session results to JSON file: %s' % json_dump_full_filename)
        with open(json_dump_full_filename, 'w') as json_dump_file:
            num_job_results_collected = 0
            while num_job_results_collected < num_expected_job_results:
                logger.info('Retrieving list of session results %i [of %i] from queue' % (1+num_job_results_collected, num_expected_job_results))
                worker_session_result_dict_list = siu_results_queue.get()
                num_job_results_collected += 1

                logger.debug('Session results:')
                logger.debug(pprint.pformat(worker_session_result_dict_list))

                logger.info('Dumping to file in JSON format')
                json.dump(worker_session_result_dict_list, json_dump_file, encoding='ISO-8859-1')

                json_dump_file.write('\n')
                logger.info('')

        logger.info('Finished collecting results')

        siu_jobs_queue.join()
        logger.info('All workers finished!')
        logger.info('')


class Worker_Process(multiprocessing.Process):

    def __init__(self, siu_jobs_queue, siu_results_queue, worker_logger, processing_function):
        multiprocessing.Process.__init__(self)
        self.logger = worker_logger
        self.siu_jobs_queue = siu_jobs_queue
        self.siu_results_queue = siu_results_queue
        self.processing_function = processing_function


    def run(self):
        while True:
            # Retrieve from the queue a dict {'siu_name', 'siu_ip'}
            siu_data_dict = self.siu_jobs_queue.get()
            self.logger.info('Current queue size is %i job(s)' % self.siu_jobs_queue.qsize())
            if siu_data_dict is None:
                # We reached the poison pill
                self.logger.info('Got poison pill. No more jobs in the queue. This worker is done!')
                self.siu_jobs_queue.task_done()
                break

            siu_name = siu_data_dict['siu_name']
            self.logger.info('Calling callback function for %s' % siu_name)

            session_result_dict_list = self.processing_function(siu_data_dict, self.logger)

            self.logger.debug('Removing job from queue')
            self.siu_jobs_queue.task_done()

            # Put all the session data in the results queue for later analysis
            self.logger.info('Putting into queue the session results list for SIU %s' % siu_name)
            self.siu_results_queue.put(session_result_dict_list)

        self.logger.info('Exiting worker')
